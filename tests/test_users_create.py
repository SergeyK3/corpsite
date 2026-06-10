# tests/test_users_create.py
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


def _make_employee(seed) -> tuple[int, int, List[int], List[int]]:
    created_position_ids: List[int] = []
    created_employee_ids: List[int] = []

    with engine.begin() as conn:
        if not table_exists(conn, "employees"):
            pytest.skip("employees table not available")
        if not _users_has_employee_id(conn):
            pytest.skip("users.employee_id column not available")

        position_id = _create_position(conn, name=f"pytest_user_pos_{uuid4().hex[:8]}")
        created_position_ids.append(position_id)

        full_name = f"PytestUserCreate {uuid4().hex[:8]}"
        employee_id = _create_employee(
            conn,
            full_name=full_name,
            org_unit_id=int(seed["unit_id"]),
            position_id=int(position_id),
        )
        created_employee_ids.append(employee_id)

    return int(employee_id), int(position_id), created_employee_ids, created_position_ids


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_create_user_privileged_returns_201(client, seed, privileged_headers):
    employee_id, _position_id, created_employee_ids, created_position_ids = _make_employee(seed)
    login = f"pytest_user_{uuid4().hex[:10]}"
    password = "SecretPass1"

    try:
        resp = client.post(
            "/directory/users",
            json={
                "employee_id": employee_id,
                "role_id": int(seed["executor_role_id"]),
                "login": login,
                "password": password,
                "is_active": True,
            },
            headers=privileged_headers,
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["user_id"]
        assert body["employee_id"] == employee_id
        assert body["login"] == login
        assert body["role_id"] == int(seed["executor_role_id"])
        assert body["is_active"] is True
    finally:
        _cleanup_users_by_logins([login])
        _cleanup_employees(created_employee_ids)
        _cleanup_positions(created_position_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_create_user_unprivileged_returns_403(client, seed):
    employee_id, _position_id, created_employee_ids, created_position_ids = _make_employee(seed)
    login = f"pytest_user_{uuid4().hex[:10]}"

    try:
        resp = client.post(
            "/directory/users",
            json={
                "employee_id": employee_id,
                "role_id": int(seed["executor_role_id"]),
                "login": login,
                "password": "SecretPass1",
            },
            headers=auth_headers(seed["executor_user_id"]),
        )
        assert resp.status_code == 403, resp.text
    finally:
        _cleanup_employees(created_employee_ids)
        _cleanup_positions(created_position_ids)


@pytest.mark.parametrize(
    "payload",
    [
        {"role_id": 1, "login": "x", "password": "12345678"},
        {"employee_id": 1, "login": "x", "password": "12345678"},
        {"employee_id": 1, "role_id": 1, "password": "12345678"},
        {"employee_id": 1, "role_id": 1, "login": "x"},
        {"employee_id": 1, "role_id": 1, "login": "x", "password": "short"},
    ],
)
@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_create_user_missing_required_fields_returns_422(client, privileged_headers, payload):
    resp = client.post("/directory/users", json=payload, headers=privileged_headers)
    assert resp.status_code == 422, resp.text


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_create_user_bad_employee_id_returns_404(client, seed, privileged_headers):
    resp = client.post(
        "/directory/users",
        json={
            "employee_id": 999999999,
            "role_id": int(seed["executor_role_id"]),
            "login": f"pytest_user_{uuid4().hex[:10]}",
            "password": "SecretPass1",
        },
        headers=privileged_headers,
    )
    assert resp.status_code == 404, resp.text
    assert "Employee" in resp.text


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_create_user_bad_role_id_returns_404(client, seed, privileged_headers):
    employee_id, _position_id, created_employee_ids, created_position_ids = _make_employee(seed)

    try:
        resp = client.post(
            "/directory/users",
            json={
                "employee_id": employee_id,
                "role_id": 999999999,
                "login": f"pytest_user_{uuid4().hex[:10]}",
                "password": "SecretPass1",
            },
            headers=privileged_headers,
        )
        assert resp.status_code == 404, resp.text
        assert "Role" in resp.text
    finally:
        _cleanup_employees(created_employee_ids)
        _cleanup_positions(created_position_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_create_user_duplicate_login_returns_409(client, seed, privileged_headers):
    employee_id, _position_id, created_employee_ids, created_position_ids = _make_employee(seed)
    login = f"pytest_user_{uuid4().hex[:10]}"
    password = "SecretPass1"

    try:
        first = client.post(
            "/directory/users",
            json={
                "employee_id": employee_id,
                "role_id": int(seed["executor_role_id"]),
                "login": login,
                "password": password,
            },
            headers=privileged_headers,
        )
        assert first.status_code == 201, first.text

        with engine.begin() as conn:
            position_id2 = _create_position(conn, name=f"pytest_user_pos_{uuid4().hex[:8]}")
            created_position_ids.append(position_id2)
            employee_id2 = _create_employee(
                conn,
                full_name=f"PytestUserCreate {uuid4().hex[:8]}",
                org_unit_id=int(seed["unit_id"]),
                position_id=int(position_id2),
            )
            created_employee_ids.append(employee_id2)

        second = client.post(
            "/directory/users",
            json={
                "employee_id": employee_id2,
                "role_id": int(seed["executor_role_id"]),
                "login": login,
                "password": password,
            },
            headers=privileged_headers,
        )
        assert second.status_code == 409, second.text
        assert "Login" in second.text
    finally:
        _cleanup_users_by_logins([login])
        _cleanup_employees(created_employee_ids)
        _cleanup_positions(created_position_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_create_user_duplicate_employee_id_returns_409(client, seed, privileged_headers):
    employee_id, _position_id, created_employee_ids, created_position_ids = _make_employee(seed)
    login1 = f"pytest_user_{uuid4().hex[:10]}"
    login2 = f"pytest_user_{uuid4().hex[:10]}"
    password = "SecretPass1"

    try:
        first = client.post(
            "/directory/users",
            json={
                "employee_id": employee_id,
                "role_id": int(seed["executor_role_id"]),
                "login": login1,
                "password": password,
            },
            headers=privileged_headers,
        )
        assert first.status_code == 201, first.text

        second = client.post(
            "/directory/users",
            json={
                "employee_id": employee_id,
                "role_id": int(seed["executor_role_id"]),
                "login": login2,
                "password": password,
            },
            headers=privileged_headers,
        )
        assert second.status_code == 409, second.text
        assert "employee" in second.text.lower()
    finally:
        _cleanup_users_by_logins([login1, login2])
        _cleanup_employees(created_employee_ids)
        _cleanup_positions(created_position_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_get_employee_shows_linked_user(client, seed, privileged_headers):
    employee_id, _position_id, created_employee_ids, created_position_ids = _make_employee(seed)
    login = f"pytest_user_{uuid4().hex[:10]}"
    password = "SecretPass1"

    try:
        create_resp = client.post(
            "/directory/users",
            json={
                "employee_id": employee_id,
                "role_id": int(seed["executor_role_id"]),
                "login": login,
                "password": password,
            },
            headers=privileged_headers,
        )
        assert create_resp.status_code == 201, create_resp.text
        created_user = create_resp.json()

        get_resp = client.get(
            f"/directory/employees/{employee_id}",
            headers=privileged_headers,
        )
        assert get_resp.status_code == 200, get_resp.text
        body = get_resp.json()
        assert body.get("user") is not None
        assert body["user"]["user_id"] == created_user["user_id"]
        assert body["user"]["login"] == login
        assert body["user"]["role_id"] == int(seed["executor_role_id"])
        assert body["user"]["is_active"] is True
    finally:
        _cleanup_users_by_logins([login])
        _cleanup_employees(created_employee_ids)
        _cleanup_positions(created_position_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_auth_login_works_for_created_user(client, seed, privileged_headers):
    employee_id, _position_id, created_employee_ids, created_position_ids = _make_employee(seed)
    login = f"pytest_user_{uuid4().hex[:10]}"
    password = "SecretPass1"

    try:
        create_resp = client.post(
            "/directory/users",
            json={
                "employee_id": employee_id,
                "role_id": int(seed["executor_role_id"]),
                "login": login,
                "password": password,
            },
            headers=privileged_headers,
        )
        assert create_resp.status_code == 201, create_resp.text

        login_resp = client.post(
            "/auth/login",
            json={"login": login, "password": password},
        )
        assert login_resp.status_code == 200, login_resp.text
        token_body = login_resp.json()
        assert token_body.get("access_token")
        assert token_body.get("token_type") == "bearer"
    finally:
        _cleanup_users_by_logins([login])
        _cleanup_employees(created_employee_ids)
        _cleanup_positions(created_position_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_working_contacts_sees_created_user(client, seed, privileged_headers):
    employee_id, _position_id, created_employee_ids, created_position_ids = _make_employee(seed)
    login = f"pytest_user_{uuid4().hex[:10]}"
    password = "SecretPass1"
    created_user_id: Optional[int] = None

    try:
        create_resp = client.post(
            "/directory/users",
            json={
                "employee_id": employee_id,
                "role_id": int(seed["executor_role_id"]),
                "login": login,
                "password": password,
            },
            headers=privileged_headers,
        )
        assert create_resp.status_code == 201, create_resp.text
        created_user_id = int(create_resp.json()["user_id"])

        list_resp = client.get("/directory/working-contacts", headers=privileged_headers)
        assert list_resp.status_code == 200, list_resp.text
        items = list_resp.json().get("items") or []
        ids = {int(x.get("user_id") or x.get("id") or 0) for x in items}
        assert created_user_id in ids

        one_resp = client.get(
            f"/directory/working-contacts/{created_user_id}",
            headers=privileged_headers,
        )
        assert one_resp.status_code == 200, one_resp.text
        one_body = one_resp.json()
        assert one_body.get("login") == login
    finally:
        _cleanup_users_by_logins([login])
        _cleanup_employees(created_employee_ids)
        _cleanup_positions(created_position_ids)
