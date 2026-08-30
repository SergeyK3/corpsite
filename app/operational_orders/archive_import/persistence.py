"""Transactional persistence for validated archive import reports."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.engine import engine
from app.db.models.operational_order_archive_import import (
    IMPORT_BATCH_STATUS_IMPORTED,
    INITIAL_REVIEW_NEEDS_DOCUMENT_TYPE,
    INITIAL_REVIEW_NEEDS_REQUISITES,
    INITIAL_REVIEW_POSSIBLE_NON_ORDER,
    INITIAL_REVIEW_REQUISITES_PRECONFIRMED,
)
from app.operational_orders.archive_import.models import DryRunReport
from app.operational_orders.domain import content_fingerprint


ARCHIVE_IMPORT_FORMAT_VERSION = "WP-PO-002-v1"
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_INITIAL_REVIEW_BY_SOURCE_STATUS = {
    "Найден": INITIAL_REVIEW_REQUISITES_PRECONFIRMED,
    "Не найден": INITIAL_REVIEW_NEEDS_REQUISITES,
    "Требует проверки": INITIAL_REVIEW_NEEDS_DOCUMENT_TYPE,
    "Не является приказом": INITIAL_REVIEW_POSSIBLE_NON_ORDER,
}


class ArchiveImportPersistenceError(ValueError):
    """The dry-run report cannot be persisted as an import batch."""


@dataclass(frozen=True, slots=True)
class PersistedArchiveImportBatch:
    batch_id: int
    batch_fingerprint: str
    created: bool
    row_count: int


def calculate_batch_fingerprint(
    report: DryRunReport,
    *,
    source_manifest_sha256: str,
    format_version: str = ARCHIVE_IMPORT_FORMAT_VERSION,
) -> str:
    """Hash the manifest and deterministic set of validated source file identities."""
    manifest_sha256 = _normalize_sha256(source_manifest_sha256, field="source_manifest_sha256")
    version = str(format_version or "").strip()
    if not version:
        raise ArchiveImportPersistenceError("format_version is required")
    source_files = sorted(
        (
            row.source.source_number,
            row.source.relative_path,
            row.sha256 or "",
        )
        for row in report.rows
    )
    canonical = json.dumps(
        {
            "format_version": version,
            "source_manifest_sha256": manifest_sha256,
            "source_files": source_files,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return content_fingerprint(canonical)


def persist_archive_import_batch(
    *,
    report: DryRunReport,
    source_manifest_name: str,
    source_manifest_sha256: str,
    actor_user_id: int,
    connection: Connection | None = None,
    format_version: str = ARCHIVE_IMPORT_FORMAT_VERSION,
) -> PersistedArchiveImportBatch:
    """Persist one PASS report atomically, or return its existing idempotent batch."""
    prepared = _prepare_persistence(
        report=report,
        source_manifest_name=source_manifest_name,
        source_manifest_sha256=source_manifest_sha256,
        actor_user_id=actor_user_id,
        format_version=format_version,
    )
    if connection is not None:
        return _persist_prepared(connection, report=report, **prepared)
    with engine.begin() as owned_connection:
        return _persist_prepared(owned_connection, report=report, **prepared)


def _prepare_persistence(
    *,
    report: DryRunReport,
    source_manifest_name: str,
    source_manifest_sha256: str,
    actor_user_id: int,
    format_version: str,
) -> dict[str, object]:
    _validate_pass_report(report)
    try:
        actor_id = int(actor_user_id)
    except (TypeError, ValueError) as exc:
        raise ArchiveImportPersistenceError("actor_user_id must be a positive integer") from exc
    if actor_id <= 0:
        raise ArchiveImportPersistenceError("actor_user_id must be a positive integer")

    manifest_name = _leaf_name(source_manifest_name)
    root_name = _leaf_name(report.archive_root)
    manifest_sha256 = _normalize_sha256(source_manifest_sha256, field="source_manifest_sha256")
    version = str(format_version or "").strip()
    if not version:
        raise ArchiveImportPersistenceError("format_version is required")
    fingerprint = calculate_batch_fingerprint(
        report,
        source_manifest_sha256=manifest_sha256,
        format_version=version,
    )
    return {
        "source_manifest_name": manifest_name,
        "source_manifest_sha256": manifest_sha256,
        "source_root_name": root_name,
        "actor_user_id": actor_id,
        "format_version": version,
        "batch_fingerprint": fingerprint,
    }


def _validate_pass_report(report: DryRunReport) -> None:
    if report.outcome != "PASS" or report.errors:
        raise ArchiveImportPersistenceError("Only a PASS dry-run report can be persisted")
    summary = report.summary
    if (
        summary.error_rows != 0
        or summary.valid_rows != summary.total_rows
        or summary.total_rows != len(report.rows)
        or summary.existing_files != summary.total_rows
        or summary.unique_archive_sections
        != len({result.source.archive_section for result in report.rows})
    ):
        raise ArchiveImportPersistenceError("PASS report summary contains error rows or inconsistent counts")

    source_numbers: set[str] = set()
    relative_paths: set[str] = set()
    for result in report.rows:
        if not result.is_valid or any(issue.severity == "ERROR" for issue in result.issues):
            raise ArchiveImportPersistenceError(
                f"PASS report contains an invalid row at Excel row {result.source.excel_row}"
            )
        if not result.file_exists or result.file_size_bytes is None or not result.sha256:
            raise ArchiveImportPersistenceError(
                f"PASS report row {result.source.excel_row} has no validated physical file"
            )
        if result.file_size_bytes < 0:
            raise ArchiveImportPersistenceError(
                f"PASS report row {result.source.excel_row} has a negative file size"
            )
        if not result.source.source_number.strip():
            raise ArchiveImportPersistenceError("PASS report contains an empty source_row_number")
        if not result.source.relative_path.strip():
            raise ArchiveImportPersistenceError("PASS report contains an empty relative_path")
        _normalize_sha256(result.sha256, field=f"row {result.source.excel_row} file_sha256")
        if result.extension not in {".doc", ".docx", ".pdf"}:
            raise ArchiveImportPersistenceError(
                f"PASS report row {result.source.excel_row} has unsupported extension"
            )
        if result.source.source_status not in _INITIAL_REVIEW_BY_SOURCE_STATUS:
            raise ArchiveImportPersistenceError(
                f"Unsupported source status at Excel row {result.source.excel_row}: "
                f"{result.source.source_status!r}"
            )
        if result.source.source_number in source_numbers:
            raise ArchiveImportPersistenceError("PASS report contains duplicate source_row_number")
        if result.source.relative_path in relative_paths:
            raise ArchiveImportPersistenceError("PASS report contains duplicate relative_path")
        source_numbers.add(result.source.source_number)
        relative_paths.add(result.source.relative_path)


def _persist_prepared(
    connection: Connection,
    *,
    report: DryRunReport,
    source_manifest_name: object,
    source_manifest_sha256: object,
    source_root_name: object,
    actor_user_id: object,
    format_version: object,
    batch_fingerprint: object,
) -> PersistedArchiveImportBatch:
    batch = connection.execute(
        text(
            """
            INSERT INTO public.operational_order_import_batches (
                source_manifest_name,
                source_manifest_sha256,
                batch_fingerprint,
                format_version,
                source_root_name,
                sheet_name,
                status,
                total_rows,
                valid_rows,
                error_rows,
                file_count,
                archive_section_count,
                created_by_user_id
            ) VALUES (
                :source_manifest_name,
                :source_manifest_sha256,
                :batch_fingerprint,
                :format_version,
                :source_root_name,
                :sheet_name,
                :status,
                :total_rows,
                :valid_rows,
                :error_rows,
                :file_count,
                :archive_section_count,
                :created_by_user_id
            )
            ON CONFLICT (batch_fingerprint) DO UPDATE
            SET batch_fingerprint = operational_order_import_batches.batch_fingerprint
            RETURNING
                id,
                (xmax = 0) AS created,
                source_manifest_name,
                source_manifest_sha256,
                format_version,
                source_root_name,
                sheet_name,
                total_rows,
                valid_rows,
                error_rows,
                file_count,
                archive_section_count,
                created_by_user_id
            """
        ),
        {
            "source_manifest_name": source_manifest_name,
            "source_manifest_sha256": source_manifest_sha256,
            "batch_fingerprint": batch_fingerprint,
            "format_version": format_version,
            "source_root_name": source_root_name,
            "sheet_name": report.sheet_name,
            "status": IMPORT_BATCH_STATUS_IMPORTED,
            "total_rows": report.summary.total_rows,
            "valid_rows": report.summary.valid_rows,
            "error_rows": report.summary.error_rows,
            "file_count": report.summary.existing_files,
            "archive_section_count": report.summary.unique_archive_sections,
            "created_by_user_id": actor_user_id,
        },
    ).mappings().one()

    expected_batch = {
        "source_manifest_name": source_manifest_name,
        "source_manifest_sha256": source_manifest_sha256,
        "format_version": format_version,
        "source_root_name": source_root_name,
        "sheet_name": report.sheet_name,
        "total_rows": report.summary.total_rows,
        "valid_rows": report.summary.valid_rows,
        "error_rows": report.summary.error_rows,
        "file_count": report.summary.existing_files,
        "archive_section_count": report.summary.unique_archive_sections,
        "created_by_user_id": actor_user_id,
    }
    mismatched_batch_fields = [
        field for field, expected in expected_batch.items() if batch[field] != expected
    ]
    if mismatched_batch_fields:
        raise ArchiveImportPersistenceError(
            "Existing batch fingerprint has different metadata: "
            + ", ".join(mismatched_batch_fields)
        )

    batch_id = int(batch["id"])
    created = bool(batch["created"])
    if not created:
        _assert_existing_rows_match(connection, batch_id=batch_id, report=report)
        return PersistedArchiveImportBatch(
            batch_id=batch_id,
            batch_fingerprint=str(batch_fingerprint),
            created=False,
            row_count=len(report.rows),
        )

    for result in report.rows:
        source = result.source
        connection.execute(
            text(
                """
                INSERT INTO public.operational_order_import_rows (
                    batch_id,
                    source_row_number,
                    source_filename,
                    source_document_type,
                    source_status,
                    source_event_type,
                    source_order_number,
                    source_order_date,
                    source_note,
                    source_folder,
                    archive_section,
                    relative_path,
                    file_extension,
                    file_size,
                    file_sha256,
                    initial_review_state
                ) VALUES (
                    :batch_id,
                    :source_row_number,
                    :source_filename,
                    :source_document_type,
                    :source_status,
                    :source_event_type,
                    :source_order_number,
                    :source_order_date,
                    :source_note,
                    :source_folder,
                    :archive_section,
                    :relative_path,
                    :file_extension,
                    :file_size,
                    :file_sha256,
                    :initial_review_state
                )
                """
            ),
            {
                "batch_id": batch_id,
                "source_row_number": source.source_number,
                "source_filename": source.file_name,
                "source_document_type": source.document_type,
                "source_status": source.source_status,
                "source_event_type": source.event_type,
                "source_order_number": source.order_number or None,
                "source_order_date": result.parsed_order_date,
                "source_note": source.note or None,
                "source_folder": source.source_folder,
                "archive_section": source.archive_section,
                "relative_path": source.relative_path,
                "file_extension": result.extension,
                "file_size": result.file_size_bytes,
                "file_sha256": result.sha256,
                "initial_review_state": _INITIAL_REVIEW_BY_SOURCE_STATUS[source.source_status],
            },
        )

    return PersistedArchiveImportBatch(
        batch_id=batch_id,
        batch_fingerprint=str(batch_fingerprint),
        created=True,
        row_count=len(report.rows),
    )


def _assert_existing_rows_match(
    connection: Connection,
    *,
    batch_id: int,
    report: DryRunReport,
) -> None:
    existing_rows = connection.execute(
        text(
            """
            SELECT
                source_row_number,
                source_filename,
                source_document_type,
                source_status,
                source_event_type,
                source_order_number,
                source_order_date,
                source_note,
                source_folder,
                archive_section,
                relative_path,
                file_extension,
                file_size,
                file_sha256,
                initial_review_state
            FROM public.operational_order_import_rows
            WHERE batch_id = :batch_id
            ORDER BY source_row_number, relative_path
            """
        ),
        {"batch_id": batch_id},
    ).mappings().all()
    expected_rows = sorted(
        (
            {
                "source_row_number": result.source.source_number,
                "source_filename": result.source.file_name,
                "source_document_type": result.source.document_type,
                "source_status": result.source.source_status,
                "source_event_type": result.source.event_type,
                "source_order_number": result.source.order_number or None,
                "source_order_date": result.parsed_order_date,
                "source_note": result.source.note or None,
                "source_folder": result.source.source_folder,
                "archive_section": result.source.archive_section,
                "relative_path": result.source.relative_path,
                "file_extension": result.extension,
                "file_size": result.file_size_bytes,
                "file_sha256": result.sha256,
                "initial_review_state": _INITIAL_REVIEW_BY_SOURCE_STATUS[
                    result.source.source_status
                ],
            }
            for result in report.rows
        ),
        key=lambda row: (str(row["source_row_number"]), str(row["relative_path"])),
    )
    if [dict(row) for row in existing_rows] != expected_rows:
        raise ArchiveImportPersistenceError(
            "Existing batch fingerprint has different imported row metadata"
        )


def _normalize_sha256(value: str, *, field: str) -> str:
    normalized = str(value or "").strip().casefold()
    if not _SHA256_PATTERN.fullmatch(normalized):
        raise ArchiveImportPersistenceError(f"{field} must be a 64-character SHA-256 hex digest")
    return normalized


def _leaf_name(value: str) -> str:
    normalized = str(value or "").strip().rstrip("/\\")
    leaf = normalized.replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not leaf or leaf in {".", ".."} or ":" in leaf:
        raise ArchiveImportPersistenceError("A non-empty local basename is required")
    return Path(leaf).name
