# tests/test_employees_create.py
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


def _create_position(conn, *, name: str) -> int:
    cols = get_columns(conn, "positions")
    values: Dict[str, Any] = {"name": name}
    if "category" in cols:
        values["category"] = "other"
    return insert_returning_id(conn, table="positions", id_col="position_id", values=values)


def _cleanup_employees(full_names: List[str]) -> None:
    if not full_names:
        return
    with engine.begin() as conn:
        if table_exists(conn, "employee_events"):
            conn.execute(
                text(
                    """
                    DELETE FROM public.employee_events
                    WHERE employee_id IN (
                        SELECT employee_id FROM public.employees WHERE full_name = ANY(:names)
                    )
                    """
                ),
                {"names": full_names},
            )
        conn.execute(
            text("DELETE FROM public.employees WHERE full_name = ANY(:names)"),
            {"names": full_names},
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
def test_create_employee_privileged_returns_201(client, seed, privileged_headers):
    unique_name = f"PytestEmpCreate {uuid4().hex[:8]}"
    created_names: List[str] = [unique_name]
    created_position_ids: List[int] = []

    try:
        with engine.begin() as conn:
            if not table_exists(conn, "employees"):
                pytest.skip("employees table not available")
            position_id = _create_position(conn, name=f"pytest_pos_{uuid4().hex[:8]}")
            created_position_ids.append(position_id)

        payload = {
            "full_name": unique_name,
            "org_unit_id": int(seed["unit_id"]),
            "position_id": int(position_id),
        }

        resp = client.post("/directory/employees", json=payload, headers=privileged_headers)
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["fio"] == unique_name
        assert body["id"]
        assert body["org_unit"]["unit_id"] == int(seed["unit_id"])
        assert body["position"]["id"] == int(position_id)
        assert body["status"] == "active"
    finally:
        _cleanup_employees(created_names)
        _cleanup_positions(created_position_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_create_employee_unprivileged_returns_403(client, seed):
    with engine.begin() as conn:
        if not table_exists(conn, "employees"):
            pytest.skip("employees table not available")
        position_id = _create_position(conn, name=f"pytest_pos_{uuid4().hex[:8]}")

    try:
        resp = client.post(
            "/directory/employees",
            json={
                "full_name": "PytestEmpCreate Forbidden",
                "org_unit_id": int(seed["unit_id"]),
                "position_id": int(position_id),
            },
            headers=auth_headers(seed["executor_user_id"]),
        )
        assert resp.status_code == 403, resp.text
    finally:
        _cleanup_positions([int(position_id)])


@pytest.mark.parametrize(
    "payload",
    [
        {"org_unit_id": 1, "position_id": 1},
        {"full_name": "X", "position_id": 1},
        {"full_name": "X", "org_unit_id": 1},
        {"full_name": "", "org_unit_id": 1, "position_id": 1},
    ],
)
@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_create_employee_missing_required_fields_returns_422(client, privileged_headers, payload):
    resp = client.post("/directory/employees", json=payload, headers=privileged_headers)
    assert resp.status_code == 422, resp.text


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_create_employee_bad_org_unit_id_returns_404(client, seed, privileged_headers):
    created_position_ids: List[int] = []

    try:
        with engine.begin() as conn:
            position_id = _create_position(conn, name=f"pytest_pos_{uuid4().hex[:8]}")
            created_position_ids.append(position_id)

        resp = client.post(
            "/directory/employees",
            json={
                "full_name": "PytestEmpCreate BadOrgUnit",
                "org_unit_id": 999999999,
                "position_id": int(position_id),
            },
            headers=privileged_headers,
        )
        assert resp.status_code == 404, resp.text
        assert "Org unit" in resp.text
    finally:
        _cleanup_positions(created_position_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_create_employee_bad_position_id_returns_404(client, seed, privileged_headers):
    resp = client.post(
        "/directory/employees",
        json={
            "full_name": "PytestEmpCreate BadPosition",
            "org_unit_id": int(seed["unit_id"]),
            "position_id": 999999999,
        },
        headers=privileged_headers,
    )
    assert resp.status_code == 404, resp.text
    assert "Position" in resp.text


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_create_employee_visible_via_list_and_get(client, seed, privileged_headers):
    unique_name = f"PytestEmpCreate Visible {uuid4().hex[:8]}"
    created_names: List[str] = [unique_name]
    created_position_ids: List[int] = []
    employee_id: Optional[str] = None

    try:
        with engine.begin() as conn:
            if not table_exists(conn, "employees"):
                pytest.skip("employees table not available")
            position_id = _create_position(conn, name=f"pytest_pos_{uuid4().hex[:8]}")
            created_position_ids.append(position_id)

        create_resp = client.post(
            "/directory/employees",
            json={
                "full_name": unique_name,
                "org_unit_id": int(seed["unit_id"]),
                "position_id": int(position_id),
            },
            headers=privileged_headers,
        )
        assert create_resp.status_code == 201, create_resp.text
        employee_id = str(create_resp.json()["id"])

        list_resp = client.get(
            "/directory/employees",
            params={"status": "all", "q": unique_name, "limit": 50},
            headers=privileged_headers,
        )
        assert list_resp.status_code == 200, list_resp.text
        list_body = list_resp.json()
        assert list_body["total"] >= 1
        fios = {str(x.get("fio") or "") for x in list_body["items"]}
        assert unique_name in fios

        get_resp = client.get(
            f"/directory/employees/{employee_id}",
            headers=privileged_headers,
        )
        assert get_resp.status_code == 200, get_resp.text
        get_body = get_resp.json()
        assert get_body["fio"] == unique_name
        assert get_body["id"] == employee_id
    finally:
        _cleanup_employees(created_names)
        _cleanup_positions(created_position_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_create_employee_emits_hire_event(client, seed, privileged_headers):
    unique_name = f"PytestEmpCreate HireEvent {uuid4().hex[:8]}"
    created_names: List[str] = [unique_name]
    created_position_ids: List[int] = []
    employee_id: Optional[str] = None

    try:
        with engine.begin() as conn:
            if not table_exists(conn, "employees") or not table_exists(conn, "employee_events"):
                pytest.skip("employees / employee_events tables not available")
            position_id = _create_position(conn, name=f"pytest_pos_{uuid4().hex[:8]}")
            created_position_ids.append(position_id)

        create_resp = client.post(
            "/directory/employees",
            json={
                "full_name": unique_name,
                "org_unit_id": int(seed["unit_id"]),
                "position_id": int(position_id),
                "date_from": "2024-03-01",
            },
            headers=privileged_headers,
        )
        assert create_resp.status_code == 201, create_resp.text
        employee_id = str(create_resp.json()["id"])

        events_resp = client.get(
            f"/directory/employees/{employee_id}/events",
            headers=privileged_headers,
        )
        assert events_resp.status_code == 200, events_resp.text
        body = events_resp.json()
        assert body["total"] == 1
        assert body["items"][0]["event_type"] == "HIRE"
        assert body["items"][0]["effective_date"] == "2024-03-01"
        assert body["items"][0]["to_org_unit_id"] == int(seed["unit_id"])
        assert body["items"][0]["to_position_id"] == int(position_id)
        assert body["items"][0]["from_org_unit_id"] is None
    finally:
        _cleanup_employees(created_names)
        _cleanup_positions(created_position_ids)
