"""HR control list import → staging persistence (ADR-038 Phase 2B)."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.models.hr_import import (
    BATCH_STATUS_FAILED,
    BATCH_STATUS_IN_REVIEW,
    BATCH_STATUS_PARSED,
    BATCH_STATUS_UPLOADED,
    CLASSIFICATION_CATEGORY_ROW,
    CLASSIFICATION_DECLARATION,
    CLASSIFICATION_DUPLICATE_IIN,
    CLASSIFICATION_INVALID_IIN,
    CLASSIFICATION_NORMAL,
    CLASSIFICATION_PART_TIME,
    CLASSIFICATION_SUMMARY_ROW,
    MATCH_STATUS_NOT_PROCESSED,
    REVIEW_STATUS_PENDING,
    ROW_TYPE_DECLARATION_PERSON,
    ROW_TYPE_DECLARATION_ROW,
    ROW_TYPE_CATEGORY_ROW,
    ROW_TYPE_SUMMARY_ROW,
    SOURCE_TYPE_HR_CONTROL_LIST,
)
from app.services.hr_import_document_candidate_service import parse_and_persist_document_candidates
from app.services.hr_import_normalized_record_service import populate_normalized_records
from scripts.import_hr_control_list import ParsedRow, build_audit, parse_workbook

# Phase 2B workflow aliases (DB CHECK constraint uses Phase 2A names).
BATCH_STATUS_CREATED = BATCH_STATUS_UPLOADED
BATCH_STATUS_REVIEW_READY = BATCH_STATUS_IN_REVIEW


def create_batch(
    conn: Connection,
    *,
    source_type: str,
    file_name: str,
    imported_by: int,
    imported_at: Optional[datetime] = None,
) -> int:
    """Create an empty import batch with status CREATED (UPLOADED)."""
    at = imported_at or datetime.now(timezone.utc)
    batch_id = conn.execute(
        text(
            """
            INSERT INTO public.hr_import_batches (
                source_type, file_name, imported_by, imported_at,
                status, total_rows, valid_rows, error_rows
            )
            VALUES (
                :source_type, :file_name, :imported_by, :imported_at,
                :status, 0, 0, 0
            )
            RETURNING batch_id
            """
        ),
        {
            "source_type": source_type,
            "file_name": file_name,
            "imported_by": imported_by,
            "imported_at": at,
            "status": BATCH_STATUS_CREATED,
        },
    ).scalar_one()
    return int(batch_id)


def _duplicate_iins(rows: list[ParsedRow]) -> set[str]:
    counts = Counter(
        row.iin_digits for row in rows if row.iin_digits and row.is_employee_roster
    )
    return {iin for iin, count in counts.items() if count > 1}


def classify_row(row: ParsedRow, duplicate_iins: set[str]) -> str:
    """Primary row classification stored in normalized_payload.metadata."""
    if row.row_type in (ROW_TYPE_DECLARATION_PERSON, ROW_TYPE_DECLARATION_ROW):
        return CLASSIFICATION_DECLARATION
    if row.row_type == ROW_TYPE_CATEGORY_ROW:
        return CLASSIFICATION_CATEGORY_ROW
    if row.row_type == ROW_TYPE_SUMMARY_ROW:
        return CLASSIFICATION_SUMMARY_ROW
    if row.sheet_type == "part_time":
        return CLASSIFICATION_PART_TIME
    if not row.is_employee_roster:
        return CLASSIFICATION_SUMMARY_ROW
    if row.iin_digits and not row.iin_valid:
        return CLASSIFICATION_INVALID_IIN
    if row.iin_digits in duplicate_iins:
        return CLASSIFICATION_DUPLICATE_IIN
    return CLASSIFICATION_NORMAL


def _build_row_payloads(
    row: ParsedRow,
    *,
    classification: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    raw_payload = dict(row.data)
    normalized_payload = {
        **row.data,
        "metadata": {
            "sheet_type": row.sheet_type,
            "classification": classification,
            "iin_valid": row.iin_valid,
            "row_type": row.row_type,
            "declaration_group": row.declaration_group or None,
            "is_employee_roster": row.is_employee_roster,
            "is_part_time": row.sheet_type == "part_time",
        },
    }
    return raw_payload, normalized_payload


def _persist_rows(
    conn: Connection,
    *,
    batch_id: int,
    rows: list[ParsedRow],
) -> None:
    duplicate_iins = _duplicate_iins(rows)
    for row in rows:
        classification = classify_row(row, duplicate_iins)
        raw_payload, normalized_payload = _build_row_payloads(row, classification=classification)
        error_codes = list(row.errors) if row.errors else None
        conn.execute(
            text(
                """
                INSERT INTO public.hr_import_rows (
                    batch_id, source_sheet, source_row_number,
                    raw_payload, normalized_payload,
                    match_status, review_status, error_codes
                )
                VALUES (
                    :batch_id, :source_sheet, :source_row_number,
                    CAST(:raw_payload AS jsonb), CAST(:normalized_payload AS jsonb),
                    :match_status, :review_status, :error_codes
                )
                """
            ),
            {
                "batch_id": batch_id,
                "source_sheet": row.data["source_sheet"],
                "source_row_number": int(row.data["source_row_number"]),
                "raw_payload": json.dumps(raw_payload, ensure_ascii=False),
                "normalized_payload": json.dumps(normalized_payload, ensure_ascii=False),
                "match_status": MATCH_STATUS_NOT_PROCESSED,
                "review_status": REVIEW_STATUS_PENDING,
                "error_codes": error_codes,
            },
        )


def _update_batch_counts(
    conn: Connection,
    *,
    batch_id: int,
    rows: list[ParsedRow],
    status: str,
) -> None:
    total_rows = len(rows)
    error_rows = sum(1 for row in rows if row.errors)
    valid_rows = total_rows - error_rows
    conn.execute(
        text(
            """
            UPDATE public.hr_import_batches
            SET status = :status,
                total_rows = :total_rows,
                valid_rows = :valid_rows,
                error_rows = :error_rows
            WHERE batch_id = :batch_id
            """
        ),
        {
            "batch_id": batch_id,
            "status": status,
            "total_rows": total_rows,
            "valid_rows": valid_rows,
            "error_rows": error_rows,
        },
    )


def summarize_batch(conn: Connection, batch_id: int) -> dict[str, Any]:
    """Return Phase 0-style audit summary for a staged batch."""
    rows = conn.execute(
        text(
            """
            SELECT
                normalized_payload,
                error_codes,
                match_status
            FROM public.hr_import_rows
            WHERE batch_id = :batch_id
            ORDER BY row_id
            """
        ),
        {"batch_id": batch_id},
    ).mappings().all()

    parsed_rows: list[ParsedRow] = []
    for db_row in rows:
        payload = dict(db_row["normalized_payload"] or {})
        metadata = payload.pop("metadata", {}) or {}
        data = {key: str(payload.get(key, "") or "") for key in payload}
        if "source_sheet" not in data:
            data["source_sheet"] = ""
        if "source_row_number" not in data:
            data["source_row_number"] = "0"

        iin_digits = data.get("iin", "")
        iin_valid = bool(metadata.get("iin_valid", False))
        errors = list(db_row["error_codes"] or [])

        parsed_rows.append(
            ParsedRow(
                data=data,
                sheet_type=str(metadata.get("sheet_type", "")),
                iin_valid=iin_valid,
                iin_digits=iin_digits,
                errors=errors,
            )
        )

    audit = build_audit(parsed_rows)
    return {
        "total_rows": audit["total_rows"],
        "valid_iin": audit["valid_iin"],
        "invalid_iin": audit["invalid_iin"],
        "duplicate_iin_groups": audit["duplicate_iin"],
        "duplicate_iin_rows": audit["duplicate_iin_rows"],
        "missing_full_name": audit["missing_full_name"],
        "missing_department": audit["missing_department"],
        "with_training": audit["with_training"],
        "with_certification": audit["with_certification"],
    }


def import_control_list(
    conn: Connection,
    *,
    file_path: Path | str,
    imported_by: int,
    source_type: str = SOURCE_TYPE_HR_CONTROL_LIST,
) -> tuple[int, dict[str, Any], list[str]]:
    """
    Parse control list Excel, persist batch + rows to staging, return summary.

    On success the batch ends in REVIEW_READY (IN_REVIEW). On failure the batch
    is marked FAILED and the exception propagates after the status update.
    """
    path = Path(file_path)
    batch_id = create_batch(
        conn,
        source_type=source_type,
        file_name=path.name,
        imported_by=imported_by,
    )

    try:
        parsed_rows, warnings = parse_workbook(path)
        _persist_rows(conn, batch_id=batch_id, rows=parsed_rows)
        parse_and_persist_document_candidates(conn, batch_id)
        populate_normalized_records(conn, batch_id)
        _update_batch_counts(
            conn,
            batch_id=batch_id,
            rows=parsed_rows,
            status=BATCH_STATUS_PARSED,
        )
        _update_batch_counts(
            conn,
            batch_id=batch_id,
            rows=parsed_rows,
            status=BATCH_STATUS_REVIEW_READY,
        )
        summary = summarize_batch(conn, batch_id)
        return batch_id, summary, warnings
    except Exception:
        conn.execute(
            text(
                """
                UPDATE public.hr_import_batches
                SET status = :status
                WHERE batch_id = :batch_id
                """
            ),
            {"batch_id": batch_id, "status": BATCH_STATUS_FAILED},
        )
        raise


def resolve_default_imported_by(conn: Connection) -> int:
    """Pick the lowest user_id for CLI staging when --imported-by is omitted."""
    user_id = conn.execute(
        text("SELECT user_id FROM public.users ORDER BY user_id LIMIT 1")
    ).scalar_one_or_none()
    if user_id is None:
        raise RuntimeError("No users in database — cannot set imported_by for staging import")
    return int(user_id)
