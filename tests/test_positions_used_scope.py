"""Focused coverage for active personnel positions in the journal scope selector."""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.directory.positions_routes import list_positions_crud
from tests.conftest import insert_returning_id


@pytest.fixture
def used_scope_rows():
    suffix = uuid4().hex[:8]
    group_id = unit_id = active_position_id = inactive_position_id = None
    active_employee_id = inactive_employee_id = None
    try:
        with engine.begin() as conn:
            group_id = insert_returning_id(
                conn,
                table="deps_group",
                id_col="group_id",
                values={"group_name": f"pytest used scope group {suffix}"},
            )
            unit_id = insert_returning_id(
                conn,
                table="org_units",
                id_col="unit_id",
                values={
                    "name": f"pytest used scope unit {suffix}",
                    "code": f"pytest_used_scope_{suffix}",
                    "group_id": group_id,
                    "is_active": True,
                },
            )
            active_position_id = insert_returning_id(
                conn,
                table="positions",
                id_col="position_id",
                values={"name": f"pytest used active {suffix}", "category": "admin"},
            )
            inactive_position_id = insert_returning_id(
                conn,
                table="positions",
                id_col="position_id",
                values={"name": f"pytest used inactive {suffix}", "category": "admin"},
            )
            conn.execute(
                text(
                    "INSERT INTO public.org_unit_allowed_positions "
                    "(org_unit_id, position_id, is_active) "
                    "VALUES (:unit_id, :position_id, TRUE), (:unit_id, :inactive_position_id, FALSE)"
                ),
                {
                    "unit_id": unit_id,
                    "position_id": active_position_id,
                    "inactive_position_id": inactive_position_id,
                },
            )
            active_employee_id = insert_returning_id(
                conn,
                table="employees",
                id_col="employee_id",
                values={
                    "full_name": f"pytest used active employee {suffix}",
                    "org_unit_id": unit_id,
                    "position_id": active_position_id,
                    "is_active": True,
                },
            )
            inactive_employee_id = insert_returning_id(
                conn,
                table="employees",
                id_col="employee_id",
                values={
                    "full_name": f"pytest used inactive employee {suffix}",
                    "org_unit_id": unit_id,
                    "position_id": inactive_position_id,
                    "is_active": False,
                },
            )
        yield {
            "unit_id": unit_id,
            "active_position_id": active_position_id,
            "inactive_position_id": inactive_position_id,
        }
    finally:
        with engine.begin() as conn:
            if active_employee_id is not None or inactive_employee_id is not None:
                conn.execute(
                    text("DELETE FROM public.employees WHERE employee_id = ANY(:ids)"),
                    {"ids": [x for x in (active_employee_id, inactive_employee_id) if x is not None]},
                )
            if active_position_id is not None or inactive_position_id is not None:
                conn.execute(
                    text("DELETE FROM public.org_unit_allowed_positions WHERE position_id = ANY(:ids)"),
                    {"ids": [x for x in (active_position_id, inactive_position_id) if x is not None]},
                )
                conn.execute(
                    text("DELETE FROM public.positions WHERE position_id = ANY(:ids)"),
                    {"ids": [x for x in (active_position_id, inactive_position_id) if x is not None]},
                )
            if unit_id is not None:
                conn.execute(text("DELETE FROM public.org_units WHERE unit_id = :unit_id"), {"unit_id": unit_id})
            if group_id is not None:
                conn.execute(text("DELETE FROM public.deps_group WHERE group_id = :group_id"), {"group_id": group_id})


def test_used_scope_returns_only_active_employee_positions(used_scope_rows):
    result = list_positions_crud(
        q=None,
        category=None,
        org_group_id=None,
        org_unit_id=used_scope_rows["unit_id"],
        scope="used",
        delete_status=None,
        limit=100,
        offset=0,
        user={"user_id": 1, "role_id": 2},
    )

    position_ids = {item["position_id"] for item in result["items"]}
    assert used_scope_rows["active_position_id"] in position_ids
    assert used_scope_rows["inactive_position_id"] not in position_ids
