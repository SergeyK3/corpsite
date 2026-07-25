# tests/personnel_lk/conftest.py
"""Shared fixtures for personnel LK registry tests."""
from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.personnel_applications.domain.status import VACANCY_CHECK_CONFIRMED_VISUALLY
from tests.conftest import get_columns, insert_returning_id, table_exists
from tests.personnel_applications.conftest import insert_person_with_iin, materialize_envelope
from tests.ppr.conftest import cleanup_person_graph, insert_employee, ppr_db_available


def require_personnel_lk_schema() -> None:
    if not ppr_db_available():
        pytest.skip("PostgreSQL not available")
    with engine.begin() as conn:
        if not table_exists(conn, "persons"):
            pytest.skip("persons table missing — run: alembic upgrade head")
        if not table_exists(conn, "personnel_applications"):
            pytest.skip("personnel_applications missing — run: alembic upgrade head")


def unique_iin(prefix: str = "8") -> str:
    return f"{prefix}{uuid4().int % 10_000_000_000_000:011d}"[:12]


def seed_user_id(conn) -> int:
    row = conn.execute(text("SELECT user_id FROM public.users LIMIT 1")).mappings().first()
    assert row is not None
    return int(row["user_id"])


def load_org_fixture(conn) -> dict[str, int | None]:
    unit = conn.execute(
        text(
            """
            SELECT unit_id, group_id
            FROM public.org_units
            WHERE unit_id IS NOT NULL
            ORDER BY unit_id
            LIMIT 1
            """
        )
    ).mappings().first()
    pos = conn.execute(
        text("SELECT position_id FROM public.positions ORDER BY position_id LIMIT 1")
    ).mappings().first()
    if unit is None:
        return {"org_unit_id": None, "org_group_id": None, "position_id": None}
    return {
        "org_unit_id": int(unit["unit_id"]),
        "org_group_id": int(unit["group_id"]) if unit.get("group_id") is not None else None,
        "position_id": int(pos["position_id"]) if pos else None,
    }


def insert_application(
    conn,
    *,
    person_id: int,
    registered_by_user_id: int,
    status: str = "registered",
    application_received_at: date | None = None,
    intended_org_group_id: int | None = None,
    intended_org_unit_id: int | None = None,
    intended_position_id: int | None = None,
    intended_employment_rate: float | None = None,
) -> int:
    received = application_received_at or date(2026, 7, 17)
    now = datetime.now(timezone.utc)
    cols = get_columns(conn, "personnel_applications")
    values: dict = {
        "person_id": person_id,
        "status": status,
        "application_received_at": received,
        "application_source": "paper",
        "vacancy_check_status": VACANCY_CHECK_CONFIRMED_VISUALLY,
        "registered_at": now,
        "registered_by_user_id": registered_by_user_id,
        "created_at": now,
        "updated_at": now,
    }
    if intended_org_group_id is not None and "intended_org_group_id" in cols:
        values["intended_org_group_id"] = intended_org_group_id
    if intended_org_unit_id is not None and "intended_org_unit_id" in cols:
        values["intended_org_unit_id"] = intended_org_unit_id
    if intended_position_id is not None and "intended_position_id" in cols:
        values["intended_position_id"] = intended_position_id
    if intended_employment_rate is not None and "intended_employment_rate" in cols:
        values["intended_employment_rate"] = intended_employment_rate
    return insert_returning_id(
        conn,
        table="personnel_applications",
        id_col="application_id",
        values=values,
    )


def set_employee_assignment(
    conn,
    *,
    employee_id: int,
    org_unit_id: int | None = None,
    position_id: int | None = None,
    employment_rate: float | None = None,
    is_active: bool = True,
) -> None:
    cols = get_columns(conn, "employees")
    sets: list[str] = []
    params: dict = {"employee_id": employee_id}
    if org_unit_id is not None and "org_unit_id" in cols:
        sets.append("org_unit_id = :org_unit_id")
        params["org_unit_id"] = org_unit_id
    if position_id is not None and "position_id" in cols:
        sets.append("position_id = :position_id")
        params["position_id"] = position_id
    if employment_rate is not None and "employment_rate" in cols:
        sets.append("employment_rate = :employment_rate")
        params["employment_rate"] = employment_rate
    if "is_active" in cols:
        sets.append("is_active = :is_active")
        params["is_active"] = is_active
    if "operational_status" in cols:
        sets.append("operational_status = :operational_status")
        params["operational_status"] = "active" if is_active else "terminated"
    if not sets:
        return
    conn.execute(
        text(f"UPDATE public.employees SET {', '.join(sets)} WHERE employee_id = :employee_id"),
        params,
    )


@pytest.fixture
def lk_env():
    require_personnel_lk_schema()
    yield
