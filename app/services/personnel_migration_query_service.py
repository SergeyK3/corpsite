"""Read-side queries for Personnel Migration Framework (PMF-3A)."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.engine import engine
from app.services.personnel_migration_commit_service import personnel_migration_available
from app.services.personnel_migration_types import (
    PersonnelMigrationNotFoundError,
    PersonnelMigrationValidationError,
)


def _require_available() -> None:
    if not personnel_migration_available():
        raise PersonnelMigrationValidationError("PMF schema is not available.")


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _serialize_domain_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "domain_code": row["domain_code"],
        "display_name": row["display_name"],
        "description": row.get("description"),
        "is_enabled": bool(row.get("is_enabled")),
        "target_table_names": _json_safe(row.get("target_table_names") or []),
        "control_list_columns": _json_safe(row.get("control_list_columns") or []),
        "created_at": _json_safe(row.get("created_at")),
        "updated_at": _json_safe(row.get("updated_at")),
    }


def _serialize_run_row(row: dict[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    return {
        "run_id": int(row["run_id"]),
        "domain_code": row["domain_code"],
        "employee_context_id": row.get("employee_context_id"),
        "person_id": row.get("person_id"),
        "run_status": row["run_status"],
        "started_at": _json_safe(row.get("started_at")),
        "committed_at": _json_safe(row.get("committed_at")),
        "voided_at": _json_safe(row.get("voided_at")),
        "started_by": row.get("started_by"),
        "committed_by": row.get("committed_by"),
        "voided_by": row.get("voided_by"),
        "void_reason": row.get("void_reason"),
        "metadata": _json_safe(metadata),
    }


def _serialize_item_row(row: dict[str, Any]) -> dict[str, Any]:
    draft_payload = row.get("draft_payload") or {}
    source_payload = row.get("source_payload") or {}
    validation_errors = row.get("validation_errors") or []
    if not isinstance(draft_payload, dict):
        draft_payload = {}
    if not isinstance(source_payload, dict):
        source_payload = {}
    if not isinstance(validation_errors, list):
        validation_errors = []
    return {
        "item_id": int(row["item_id"]),
        "run_id": int(row["run_id"]),
        "domain_code": row["domain_code"],
        "source_kind": row["source_kind"],
        "source_record_id": row.get("source_record_id"),
        "import_batch_id": row.get("import_batch_id"),
        "import_row_id": row.get("import_row_id"),
        "record_kind": row.get("record_kind"),
        "target_table_name": row.get("target_table_name"),
        "target_record_id": row.get("target_record_id"),
        "item_status": row["item_status"],
        "draft_payload": _json_safe(draft_payload),
        "source_payload": _json_safe(source_payload),
        "validation_errors": _json_safe(validation_errors),
        "created_at": _json_safe(row.get("created_at")),
        "committed_at": _json_safe(row.get("committed_at")),
        "voided_at": _json_safe(row.get("voided_at")),
        "void_reason": row.get("void_reason"),
    }


def list_migration_domains(conn: Optional[Connection] = None) -> dict[str, Any]:
    _require_available()
    if conn is not None:
        return _list_migration_domains_tx(conn)
    with engine.connect() as owned_conn:
        return _list_migration_domains_tx(owned_conn)


def _list_migration_domains_tx(conn: Connection) -> dict[str, Any]:
    rows = conn.execute(
        text(
            """
            SELECT
                domain_code,
                display_name,
                description,
                is_enabled,
                target_table_names,
                control_list_columns,
                created_at,
                updated_at
            FROM public.personnel_migration_domains
            ORDER BY domain_code ASC
            """
        )
    ).mappings().all()
    return {"items": [_serialize_domain_row(dict(row)) for row in rows]}


def get_migration_run(conn: Connection, *, run_id: int) -> dict[str, Any]:
    _require_available()
    run_row = conn.execute(
        text(
            """
            SELECT
                run_id,
                domain_code,
                employee_context_id,
                person_id,
                run_status,
                started_at,
                committed_at,
                voided_at,
                started_by,
                committed_by,
                voided_by,
                void_reason,
                metadata
            FROM public.personnel_migration_runs
            WHERE run_id = :run_id
            """
        ),
        {"run_id": int(run_id)},
    ).mappings().first()
    if run_row is None:
        raise PersonnelMigrationNotFoundError(f"Migration run {run_id} not found.")

    item_rows = conn.execute(
        text(
            """
            SELECT
                item_id,
                run_id,
                domain_code,
                source_kind,
                source_record_id,
                import_batch_id,
                import_row_id,
                record_kind,
                target_table_name,
                target_record_id,
                item_status,
                draft_payload,
                source_payload,
                validation_errors,
                created_at,
                committed_at,
                voided_at,
                void_reason
            FROM public.personnel_migration_items
            WHERE run_id = :run_id
            ORDER BY item_id ASC
            """
        ),
        {"run_id": int(run_id)},
    ).mappings().all()

    run = _serialize_run_row(dict(run_row))
    run["items"] = [_serialize_item_row(dict(row)) for row in item_rows]
    return run


def get_migration_run_tx(*, run_id: int) -> dict[str, Any]:
    with engine.connect() as conn:
        return get_migration_run(conn, run_id=run_id)
