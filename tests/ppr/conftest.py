# tests/ppr/conftest.py
"""Shared PostgreSQL fixtures for PPR repository contract tests."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import get_columns, insert_returning_id, table_exists


def ppr_db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def require_ppr_schema() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "persons"):
            pytest.skip("persons table missing — run: alembic upgrade head")


def insert_person(
    conn,
    *,
    full_name: str,
    person_status: str = "active",
    merged_into_person_id: int | None = None,
    prefix: str = "ppr",
) -> int:
    suffix = uuid4().hex[:12]
    match_key = f"{prefix}:{suffix}"
    cols = get_columns(conn, "persons")
    values: dict[str, Any] = {"full_name": full_name}
    if "match_key" in cols:
        values["match_key"] = match_key
    if "source" in cols:
        values["source"] = "manual"
    if "person_status" in cols:
        values["person_status"] = person_status
    if merged_into_person_id is not None and "merged_into_person_id" in cols:
        values["merged_into_person_id"] = merged_into_person_id
    return insert_returning_id(
        conn,
        table="persons",
        id_col="person_id",
        values=values,
    )


def insert_employee(
    conn,
    *,
    full_name: str,
    person_id: int | None = None,
    is_active: bool = True,
    operational_status: str | None = None,
) -> int:
    cols = get_columns(conn, "employees")
    values: dict[str, Any] = {"full_name": full_name, "is_active": is_active}
    if person_id is not None and "person_id" in cols:
        values["person_id"] = person_id
    if "employment_rate" in cols:
        values["employment_rate"] = 1.00
    if operational_status is not None and "operational_status" in cols:
        values["operational_status"] = operational_status
    elif "operational_status" in cols:
        values["operational_status"] = "terminated" if not is_active else "active"
    return insert_returning_id(
        conn,
        table="employees",
        id_col="employee_id",
        values=values,
    )


def cleanup_person_graph(conn, *, person_ids: list[int], employee_ids: list[int]) -> None:
    if person_ids:
        if table_exists(conn, "person_assignments"):
            conn.execute(
                text("DELETE FROM public.person_assignments WHERE person_id = ANY(:ids)"),
                {"ids": person_ids},
            )
        conn.execute(
            text("DELETE FROM public.ppr_command_executions WHERE person_id = ANY(:ids)"),
            {"ids": person_ids},
        )
        conn.execute(
            text("DELETE FROM public.personnel_record_metadata WHERE person_id = ANY(:ids)"),
            {"ids": person_ids},
        )
        conn.execute(
            text("DELETE FROM public.personnel_record_events WHERE person_id = ANY(:ids)"),
            {"ids": person_ids},
        )
        conn.execute(
            text("DELETE FROM public.person_education WHERE person_id = ANY(:ids)"),
            {"ids": person_ids},
        )
        conn.execute(
            text("DELETE FROM public.person_training WHERE person_id = ANY(:ids)"),
            {"ids": person_ids},
        )
        conn.execute(
            text("DELETE FROM public.person_relatives WHERE person_id = ANY(:ids)"),
            {"ids": person_ids},
        )
        conn.execute(
            text("DELETE FROM public.person_external_employment WHERE person_id = ANY(:ids)"),
            {"ids": person_ids},
        )
        if table_exists(conn, "person_military_service"):
            conn.execute(
                text("DELETE FROM public.person_military_service WHERE person_id = ANY(:ids)"),
                {"ids": person_ids},
            )
    if employee_ids:
        if table_exists(conn, "employee_events"):
            conn.execute(
                text("DELETE FROM public.employee_events WHERE employee_id = ANY(:ids)"),
                {"ids": employee_ids},
            )
        conn.execute(
            text("DELETE FROM public.employees WHERE employee_id = ANY(:ids)"),
            {"ids": employee_ids},
        )
    if person_ids:
        conn.execute(
            text("DELETE FROM public.persons WHERE person_id = ANY(:ids)"),
            {"ids": person_ids},
        )
