"""HIRE apply support for applicants without a pre-existing Employee row."""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.models.personnel_orders import ORDER_TYPE_HIRE
from app.ppr.domain.models import HR_RELATIONSHIP_CANDIDATE
from app.services.personnel_orders_command_service import PersonnelOrderValidationError


def parse_person_id_from_payload(payload: Dict[str, Any] | None) -> Optional[int]:
    if not payload:
        return None
    raw = payload.get("person_id")
    if raw is None:
        return None
    try:
        person_id = int(raw)
    except (TypeError, ValueError) as exc:
        raise PersonnelOrderValidationError("HIRE payload person_id must be a positive integer.") from exc
    if person_id <= 0:
        raise PersonnelOrderValidationError("HIRE payload person_id must be a positive integer.")
    return person_id


def _table_exists(conn: Connection, table_name: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = :table_name
            LIMIT 1
            """
        ),
        {"table_name": table_name},
    ).first()
    return row is not None


def _employee_columns(conn: Connection) -> set[str]:
    rows = conn.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'employees'
            """
        )
    ).fetchall()
    return {str(row[0]) for row in rows}


def _load_person_row(conn: Connection, person_id: int) -> Dict[str, Any]:
    row = conn.execute(
        text(
            """
            SELECT person_id, full_name, person_status
            FROM public.persons
            WHERE person_id = :person_id
            LIMIT 1
            """
        ),
        {"person_id": int(person_id)},
    ).mappings().first()
    if row is None:
        raise PersonnelOrderValidationError(f"Person {person_id} not found.")
    return dict(row)


def _load_ppr_context(conn: Connection, person_id: int) -> Optional[str]:
    if not _table_exists(conn, "personnel_record_metadata"):
        return None
    row = conn.execute(
        text(
            """
            SELECT hr_relationship_context
            FROM public.personnel_record_metadata
            WHERE person_id = :person_id
            LIMIT 1
            """
        ),
        {"person_id": int(person_id)},
    ).mappings().first()
    if row is None:
        return None
    return str(row.get("hr_relationship_context") or "").strip() or None


def _find_active_employee_for_person(conn: Connection, person_id: int) -> Optional[int]:
    cols = _employee_columns(conn)
    if "person_id" not in cols:
        return None
    row = conn.execute(
        text(
            """
            SELECT employee_id
            FROM public.employees
            WHERE person_id = :person_id
              AND COALESCE(is_active, TRUE) = TRUE
            ORDER BY employee_id ASC
            LIMIT 1
            """
        ),
        {"person_id": int(person_id)},
    ).mappings().first()
    if row is None:
        return None
    return int(row["employee_id"])


def validate_hire_person_candidate(conn: Connection, person_id: int) -> Dict[str, Any]:
    person = _load_person_row(conn, person_id)
    if str(person.get("person_status") or "").strip().lower() not in {"", "active"}:
        raise PersonnelOrderValidationError(
            f"Person {person_id} is not active and cannot be hired via HIRE order."
        )

    active_employee_id = _find_active_employee_for_person(conn, person_id)
    if active_employee_id is not None:
        raise PersonnelOrderValidationError(
            f"Person {person_id} already has active employee_id={active_employee_id}."
        )

    hr_context = _load_ppr_context(conn, person_id)
    if hr_context is not None and hr_context != HR_RELATIONSHIP_CANDIDATE:
        raise PersonnelOrderValidationError(
            f"Person {person_id} hr_relationship_context={hr_context!r} is not CANDIDATE."
        )
    return person


def validate_hire_item_identity(
    conn: Connection,
    *,
    item_type_code: str,
    employee_id: Optional[int],
    payload: Optional[Dict[str, Any]],
) -> None:
    normalized = str(item_type_code or "").strip().upper()
    if normalized != ORDER_TYPE_HIRE:
        if employee_id is None:
            raise PersonnelOrderValidationError(
                f"Order item type {item_type_code} requires employee_id."
            )
        return

    if employee_id is not None:
        return

    person_id = parse_person_id_from_payload(payload or {})
    if person_id is None:
        raise PersonnelOrderValidationError(
            "HIRE order item requires employee_id or payload.person_id."
        )
    validate_hire_person_candidate(conn, person_id)


def _find_inactive_employee_for_person(conn: Connection, person_id: int) -> Optional[int]:
    cols = _employee_columns(conn)
    if "person_id" not in cols:
        return None
    row = conn.execute(
        text(
            """
            SELECT employee_id
            FROM public.employees
            WHERE person_id = :person_id
            ORDER BY employee_id ASC
            LIMIT 1
            """
        ),
        {"person_id": int(person_id)},
    ).mappings().first()
    if row is None:
        return None
    return int(row["employee_id"])


