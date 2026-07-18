# tests/test_tasks_list_position_filter.py
from __future__ import annotations

from typing import Any, Dict, Optional

from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.tasks_service import SYSTEM_ADMIN_ROLE_ID
from tests.conftest import (
    auth_headers,
    cleanup_task,
    create_role,
    create_task,
    create_user,
    get_columns,
    insert_returning_id,
    table_exists,
)


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _list_tasks(client, user_id: int, **params):
    return client.get("/tasks", params=params, headers=auth_headers(user_id))


def _admin_user_id(conn) -> int:
    row = conn.execute(
        text(
            """
            SELECT user_id
            FROM public.users
            WHERE role_id = :role_id
              AND COALESCE(is_active, TRUE) = TRUE
            LIMIT 1
            """
        ),
        {"role_id": int(SYSTEM_ADMIN_ROLE_ID)},
    ).first()
    if row:
        return int(row[0])
    pytest.skip("system admin user not available")


def _create_position(conn, name: str) -> int:
    if not table_exists(conn, "positions"):
        pytest.skip("positions table not available")
    return insert_returning_id(
        conn,
        table="positions",
        id_col="position_id",
        values={"name": name},
    )


def _link_user_employee(
    conn,
    *,
    user_id: int,
    position_id: int,
    org_unit_id: Optional[int],
) -> None:
    user_cols = get_columns(conn, "users")
    if "employee_id" not in user_cols:
        pytest.skip("users.employee_id not available")

    emp_cols = get_columns(conn, "employees")
    values: Dict[str, Any] = {
        "full_name": f"Pytest Employee {user_id}",
        "position_id": int(position_id),
        "is_active": True,
    }
    if "org_unit_id" in emp_cols and org_unit_id is not None:
        values["org_unit_id"] = int(org_unit_id)

    employee_id = insert_returning_id(
        conn,
        table="employees",
        id_col="employee_id",
        values=values,
    )
    conn.execute(
        text(
            """
            UPDATE public.users
            SET employee_id = :employee_id
            WHERE user_id = :user_id
            """
        ),
        {"employee_id": int(employee_id), "user_id": int(user_id)},
    )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_tasks_filters_by_position_id_within_team_scope(client, seed):
    matched_task_id: int | None = None
    other_task_id: int | None = None
    alt_role_id: int | None = None
    alt_user_id: int | None = None
    matched_position_id: int | None = None
    other_position_id: int | None = None
    suffix = uuid4().hex[:8]

    try:
        with engine.begin() as conn:
            admin_user_id = _admin_user_id(conn)
            matched_position_id = _create_position(conn, f"Pytest Position Matched {suffix}")
            other_position_id = _create_position(conn, f"Pytest Position Other {suffix}")

            alt_role_id = create_role(conn, f"pytest_position_filter_alt_{suffix}")
            alt_user_id = create_user(
                conn,
                full_name=f"Pytest Position Alt Executor {suffix}",
                role_id=alt_role_id,
                unit_id=seed["unit_id"],
            )
            _link_user_employee(
                conn,
                user_id=int(seed["executor_user_id"]),
                position_id=matched_position_id,
                org_unit_id=seed.get("unit_id"),
            )
            _link_user_employee(
                conn,
                user_id=alt_user_id,
                position_id=other_position_id,
                org_unit_id=seed.get("unit_id"),
            )

        matched_task_id = create_task(
            period_id=seed["period_id"],
            title=f"Pytest position filter matched {suffix}",
            initiator_user_id=seed["initiator_user_id"],
            executor_role_id=seed["executor_role_id"],
            assignment_scope=seed["assignment_scope"],
            status_code="IN_PROGRESS",
            unit_id=seed.get("unit_id"),
        )
        other_task_id = create_task(
            period_id=seed["period_id"],
            title=f"Pytest position filter other {suffix}",
            initiator_user_id=seed["initiator_user_id"],
            executor_role_id=alt_role_id,
            assignment_scope=seed["assignment_scope"],
            status_code="IN_PROGRESS",
            unit_id=seed.get("unit_id"),
        )

        resp = _list_tasks(
            client,
            admin_user_id,
            scope="team",
            position_id=matched_position_id,
            limit=200,
            offset=0,
        )
        assert resp.status_code == 200, resp.text
        items = resp.json().get("items") or []
        ids = {int(x["task_id"]) for x in items}

        assert matched_task_id in ids
        assert other_task_id not in ids
    finally:
        if matched_task_id is not None:
            cleanup_task(matched_task_id)
        if other_task_id is not None:
            cleanup_task(other_task_id)
        with engine.begin() as conn:
            if alt_user_id is not None:
                conn.execute(
                    text("UPDATE public.users SET employee_id = NULL WHERE user_id = :uid"),
                    {"uid": int(alt_user_id)},
                )
                conn.execute(text("DELETE FROM public.users WHERE user_id = :uid"), {"uid": int(alt_user_id)})
            if alt_role_id is not None:
                conn.execute(text("DELETE FROM public.roles WHERE role_id = :rid"), {"rid": int(alt_role_id)})
            for position_id in (matched_position_id, other_position_id):
                if position_id is None:
                    continue
                conn.execute(
                    text("UPDATE public.users SET employee_id = NULL WHERE employee_id IN (SELECT employee_id FROM public.employees WHERE position_id = :pid)"),
                    {"pid": int(position_id)},
                )
                conn.execute(text("DELETE FROM public.employees WHERE position_id = :pid"), {"pid": int(position_id)})
                conn.execute(text("DELETE FROM public.positions WHERE position_id = :pid"), {"pid": int(position_id)})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_org_unit_filter_does_not_expand_team_scope(client, seed):
    foreign_task_id: int | None = None
    foreign_unit_id: int | None = None
    suffix = uuid4().hex[:8]

    try:
        with engine.begin() as conn:
            if not table_exists(conn, "org_units"):
                pytest.skip("org_units table not available")

            admin_user_id = _admin_user_id(conn)
            foreign_unit_id = insert_returning_id(
                conn,
                table="org_units",
                id_col="unit_id",
                values={"name": f"Pytest foreign unit {suffix}", "code": f"pytest_foreign_unit_{suffix}"},
            )

        foreign_task_id = create_task(
            period_id=seed["period_id"],
            title=f"Pytest foreign unit task {suffix}",
            initiator_user_id=seed["initiator_user_id"],
            executor_role_id=seed["executor_role_id"],
            assignment_scope=seed["assignment_scope"],
            status_code="IN_PROGRESS",
            unit_id=foreign_unit_id,
        )

        resp = _list_tasks(
            client,
            admin_user_id,
            scope="team",
            org_unit_id=foreign_unit_id,
            limit=200,
            offset=0,
        )
        assert resp.status_code == 200, resp.text
        ids = {int(x["task_id"]) for x in (resp.json().get("items") or [])}
        assert foreign_task_id not in ids
    finally:
        if foreign_task_id is not None:
            cleanup_task(foreign_task_id)
        if foreign_unit_id is not None:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM public.org_units WHERE unit_id = :uid"), {"uid": int(foreign_unit_id)})
