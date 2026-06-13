# tests/test_employees_terminate.py
from __future__ import annotations

from typing import Any, Dict, List
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
        if table_exists(conn, "employee_events"):
            conn.execute(
                text("DELETE FROM public.employee_events WHERE employee_id = ANY(:ids)"),
                {"ids": [int(x) for x in employee_ids]},
            )
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


def _make_employee(seed) -> tuple[int, List[int], List[int]]:
    created_position_ids: List[int] = []
    created_employee_ids: List[int] = []

    with engine.begin() as conn:
        if not table_exists(conn, "employees"):
            pytest.skip("employees table not available")
        position_id = _create_position(conn, name=f"pytest_term_pos_{uuid4().hex[:8]}")
        created_position_ids.append(position_id)
        employee_id = _create_employee(
            conn,
            full_name=f"PytestTerminate {uuid4().hex[:8]}",
            org_unit_id=int(seed["unit_id"]),
            position_id=int(position_id),
        )
        created_employee_ids.append(employee_id)

    return int(employee_id), created_employee_ids, created_position_ids


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_terminate_employee_without_user_returns_200(client, seed, privileged_headers):
    employee_id, created_employee_ids, created_position_ids = _make_employee(seed)

    try:
        resp = client.post(
            f"/directory/employees/{employee_id}/terminate",
            headers=privileged_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "inactive"
        assert body["date_to"] is not None
        assert body.get("user") is None

        with engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT is_active, date_to
                    FROM public.employees
                    WHERE employee_id = :employee_id
                    """
                ),
                {"employee_id": employee_id},
            ).mappings().first()
        assert row is not None
        assert row["is_active"] is False
        assert row["date_to"] is not None
    finally:
        _cleanup_employees(created_employee_ids)
        _cleanup_positions(created_position_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_terminate_employee_with_linked_user_deactivates_user(client, seed, privileged_headers):
    employee_id, created_employee_ids, created_position_ids = _make_employee(seed)
    login = f"pytest_term_{uuid4().hex[:10]}"
    password = "SecretPass1"
    created_user_id: int | None = None

    try:
        create_user = client.post(
            "/directory/users",
            json={
                "employee_id": employee_id,
                "role_id": int(seed["executor_role_id"]),
                "login": login,
                "password": password,
            },
            headers=privileged_headers,
        )
        assert create_user.status_code == 201, create_user.text
        created_user_id = int(create_user.json()["user_id"])

        resp = client.post(
            f"/directory/employees/{employee_id}/terminate",
            headers=privileged_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "inactive"
        assert body.get("user") is not None
        assert body["user"]["is_active"] is False
        assert body["user"]["login"] == login

        with engine.begin() as conn:
            user_row = conn.execute(
                text("SELECT is_active, employee_id FROM public.users WHERE user_id = :uid"),
                {"uid": created_user_id},
            ).mappings().first()
        assert user_row is not None
        assert user_row["is_active"] is False
        assert int(user_row["employee_id"]) == employee_id
    finally:
        _cleanup_users_by_logins([login])
        _cleanup_employees(created_employee_ids)
        _cleanup_positions(created_position_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_terminate_employee_unprivileged_returns_403(client, seed):
    employee_id, created_employee_ids, created_position_ids = _make_employee(seed)

    try:
        resp = client.post(
            f"/directory/employees/{employee_id}/terminate",
            headers=auth_headers(seed["executor_user_id"]),
        )
        assert resp.status_code == 403, resp.text
    finally:
        _cleanup_employees(created_employee_ids)
        _cleanup_positions(created_position_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_terminate_employee_bad_id_returns_404(client, privileged_headers):
    resp = client.post(
        "/directory/employees/999999999/terminate",
        headers=privileged_headers,
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_terminate_employee_repeated_is_idempotent(client, seed, privileged_headers):
    employee_id, created_employee_ids, created_position_ids = _make_employee(seed)
    first_date = "2026-01-15"
    second_date = "2026-02-20"

    try:
        first = client.post(
            f"/directory/employees/{employee_id}/terminate",
            json={"date_to": first_date},
            headers=privileged_headers,
        )
        assert first.status_code == 200, first.text
        assert first.json()["date_to"] == first_date

        repeat = client.post(
            f"/directory/employees/{employee_id}/terminate",
            headers=privileged_headers,
        )
        assert repeat.status_code == 200, repeat.text
        assert repeat.json()["status"] == "inactive"
        assert repeat.json()["date_to"] == first_date

        repeat_with_date = client.post(
            f"/directory/employees/{employee_id}/terminate",
            json={"date_to": second_date},
            headers=privileged_headers,
        )
        assert repeat_with_date.status_code == 200, repeat_with_date.text
        assert repeat_with_date.json()["date_to"] == second_date
    finally:
        _cleanup_employees(created_employee_ids)
        _cleanup_positions(created_position_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_terminate_employee_emits_termination_event_once(client, seed, privileged_headers):
    employee_id, created_employee_ids, created_position_ids = _make_employee(seed)
    termination_date = "2026-05-30"

    try:
        with engine.begin() as conn:
            if not table_exists(conn, "employee_events"):
                pytest.skip("employee_events table not available")

        first = client.post(
            f"/directory/employees/{employee_id}/terminate",
            json={"date_to": termination_date},
            headers=privileged_headers,
        )
        assert first.status_code == 200, first.text

        events_resp = client.get(
            f"/directory/employees/{employee_id}/events",
            headers=privileged_headers,
        )
        assert events_resp.status_code == 200, events_resp.text
        body = events_resp.json()
        assert body["total"] == 1
        assert body["items"][0]["event_type"] == "TERMINATION"
        assert body["items"][0]["effective_date"] == termination_date
        assert body["items"][0]["from_org_unit_id"] == int(seed["unit_id"])
        assert body["items"][0]["to_org_unit_id"] is None

        repeat = client.post(
            f"/directory/employees/{employee_id}/terminate",
            headers=privileged_headers,
        )
        assert repeat.status_code == 200, repeat.text

        events_repeat = client.get(
            f"/directory/employees/{employee_id}/events",
            headers=privileged_headers,
        )
        assert events_repeat.status_code == 200, events_repeat.text
        assert events_repeat.json()["total"] == 1
    finally:
        _cleanup_employees(created_employee_ids)
        _cleanup_positions(created_position_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_terminated_user_cannot_login(client, seed, privileged_headers):
    employee_id, created_employee_ids, created_position_ids = _make_employee(seed)
    login = f"pytest_term_{uuid4().hex[:10]}"
    password = "SecretPass1"

    try:
        create_user = client.post(
            "/directory/users",
            json={
                "employee_id": employee_id,
                "role_id": int(seed["executor_role_id"]),
                "login": login,
                "password": password,
            },
            headers=privileged_headers,
        )
        assert create_user.status_code == 201, create_user.text

        terminate = client.post(
            f"/directory/employees/{employee_id}/terminate",
            headers=privileged_headers,
        )
        assert terminate.status_code == 200, terminate.text

        login_resp = client.post(
            "/auth/login",
            json={"login": login, "password": password},
        )
        assert login_resp.status_code == 403, login_resp.text
        assert "неактив" in login_resp.text.lower()
    finally:
        _cleanup_users_by_logins([login])
        _cleanup_employees(created_employee_ids)
        _cleanup_positions(created_position_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_working_contacts_excludes_terminated_linked_user(client, seed, privileged_headers):
    employee_id, created_employee_ids, created_position_ids = _make_employee(seed)
    login = f"pytest_term_{uuid4().hex[:10]}"
    password = "SecretPass1"
    created_user_id: int | None = None

    try:
        create_user = client.post(
            "/directory/users",
            json={
                "employee_id": employee_id,
                "role_id": int(seed["executor_role_id"]),
                "login": login,
                "password": password,
            },
            headers=privileged_headers,
        )
        assert create_user.status_code == 201, create_user.text
        created_user_id = int(create_user.json()["user_id"])

        before = client.get("/directory/working-contacts", headers=privileged_headers)
        assert before.status_code == 200, before.text
        before_ids = {
            int(x.get("user_id") or x.get("id") or 0) for x in (before.json().get("items") or [])
        }
        assert created_user_id in before_ids

        terminate = client.post(
            f"/directory/employees/{employee_id}/terminate",
            headers=privileged_headers,
        )
        assert terminate.status_code == 200, terminate.text

        after = client.get("/directory/working-contacts", headers=privileged_headers)
        assert after.status_code == 200, after.text
        after_ids = {
            int(x.get("user_id") or x.get("id") or 0) for x in (after.json().get("items") or [])
        }
        assert created_user_id not in after_ids
    finally:
        _cleanup_users_by_logins([login])
        _cleanup_employees(created_employee_ids)
        _cleanup_positions(created_position_ids)
