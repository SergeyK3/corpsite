"""Manual type override for one current primary personnel assignment."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import text


def set_current_assignment_manual_type(
    conn, *, employee_id: int, assignment_id: int, manual_type_code: int | None,
) -> None:
    # Serialize with appointment changes, which also lock the employee row.
    employee = conn.execute(text("""
        SELECT person_id FROM public.employees
        WHERE employee_id=:employee_id FOR UPDATE
    """), {"employee_id": employee_id}).mappings().first()
    if employee is None or employee["person_id"] is None:
        raise HTTPException(status_code=404, detail="Employee not found.")

    current = conn.execute(text("""
        SELECT assignment_id FROM public.person_assignments
        WHERE person_id=:person_id AND active_flag IS TRUE
          AND is_primary IS TRUE AND lifecycle_status='active'
          AND start_date<=CURRENT_DATE
          AND (end_date IS NULL OR end_date>=CURRENT_DATE)
        FOR UPDATE
    """), {"person_id": employee["person_id"]}).scalars().all()
    if len(current) != 1 or int(current[0]) != assignment_id:
        raise HTTPException(status_code=409, detail="Current primary assignment changed. Reload the card.")

    if manual_type_code is not None:
        valid = conn.execute(text("""
            SELECT 1 FROM public.position_types WHERE code=:code
        """), {"code": manual_type_code}).first()
        if valid is None:
            raise HTTPException(status_code=422, detail="Unknown position type.")

    conn.execute(text("""
        UPDATE public.person_assignments
        SET manual_type_code=:code, updated_at=now()
        WHERE assignment_id=:assignment_id
    """), {"code": manual_type_code, "assignment_id": assignment_id})
