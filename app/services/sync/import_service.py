"""ADR-038 Phase B.3 — HR sync package import into database."""
from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.services.employee_import_profile_override_service import employee_overrides_available
from app.services.hr_import_profile_override_service import prepare_profile_override_for_storage
from app.services.sync.package_schema import (
    EmployeeImportProfileOverrideSyncRecord,
    digits_only,
    normalize_full_name,
)
from app.services.sync.package_validator import validate_sync_package


class SyncImportError(RuntimeError):
    """Raised when import cannot proceed (missing tables, invalid package)."""


class EmployeeResolveStatus(str, Enum):
    RESOLVED = "RESOLVED"
    ORPHAN = "ORPHAN"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True)
class EmployeeResolveResult:
    status: EmployeeResolveStatus
    employee_id: Optional[int] = None
    candidate_ids: tuple[int, ...] = ()


@dataclass
class SyncImportResult:
    package_path: Path
    employee_records: int = 0
    override_records: int = 0
    resolved_count: int = 0
    orphan_count: int = 0
    ambiguous_count: int = 0
    applied_count: int = 0
    skipped_count: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    validation_ok: bool = False
    dry_run: bool = True


_SYNC_PROVENANCE_KEY = "_sync_provenance"


def _table_exists(conn: Connection, table: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = :table
            LIMIT 1
            """
        ),
        {"table": table},
    ).first()
    return row is not None


def _column_exists(conn: Connection, table: str, column: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = :table
              AND column_name = :column
            LIMIT 1
            """
        ),
        {"table": table, "column": column},
    ).first()
    return row is not None


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text_val = value.strip()
    if text_val.endswith("Z"):
        text_val = text_val[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text_val)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _read_jsonl_records(package_path: Path, filename: str) -> list[dict[str, Any]]:
    with zipfile.ZipFile(package_path, mode="r") as archive:
        if filename not in archive.namelist():
            return []
        content = archive.read(filename).decode("utf-8")
    records: list[dict[str, Any]] = []
    for line in content.splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            records.append(payload)
    return records


def _load_override_records(package_path: Path) -> list[EmployeeImportProfileOverrideSyncRecord]:
    records: list[EmployeeImportProfileOverrideSyncRecord] = []
    for payload in _read_jsonl_records(package_path, "employee_import_profile_overrides.jsonl"):
        record, err = EmployeeImportProfileOverrideSyncRecord.from_dict(payload)
        if record is not None:
            records.append(record)
        elif err:
            raise SyncImportError(f"invalid override record in package: {err}")
    return records


def resolve_employee_key(conn: Connection, employee_key: str) -> EmployeeResolveResult:
    """Resolve sync employee_key to a target directory employee_id."""
    key = (employee_key or "").strip()
    if key.startswith("iin:"):
        iin_digits = digits_only(key[4:])
        if len(iin_digits) != 12:
            return EmployeeResolveResult(status=EmployeeResolveStatus.ORPHAN)

        if not _table_exists(conn, "employee_identities"):
            return EmployeeResolveResult(status=EmployeeResolveStatus.ORPHAN)

        rows = conn.execute(
            text(
                """
                SELECT DISTINCT ei.employee_id
                FROM public.employee_identities ei
                WHERE ei.identity_type = 'IIN'
                  AND ei.valid_to IS NULL
                  AND regexp_replace(COALESCE(ei.identity_value, ''), '[^0-9]', '', 'g') = :iin
                ORDER BY ei.employee_id
                """
            ),
            {"iin": iin_digits},
        ).fetchall()
        candidate_ids = tuple(int(row[0]) for row in rows if row and row[0] is not None)
        if len(candidate_ids) == 1:
            return EmployeeResolveResult(
                status=EmployeeResolveStatus.RESOLVED,
                employee_id=candidate_ids[0],
                candidate_ids=candidate_ids,
            )
        if len(candidate_ids) > 1:
            return EmployeeResolveResult(
                status=EmployeeResolveStatus.AMBIGUOUS,
                candidate_ids=candidate_ids,
            )
        return EmployeeResolveResult(status=EmployeeResolveStatus.ORPHAN)

    if key.startswith("name:"):
        normalized_key = key[5:].strip()
        if not normalized_key:
            return EmployeeResolveResult(status=EmployeeResolveStatus.ORPHAN)

        rows = conn.execute(
            text(
                """
                SELECT employee_id
                FROM public.employees
                WHERE lower(replace(trim(full_name), 'ё', 'е')) = :norm_name
                ORDER BY employee_id
                """
            ),
            {"norm_name": normalized_key},
        ).fetchall()
        candidate_ids = tuple(int(row[0]) for row in rows if row and row[0] is not None)
        if len(candidate_ids) == 1:
            return EmployeeResolveResult(
                status=EmployeeResolveStatus.RESOLVED,
                employee_id=candidate_ids[0],
                candidate_ids=candidate_ids,
            )
        if len(candidate_ids) > 1:
            return EmployeeResolveResult(
                status=EmployeeResolveStatus.AMBIGUOUS,
                candidate_ids=candidate_ids,
            )
        return EmployeeResolveResult(status=EmployeeResolveStatus.ORPHAN)

    return EmployeeResolveResult(status=EmployeeResolveStatus.ORPHAN)


