# tests/test_auth_me_position.py
from __future__ import annotations

from typing import Any, Dict, List
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import auth_headers, get_columns, insert_returning_id, table_exists


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _users_has_employee_id(conn) -> bool:
    if not table_exists(conn, "users"):
        return False
    return "employee_id" in get_columns(conn, "users")


def _create_position(conn, *, name: str) -> int:
    cols = get_columns(conn, "positions")
    values: Dict[str, Any] = {"name": name}
    if "category" in cols:
        values["category"] = "other"
    return insert_returning_id(conn, table="positions", id_col="position_id", values=values)


def _create_employee(conn, *, full_name: str, org_unit_id: int, position_id: int) -> int:
    return insert_returning_id(
        conn,
        table="employees",
        id_col="employee_id",
        values={
            "full_name": full_name,
            "org_unit_id": int(org_unit_id),
            "position_id": int(position_id),
            "employment_rate": 1.0,
            "is_active": True,
        },
    )


def _cleanup_users_by_ids(user_ids: List[int]) -> None:
    if not user_ids:
        return
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM public.users WHERE user_id = ANY(:ids)"),
            {"ids": [int(x) for x in user_ids]},
        )


def _cleanup_employees(employee_ids: List[int]) -> None:
    if not employee_ids:
        return
    with engine.begin() as conn:
        if table_exists(conn, "users"):
            conn.execute(
                text("UPDATE public.users SET employee_id = NULL WHERE employee_id = ANY(:ids)"),
                {"ids": [int(x) for x in employee_ids]},
            )
        if table_exists(conn, "employees"):
            conn.execute(
                text("DELETE FROM public.employees WHERE employee_id = ANY(:ids)"),
                {"ids": [int(x) for x in employee_ids]},
            )


def _cleanup_positions(position_ids: List[int]) -> None:
    if not position_ids:
        return
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM public.positions WHERE position_id = ANY(:ids)"),
            {"ids": [int(x) for x in position_ids]},
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_auth_me_includes_employee_position(client: TestClient, seed: Dict[str, Any]) -> None:
    with engine.begin() as conn:
        if not _users_has_employee_id(conn):
            pytest.skip("users.employee_id column missing")

        suffix = uuid4().hex[:8]
        role_name = f"pytest_dep_admin_{suffix}"
        position_name = f"pytest_hr_position_{suffix}"
        role_id = insert_returning_id(
            conn,
            table="roles",
            id_col="role_id",
            values={"name": role_name, "code": role_name},
        )
        position_id = _create_position(conn, name=position_name)
        employee_id = _create_employee(
            conn,
            full_name="Pytest HR Position User",
            org_unit_id=int(seed["unit_id"]),
            position_id=position_id,
        )
        user_id = insert_returning_id(
            conn,
            table="users",
            id_col="user_id",
            values={
                "full_name": "Pytest HR Position User",
                "role_id": role_id,
                "unit_id": int(seed["unit_id"]),
                "employee_id": employee_id,
                "is_active": True,
            },
        )

    try:
        resp = client.get("/auth/me", headers=auth_headers(user_id))
        assert resp.status_code == 200, resp.text

        body = resp.json()
        assert body["role_name_ru"] == role_name
        assert body["position_id"] == position_id
        assert body["position_name"] == position_name
    finally:
        _cleanup_users_by_ids([user_id])
        _cleanup_employees([employee_id])
        _cleanup_positions([position_id])
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM public.roles WHERE role_id = :role_id"), {"role_id": role_id})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_auth_me_position_null_without_employee_link(client: TestClient, seed: Dict[str, Any]) -> None:
    user_id = int(seed["executor_user_id"])

    resp = client.get("/auth/me", headers=auth_headers(user_id))
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body.get("position_name") in (None, "")
    assert body.get("position_id") in (None, 0)
