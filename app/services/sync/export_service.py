"""ADR-038 Phase B.2 — HR sync package export from database."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.services.employee_import_profile_override_service import employee_overrides_available
from app.services.sync.package_schema import (
    EmployeeImportProfileOverrideSyncRecord,
    EmployeeSyncRecord,
    build_employee_key,
    digits_only,
)
from app.services.sync.package_validator import validate_sync_package
from app.services.sync.package_writer import resolve_sync_package_path, write_sync_package


class SyncExportError(RuntimeError):
    """Raised when export cannot complete (missing tables, existing file, validation failure)."""


@dataclass
class SyncExportResult:
    output_path: Path
    employee_count: int
    override_count: int
    skipped_employee_count: int = 0
    skipped_override_count: int = 0
    warnings: list[str] = field(default_factory=list)
    validation_ok: bool = False


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


def _parse_jsonb(value: Any) -> Any:
    if isinstance(value, str):
        return json.loads(value)
    return value


def _iso_utc(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.replace(microsecond=0).isoformat()
    return str(value)


def _employee_status(is_active: Any) -> str:
    if is_active is None:
        return "active"
    return "active" if bool(is_active) else "inactive"


def _fetch_alembic_revision(conn: Connection) -> Optional[str]:
    if not _table_exists(conn, "alembic_version"):
        return None
    row = conn.execute(text("SELECT version_num FROM public.alembic_version LIMIT 1")).first()
    if not row:
        return None
    return str(row[0])


def _load_override_rows(conn: Connection) -> list[dict[str, Any]]:
    has_provenance = _column_exists(conn, "employee_import_profile_overrides", "base_batch_id")
    has_org_units = _table_exists(conn, "org_units") and _column_exists(conn, "org_units", "code")
    has_positions = _table_exists(conn, "positions") and _column_exists(conn, "positions", "name")
    has_identities = _table_exists(conn, "employee_identities")
    has_users = _table_exists(conn, "users") and _column_exists(conn, "users", "login")
    has_batches = _table_exists(conn, "hr_import_batches") and _column_exists(conn, "hr_import_batches", "file_name")

    provenance_cols = ""
    if has_provenance:
        provenance_cols = """
            o.base_batch_id,
            o.base_row_id,
            o.base_imported_at,
            o.created_by,
        """

    join_org = ""
    org_select = "NULL::text AS org_unit_code"
    if has_org_units:
        join_org = "LEFT JOIN public.org_units ou ON ou.unit_id = e.org_unit_id"
        org_select = "ou.code AS org_unit_code"

    join_pos = ""
    pos_select = "NULL::text AS position_name"
    if has_positions:
        join_pos = "LEFT JOIN public.positions p ON p.position_id = e.position_id"
        pos_select = "p.name AS position_name"

    join_iin = ""
    iin_select = "NULL::text AS iin_value"
    if has_identities:
        join_iin = """
            LEFT JOIN LATERAL (
                SELECT regexp_replace(COALESCE(ei.identity_value, ''), '[^0-9]', '', 'g') AS iin_digits
                FROM public.employee_identities ei
                WHERE ei.employee_id = e.employee_id
                  AND ei.identity_type = 'IIN'
                  AND ei.valid_to IS NULL
                ORDER BY ei.identity_id
                LIMIT 1
            ) ei ON TRUE
        """
        iin_select = """
            CASE
                WHEN length(ei.iin_digits) = 12 THEN ei.iin_digits
                ELSE NULL
            END AS iin_value
        """

    join_created = ""
    created_login_select = "NULL::text AS created_by_login"
    if has_users and has_provenance:
        join_created = "LEFT JOIN public.users cu ON cu.user_id = o.created_by"
        created_login_select = "cu.login AS created_by_login"

    join_updated = ""
    updated_login_select = "NULL::text AS updated_by_login"
    if has_users:
        join_updated = "LEFT JOIN public.users uu ON uu.user_id = o.updated_by"
        updated_login_select = "uu.login AS updated_by_login"

    join_batch = ""
    batch_file_select = "NULL::text AS base_source_file"
    if has_batches and has_provenance:
        join_batch = "LEFT JOIN public.hr_import_batches b ON b.batch_id = o.base_batch_id"
        batch_file_select = "b.file_name AS base_source_file"

    sql = f"""
        SELECT
            o.employee_id,
            o.profile_override,
            o.profile_status,
            o.profile_review_status,
            o.created_at,
            o.updated_at,
            o.updated_by,
            {provenance_cols}
            e.full_name,
            e.is_active,
            {org_select},
            {pos_select},
            {iin_select},
            {created_login_select},
            {updated_login_select},
            {batch_file_select}
        FROM public.employee_import_profile_overrides o
        JOIN public.employees e ON e.employee_id = o.employee_id
        {join_org}
        {join_pos}
        {join_iin}
        {join_created}
        {join_updated}
        {join_batch}
        ORDER BY o.employee_id
    """
    rows = conn.execute(text(sql)).mappings().all()
    return [dict(row) for row in rows]


def _try_build_employee_key(
    *,
    employee_id: int,
    full_name: Optional[str],
    iin_value: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    iin_digits = digits_only(iin_value or "")
    iin_for_key = iin_digits if len(iin_digits) == 12 else None
    try:
        return build_employee_key(iin=iin_for_key, full_name=full_name), None
    except ValueError:
        return None, (
            f"skipped employee_id={employee_id}: cannot build employee_key "
            f"(missing valid IIN and normalized full_name)"
        )


def _build_employee_record(
    row: dict[str, Any],
    *,
    employee_key: str,
) -> EmployeeSyncRecord:
    iin_value = row.get("iin_value")
    iin_digits = digits_only(str(iin_value or ""))
    iin_export = iin_digits if len(iin_digits) == 12 else None
    org_code = row.get("org_unit_code")
    position_name = row.get("position_name")
    return EmployeeSyncRecord(
        employee_key=employee_key,
        source_employee_id=int(row["employee_id"]),
        full_name=str(row["full_name"] or "").strip(),
        iin=iin_export,
        org_unit_key=str(org_code).strip() if org_code else None,
        position_key=str(position_name).strip() if position_name else None,
        status=_employee_status(row.get("is_active")),
    )


def _build_override_record(row: dict[str, Any], *, employee_key: str) -> EmployeeImportProfileOverrideSyncRecord:
    profile_override = _parse_jsonb(row.get("profile_override"))
    if not isinstance(profile_override, dict):
        profile_override = {}

    base_batch_id = row.get("base_batch_id")
    base_row_id = row.get("base_row_id")
    return EmployeeImportProfileOverrideSyncRecord(
        employee_key=employee_key,
        profile_override=profile_override,
        profile_status=str(row.get("profile_status") or "active"),
        profile_review_status=str(row.get("profile_review_status") or "pending"),
        created_at=_iso_utc(row.get("created_at")),
        updated_at=_iso_utc(row.get("updated_at")),
        created_by_login=row.get("created_by_login"),
        updated_by_login=row.get("updated_by_login"),
        base_imported_at=_iso_utc(row.get("base_imported_at")),
        base_source_file=row.get("base_source_file"),
        base_source_batch_id=int(base_batch_id) if base_batch_id is not None else None,
        base_source_row_id=int(base_row_id) if base_row_id is not None else None,
        source_employee_id=int(row["employee_id"]),
        source_updated_by_user_id=int(row["updated_by"]) if row.get("updated_by") is not None else None,
    )


def export_hr_sync_package(
    conn: Connection,
    *,
    output_dir: Path,
    source_instance_id: str,
    source_organization: dict[str, str],
    environment: str = "server",
    notes: Optional[str] = None,
    exported_by_user_login: Optional[str] = None,
    exported_at: Optional[datetime] = None,
) -> SyncExportResult:
    """Export employee overrides from DB into a validated sync package zip."""
    if not employee_overrides_available(conn):
        raise SyncExportError(
            "employee_import_profile_overrides not available — run alembic upgrade head"
        )

    warnings: list[str] = []
    skipped_override_count = 0

    export_moment = exported_at or datetime.now(timezone.utc)
    if export_moment.tzinfo is None:
        export_moment = export_moment.replace(tzinfo=timezone.utc)
    else:
        export_moment = export_moment.astimezone(timezone.utc)

    target_path = resolve_sync_package_path(
        output_dir,
        source_instance_id=source_instance_id,
        exported_at=export_moment,
    )
    if target_path.exists():
        raise SyncExportError(f"sync package already exists: {target_path}")

    rows = _load_override_rows(conn)
    employees_by_key: dict[str, EmployeeSyncRecord] = {}
    overrides: list[EmployeeImportProfileOverrideSyncRecord] = []

    for row in rows:
        employee_id = int(row["employee_id"])
        employee_key, key_warning = _try_build_employee_key(
            employee_id=employee_id,
            full_name=row.get("full_name"),
            iin_value=row.get("iin_value"),
        )
        if not employee_key:
            skipped_override_count += 1
            if key_warning:
                warnings.append(key_warning)
            continue

        overrides.append(_build_override_record(row, employee_key=employee_key))
        if employee_key not in employees_by_key:
            employees_by_key[employee_key] = _build_employee_record(row, employee_key=employee_key)

    metadata_extensions: dict[str, Any] = {
        "alembic_revision": _fetch_alembic_revision(conn),
        "exported_by_user_login": exported_by_user_login,
    }

    write_sync_package(
        output_dir,
        source_instance_id=source_instance_id,
        source_organization=source_organization,
        employees=list(employees_by_key.values()),
        overrides=overrides,
        environment=environment,
        notes=notes,
        exported_at=export_moment,
        metadata_extensions=metadata_extensions,
    )

    validation = validate_sync_package(target_path)
    if validation.warnings:
        warnings.extend(validation.warnings)

    result = SyncExportResult(
        output_path=target_path,
        employee_count=len(employees_by_key),
        override_count=len(overrides),
        skipped_employee_count=0,
        skipped_override_count=skipped_override_count,
        warnings=warnings,
        validation_ok=validation.ok,
    )
    if not validation.ok:
        detail = "; ".join(validation.errors)
        raise SyncExportError(f"exported package failed validation: {detail}")
    return result
