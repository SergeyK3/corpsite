# tests/test_working_contacts_routes.py
from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import uuid4

import pytest
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


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


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


def _cleanup_users_by_logins(logins: List[str]) -> None:
    if not logins:
        return
    with engine.begin() as conn:
        if not table_exists(conn, "users"):
            return
        conn.execute(
            text("DELETE FROM public.users WHERE login = ANY(:logins)"),
            {"logins": logins},
        )


def _cleanup_employees(employee_ids: List[int]) -> None:
    if not employee_ids:
        return
    with engine.begin() as conn:
        if table_exists(conn, "users"):
            conn.execute(
                text("DELETE FROM public.users WHERE employee_id = ANY(:ids)"),
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


def test_list_working_contacts_returns_200(client, seed, privileged_headers):
    resp = client.get("/directory/working-contacts", headers=privileged_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert isinstance(body["items"], list)


def test_list_working_contacts_by_org_unit_returns_200(client, seed, privileged_headers):
    if seed.get("unit_id") is None:
        pytest.skip("unit table not available")

    resp = client.get(
        f"/directory/working-contacts?org_unit_id={seed['unit_id']}",
        headers=privileged_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("filter_org_unit_id") == seed["unit_id"]


def test_get_working_contact_returns_200(client, seed, privileged_headers):
    user_id = seed["initiator_user_id"]
    resp = client.get(f"/directory/working-contacts/{user_id}", headers=privileged_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user_id"] == user_id
    assert "unit_name" in body
    assert "unit_name_ru" in body
    assert "role_name" in body
    assert "employee_id" in body
    assert "position_id" in body
    assert "position_name" in body
    assert "telegram_id" in body


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_working_contact_includes_employee_position_and_telegram_id(client, seed, privileged_headers):
    unique_name = f"PytestWcEnriched {uuid4().hex[:8]}"
    position_name = f"pytest_wc_pos_{uuid4().hex[:8]}"
    login = f"pytest_wc_{uuid4().hex[:10]}"
    telegram_id = 9876543210123
    created_employee_ids: List[int] = []
    created_position_ids: List[int] = []
    created_user_id: Optional[int] = None

    try:
        with engine.begin() as conn:
            if not _users_has_employee_id(conn):
                pytest.skip("users.employee_id column not available")
            position_id = _create_position(conn, name=position_name)
            created_position_ids.append(position_id)
            employee_id = _create_employee(
                conn,
                full_name=unique_name,
                org_unit_id=int(seed["unit_id"]),
                position_id=position_id,
            )
            created_employee_ids.append(employee_id)

        create_resp = client.post(
            "/directory/users",
            json={
                "employee_id": employee_id,
                "role_id": int(seed["executor_role_id"]),
                "login": login,
                "password": "SecretPass1",
            },
            headers=privileged_headers,
        )
        assert create_resp.status_code == 201, create_resp.text
        created_user_id = int(create_resp.json()["user_id"])

        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE public.users
                    SET telegram_id = :telegram_id
                    WHERE user_id = :user_id
                    """
                ),
                {"telegram_id": telegram_id, "user_id": created_user_id},
            )

        one_resp = client.get(
            f"/directory/working-contacts/{created_user_id}",
            headers=privileged_headers,
        )
        assert one_resp.status_code == 200, one_resp.text
        body = one_resp.json()
        assert body["employee_id"] == employee_id
        assert body["position_id"] == position_id
        assert body["position_name"] == position_name
        assert body["telegram_id"] == telegram_id
        assert body["role_name"] is not None

        list_resp = client.get(
            f"/directory/working-contacts?q={login}&active_only=false",
            headers=privileged_headers,
        )
        assert list_resp.status_code == 200, list_resp.text
        items = list_resp.json().get("items") or []
        assert len(items) >= 1
        matched = next(x for x in items if int(x["user_id"]) == created_user_id)
        assert matched["employee_id"] == employee_id
        assert matched["position_name"] == position_name
        assert matched["telegram_id"] == telegram_id
    finally:
        _cleanup_users_by_logins([login])
        _cleanup_employees(created_employee_ids)
        _cleanup_positions(created_position_ids)