def create_employee_for_hire(
    conn: Connection,
    *,
    person_id: int,
    full_name: str,
    created_by: int,
) -> int:
    """Insert a regular employees row before HIRE apply (inactive until _apply_hire activates it)."""
    cols = _employee_columns(conn)
    normalized_name = " ".join((full_name or "").split()).strip() or f"Person #{person_id}"

    values: Dict[str, Any] = {
        "full_name": normalized_name,
        "is_active": False,
    }
    if "person_id" in cols:
        values["person_id"] = int(person_id)
    if "employment_rate" in cols:
        values["employment_rate"] = 1.0
    if "operational_status" in cols:
        values["operational_status"] = "draft"
    if "enrollment_source" in cols:
        values["enrollment_source"] = "enrollment"
    if "enrolled_by_user_id" in cols:
        values["enrolled_by_user_id"] = int(created_by)

    insert_cols = [key for key in values if key in cols]
    if not insert_cols:
        raise PersonnelOrderValidationError("employees table has no writable columns for hire bootstrap.")

    col_sql = ", ".join(insert_cols)
    bind_sql = ", ".join(f":{key}" for key in insert_cols)
    row = conn.execute(
        text(
            f"""
            INSERT INTO public.employees ({col_sql})
            VALUES ({bind_sql})
            RETURNING employee_id
            """
        ),
        {key: values[key] for key in insert_cols},
    ).mappings().first()
    if row is None or row.get("employee_id") is None:
        raise PersonnelOrderValidationError("Failed to create employee for HIRE apply.")
    return int(row["employee_id"])


def ensure_person_assignment_for_hire(
    conn: Connection,
    *,
    person_id: int,
    org_unit_id: int,
    position_id: int,
    employment_rate: float,
    effective_date: date,
    order_id: int,
    item_id: int,
) -> Optional[int]:
    if not _table_exists(conn, "person_assignments"):
        return None

    assignment_key = f"hire:order:{int(order_id)}:item:{int(item_id)}"
    existing = conn.execute(
        text(
            """
            SELECT assignment_id
            FROM public.person_assignments
            WHERE person_id = :person_id
              AND assignment_key = :assignment_key
            LIMIT 1
            """
        ),
        {"person_id": int(person_id), "assignment_key": assignment_key},
    ).mappings().first()
    if existing is not None:
        return int(existing["assignment_id"])

    row = conn.execute(
        text(
            """
            INSERT INTO public.person_assignments (
                person_id,
                org_unit_id,
                position_id,
                employment_type,
                rate,
                start_date,
                active_flag,
                is_primary,
                lifecycle_status,
                assignment_key,
                source
            )
            VALUES (
                :person_id,
                :org_unit_id,
                :position_id,
                'primary',
                :rate,
                :start_date,
                TRUE,
                TRUE,
                'active',
                :assignment_key,
                'manual'
            )
            RETURNING assignment_id
            """
        ),
        {
            "person_id": int(person_id),
            "org_unit_id": int(org_unit_id),
            "position_id": int(position_id),
            "rate": float(employment_rate),
            "start_date": effective_date,
            "assignment_key": assignment_key,
        },
    ).mappings().first()
    if row is None:
        return None
    return int(row["assignment_id"])


def link_order_item_employee(conn: Connection, *, item_id: int, employee_id: int) -> None:
    conn.execute(
        text(
            """
            UPDATE public.personnel_order_items
            SET employee_id = :employee_id
            WHERE item_id = :item_id
            """
        ),
        {"item_id": int(item_id), "employee_id": int(employee_id)},
    )


def resolve_hire_employee_id_for_apply(
    conn: Connection,
    *,
    item: Dict[str, Any],
    created_by: int,
) -> tuple[int, bool, Optional[int]]:
    """Return (employee_id, created_new, person_id_if_from_payload)."""
    item_type = str(item.get("item_type_code") or "").strip().upper()
    if item_type != ORDER_TYPE_HIRE:
        employee_raw = item.get("employee_id")
        if employee_raw is None:
            raise PersonnelOrderValidationError(
                f"Order item {item['item_id']} requires employee_id."
            )
        return int(employee_raw), False, None

    employee_raw = item.get("employee_id")
    if employee_raw is not None:
        return int(employee_raw), False, parse_person_id_from_payload(item.get("payload") or {})

    payload = item.get("payload") or {}
    if isinstance(payload, str):
        payload = {}
    person_id = parse_person_id_from_payload(payload if isinstance(payload, dict) else {})
    if person_id is None:
        raise PersonnelOrderValidationError(
            f"Order item {item['item_id']} HIRE requires employee_id or payload.person_id."
        )

    person = validate_hire_person_candidate(conn, person_id)
    existing = _find_inactive_employee_for_person(conn, person_id)
    if existing is not None:
        link_order_item_employee(conn, item_id=int(item["item_id"]), employee_id=existing)
        item["employee_id"] = existing
        return existing, False, person_id

    employee_id = create_employee_for_hire(
        conn,
        person_id=person_id,
        full_name=str(person.get("full_name") or ""),
        created_by=created_by,
    )
    link_order_item_employee(conn, item_id=int(item["item_id"]), employee_id=employee_id)
    item["employee_id"] = employee_id
    return employee_id, True, person_id
