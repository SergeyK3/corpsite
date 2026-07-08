"""Read-side queries for personnel_record_events (PMF-3B)."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.engine import engine
from app.services.personnel_migration_commit_service import personnel_migration_available
from app.services.personnel_migration_query_service import get_migration_run
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


def _serialize_event_row(row: dict[str, Any]) -> dict[str, Any]:
    payload = row.get("event_payload") or {}
    if not isinstance(payload, dict):
        payload = {}
    return {
        "event_id": int(row["event_id"]),
        "person_id": int(row["person_id"]),
        "employee_context_id": row.get("employee_context_id"),
        "domain_code": row["domain_code"],
        "record_table_name": row["record_table_name"],
        "record_id": int(row["record_id"]),
        "event_type": row["event_type"],
        "event_at": _json_safe(row.get("event_at")),
        "actor_id": row.get("actor_id"),
        "event_payload": _json_safe(payload),
        "migration_run_id": row.get("migration_run_id"),
        "migration_item_id": row.get("migration_item_id"),
    }


def _resolve_person_id_from_employee(conn: Connection, employee_context_id: int) -> int:
    person_id = conn.execute(
        text(
            """
            SELECT person_id
            FROM public.employees
            WHERE employee_id = :employee_id
            """
        ),
        {"employee_id": int(employee_context_id)},
    ).scalar_one_or_none()
    if person_id is None:
        raise PersonnelMigrationNotFoundError(
            f"Employee {employee_context_id} not found or has no person_id."
        )
    return int(person_id)


def _validate_list_filters(
    *,
    person_id: Optional[int],
    employee_context_id: Optional[int],
    migration_run_id: Optional[int],
    record_id: Optional[int],
) -> None:
    if any(
        value is not None
        for value in (person_id, employee_context_id, migration_run_id, record_id)
    ):
        return
    raise PersonnelMigrationValidationError(
        "At least one filter is required: person_id, employee_context_id, "
        "migration_run_id, or record_id."
    )


def _build_event_filters(
    conn: Connection,
    *,
    person_id: Optional[int],
    employee_context_id: Optional[int],
    domain_code: Optional[str],
    record_table_name: Optional[str],
    record_id: Optional[int],
    event_type: Optional[str],
    migration_run_id: Optional[int],
) -> tuple[str, dict[str, Any]]:
    clauses: list[str] = []
    params: dict[str, Any] = {}

    resolved_person_id = person_id
    if resolved_person_id is None and employee_context_id is not None:
        resolved_person_id = _resolve_person_id_from_employee(conn, employee_context_id)

    if resolved_person_id is not None:
        clauses.append("person_id = :person_id")
        params["person_id"] = int(resolved_person_id)
    if domain_code is not None:
        clauses.append("domain_code = :domain_code")
        params["domain_code"] = domain_code
    if record_table_name is not None:
        clauses.append("record_table_name = :record_table_name")
        params["record_table_name"] = record_table_name
    if record_id is not None:
        clauses.append("record_id = :record_id")
        params["record_id"] = int(record_id)
    if event_type is not None:
        clauses.append("event_type = :event_type")
        params["event_type"] = event_type
    if migration_run_id is not None:
        clauses.append("migration_run_id = :migration_run_id")
        params["migration_run_id"] = int(migration_run_id)

    where_sql = " AND ".join(clauses) if clauses else "TRUE"
    return where_sql, params


def list_record_events(
    conn: Connection,
    *,
    person_id: Optional[int] = None,
    employee_context_id: Optional[int] = None,
    domain_code: Optional[str] = None,
    record_table_name: Optional[str] = None,
    record_id: Optional[int] = None,
    event_type: Optional[str] = None,
    migration_run_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    _require_available()
    _validate_list_filters(
        person_id=person_id,
        employee_context_id=employee_context_id,
        migration_run_id=migration_run_id,
        record_id=record_id,
    )

    safe_limit = max(1, min(int(limit), 200))
    safe_offset = max(0, int(offset))

    where_sql, params = _build_event_filters(
        conn,
        person_id=person_id,
        employee_context_id=employee_context_id,
        domain_code=domain_code,
        record_table_name=record_table_name,
        record_id=record_id,
        event_type=event_type,
        migration_run_id=migration_run_id,
    )
    params["limit"] = safe_limit
    params["offset"] = safe_offset

    total = int(
        conn.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM public.personnel_record_events
                WHERE {where_sql}
                """
            ),
            params,
        ).scalar_one()
    )

    rows = conn.execute(
        text(
            f"""
            SELECT
                event_id,
                person_id,
                employee_context_id,
                domain_code,
                record_table_name,
                record_id,
                event_type,
                event_at,
                actor_id,
                event_payload,
                migration_run_id,
                migration_item_id
            FROM public.personnel_record_events
            WHERE {where_sql}
            ORDER BY event_id DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()

    return {
        "items": [_serialize_event_row(dict(row)) for row in rows],
        "total": total,
        "limit": safe_limit,
        "offset": safe_offset,
    }


def list_record_events_tx(
    *,
    person_id: Optional[int] = None,
    employee_context_id: Optional[int] = None,
    domain_code: Optional[str] = None,
    record_table_name: Optional[str] = None,
    record_id: Optional[int] = None,
    event_type: Optional[str] = None,
    migration_run_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    with engine.connect() as conn:
        return list_record_events(
            conn,
            person_id=person_id,
            employee_context_id=employee_context_id,
            domain_code=domain_code,
            record_table_name=record_table_name,
            record_id=record_id,
            event_type=event_type,
            migration_run_id=migration_run_id,
            limit=limit,
            offset=offset,
        )


def get_record_event(conn: Connection, *, event_id: int) -> dict[str, Any]:
    _require_available()
    row = conn.execute(
        text(
            """
            SELECT
                event_id,
                person_id,
                employee_context_id,
                domain_code,
                record_table_name,
                record_id,
                event_type,
                event_at,
                actor_id,
                event_payload,
                migration_run_id,
                migration_item_id
            FROM public.personnel_record_events
            WHERE event_id = :event_id
            """
        ),
        {"event_id": int(event_id)},
    ).mappings().first()
    if row is None:
        raise PersonnelMigrationNotFoundError(f"Record event {event_id} not found.")
    return _serialize_event_row(dict(row))


def get_record_event_tx(*, event_id: int) -> dict[str, Any]:
    with engine.connect() as conn:
        return get_record_event(conn, event_id=event_id)


def list_record_events_for_run_tx(
    *,
    run_id: int,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    with engine.connect() as conn:
        get_migration_run(conn, run_id=run_id)
        return list_record_events(
            conn,
            migration_run_id=run_id,
            limit=limit,
            offset=offset,
        )
