"""Reference existence checks before SQL mutations."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection


def user_exists(conn: Connection, user_id: int) -> bool:
    row = conn.execute(
        text("SELECT 1 FROM public.users WHERE user_id = :user_id LIMIT 1"),
        {"user_id": int(user_id)},
    ).first()
    return row is not None


def org_unit_exists(conn: Connection, org_unit_id: int) -> bool:
    row = conn.execute(
        text("SELECT 1 FROM public.org_units WHERE unit_id = :unit_id LIMIT 1"),
        {"unit_id": int(org_unit_id)},
    ).first()
    return row is not None


def person_exists(conn: Connection, person_id: int) -> bool:
    row = conn.execute(
        text("SELECT 1 FROM public.persons WHERE person_id = :person_id LIMIT 1"),
        {"person_id": int(person_id)},
    ).first()
    return row is not None


def employee_exists(conn: Connection, employee_id: int) -> bool:
    row = conn.execute(
        text("SELECT 1 FROM public.employees WHERE employee_id = :employee_id LIMIT 1"),
        {"employee_id": int(employee_id)},
    ).first()
    return row is not None


def position_exists(conn: Connection, position_id: int) -> bool:
    row = conn.execute(
        text("SELECT 1 FROM public.positions WHERE position_id = :position_id LIMIT 1"),
        {"position_id": int(position_id)},
    ).first()
    return row is not None