def _build_profile_override_for_import(record: EmployeeImportProfileOverrideSyncRecord) -> dict[str, Any]:
    override = prepare_profile_override_for_storage(record.profile_override)
    provenance = {
        "base_source_file": record.base_source_file,
        "base_source_batch_id": record.base_source_batch_id,
        "base_source_row_id": record.base_source_row_id,
        "source_employee_id": record.source_employee_id,
        "source_updated_by_user_id": record.source_updated_by_user_id,
        "created_by_login": record.created_by_login,
        "updated_by_login": record.updated_by_login,
    }
    provenance = {key: value for key, value in provenance.items() if value is not None}
    if provenance:
        override[_SYNC_PROVENANCE_KEY] = provenance
    return override


def _apply_sync_override(
    conn: Connection,
    *,
    employee_id: int,
    record: EmployeeImportProfileOverrideSyncRecord,
) -> None:
    profile_override = _build_profile_override_for_import(record)
    created_at = _parse_iso_datetime(record.created_at) or datetime.now(timezone.utc)
    updated_at = _parse_iso_datetime(record.updated_at) or created_at
    base_imported_at = _parse_iso_datetime(record.base_imported_at)

    has_provenance = _column_exists(conn, "employee_import_profile_overrides", "base_batch_id")
    if has_provenance:
        conn.execute(
            text(
                """
                INSERT INTO public.employee_import_profile_overrides (
                    employee_id,
                    profile_override,
                    profile_status,
                    profile_review_status,
                    base_batch_id,
                    base_row_id,
                    base_imported_at,
                    created_by,
                    updated_by,
                    created_at,
                    updated_at
                )
                VALUES (
                    :employee_id,
                    CAST(:profile_override AS JSONB),
                    :profile_status,
                    :profile_review_status,
                    NULL,
                    NULL,
                    :base_imported_at,
                    NULL,
                    NULL,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT (employee_id) DO UPDATE SET
                    profile_override = EXCLUDED.profile_override,
                    profile_status = EXCLUDED.profile_status,
                    profile_review_status = EXCLUDED.profile_review_status,
                    base_imported_at = EXCLUDED.base_imported_at,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "employee_id": employee_id,
                "profile_override": json.dumps(profile_override, ensure_ascii=False),
                "profile_status": record.profile_status,
                "profile_review_status": record.profile_review_status,
                "base_imported_at": base_imported_at,
                "created_at": created_at,
                "updated_at": updated_at,
            },
        )
        return

    conn.execute(
        text(
            """
            INSERT INTO public.employee_import_profile_overrides (
                employee_id,
                profile_override,
                profile_status,
                profile_review_status,
                updated_by,
                created_at,
                updated_at
            )
            VALUES (
                :employee_id,
                CAST(:profile_override AS JSONB),
                :profile_status,
                :profile_review_status,
                NULL,
                :created_at,
                :updated_at
            )
            ON CONFLICT (employee_id) DO UPDATE SET
                profile_override = EXCLUDED.profile_override,
                profile_status = EXCLUDED.profile_status,
                profile_review_status = EXCLUDED.profile_review_status,
                updated_at = EXCLUDED.updated_at
            """
        ),
        {
            "employee_id": employee_id,
            "profile_override": json.dumps(profile_override, ensure_ascii=False),
            "profile_status": record.profile_status,
            "profile_review_status": record.profile_review_status,
            "created_at": created_at,
            "updated_at": updated_at,
        },
    )


def import_hr_sync_package(
    conn: Connection,
    *,
    package_path: Path,
    apply_changes: bool = False,
) -> SyncImportResult:
    """Import overrides from a validated sync package (dry-run or apply)."""
    dry_run = not apply_changes
    result = SyncImportResult(package_path=package_path, dry_run=dry_run)

    if not employee_overrides_available(conn):
        result.errors.append(
            "employee_import_profile_overrides not available — run alembic upgrade head"
        )
        return result

    validation = validate_sync_package(package_path)
    result.validation_ok = validation.ok
    result.warnings.extend(validation.warnings)
    if not validation.ok:
        result.errors.extend(validation.errors)
        result.errors.append("import aborted: package validation failed")
        return result

    result.employee_records = len(_read_jsonl_records(package_path, "employees.jsonl"))
    override_records = _load_override_records(package_path)
    result.override_records = len(override_records)

    for record in override_records:
        resolution = resolve_employee_key(conn, record.employee_key)
        if resolution.status == EmployeeResolveStatus.RESOLVED:
            result.resolved_count += 1
            if apply_changes:
                assert resolution.employee_id is not None
                _apply_sync_override(conn, employee_id=resolution.employee_id, record=record)
                result.applied_count += 1
            continue

        result.skipped_count += 1
        if resolution.status == EmployeeResolveStatus.ORPHAN:
            result.orphan_count += 1
            result.warnings.append(
                f"employee_key not found: {record.employee_key}"
            )
        elif resolution.status == EmployeeResolveStatus.AMBIGUOUS:
            result.ambiguous_count += 1
            result.warnings.append(
                f"employee_key ambiguous: {record.employee_key} "
                f"candidates={list(resolution.candidate_ids)}"
            )

    return result
