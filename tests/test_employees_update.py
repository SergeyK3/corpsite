# tests/test_employees_update.py
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


def _create_position(conn, *, name: str) -> int:
    cols = get_columns(conn, "positions")
    values: Dict[str, Any] = {"name": name}
    if "category" in cols:
        values["category"] = "other"
    return insert_returning_id(conn, table="positions", id_col="position_id", values=values)


def _create_employee(
    conn,
    *,
    full_name: str,
    org_unit_id: int,
    position_id: int,
    date_from: str | None = None,
    date_to: str | None = None,
    employment_rate: float = 1.0,
    is_active: bool = True,
) -> int:
    values: Dict[str, Any] = {
        "full_name": full_name,
        "org_unit_id": int(org_unit_id),
        "position_id": int(position_id),
        "employment_rate": employment_rate,
        "is_active": is_active,
    }
    if date_from is not None:
        values["date_from"] = date_from
    if date_to is not None:
        values["date_to"] = date_to
    return insert_returning_id(conn, table="employees", id_col="employee_id", values=values)


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


def _make_employee(seed) -> tuple[int, int, int, List[int], List[int]]:
    created_position_ids: List[int] = []
    created_employee_ids: List[int] = []

    with engine.begin() as conn:
        if not table_exists(conn, "employees"):
            pytest.skip("employees table not available")
        position_id = _create_position(conn, name=f"pytest_upd_pos_{uuid4().hex[:8]}")
        alt_position_id = _create_position(conn, name=f"pytest_upd_pos_alt_{uuid4().hex[:8]}")
        created_position_ids.extend([position_id, alt_position_id])
        employee_id = _create_employee(
            conn,
            full_name=f"PytestUpdate {uuid4().hex[:8]}",
            org_unit_id=int(seed["unit_id"]),
            position_id=int(position_id),
            date_from="2024-01-10",
            employment_rate=1.0,
        )
        created_employee_ids.append(employee_id)

    return int(employee_id), int(position_id), int(alt_position_id), created_employee_ids, created_position_ids


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_update_employee_happy_path(client, seed, privileged_headers):
    employee_id, position_id, alt_position_id, created_employee_ids, created_position_ids = _make_employee(seed)
    new_name = f"PytestUpdate Renamed {uuid4().hex[:8]}"

    try:
        resp = client.patch(
            f"/directory/employees/{employee_id}",
            json={
                "full_name": new_name,
                "employment_rate": 0.75,
                "date_from": "2024-02-01",
                "position_id": alt_position_id,
            },
            headers=privileged_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["fio"] == new_name
        assert float(body["rate"]) == 0.75
        assert body["date_from"] == "2024-02-01"
        assert int(body["position"]["id"]) == alt_position_id
        assert int(body["org_unit"]["unit_id"]) == int(seed["unit_id"])
    finally:
        _cleanup_employees(created_employee_ids)
        _cleanup_positions(created_position_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_update_employee_unprivileged_returns_403(client, seed):
    employee_id, _, _, created_employee_ids, created_position_ids = _make_employee(seed)

    try:
        resp = client.patch(
            f"/directory/employees/{employee_id}",
            json={"full_name": "Forbidden Update"},
            headers=auth_headers(seed["executor_user_id"]),
        )
        assert resp.status_code == 403, resp.text
    finally:
        _cleanup_employees(created_employee_ids)
        _cleanup_positions(created_position_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_update_employee_not_found_returns_404(client, privileged_headers):
    resp = client.patch(
        "/directory/employees/999999999",
        json={"full_name": "Missing Employee"},
        headers=privileged_headers,
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_update_employee_bad_position_returns_404(client, seed, privileged_headers):
    employee_id, _, _, created_employee_ids, created_position_ids = _make_employee(seed)

    try:
        resp = client.patch(
            f"/directory/employees/{employee_id}",
            json={"position_id": 999999999},
            headers=privileged_headers,
        )
        assert resp.status_code == 404, resp.text
        assert "Position" in resp.text
    finally:
        _cleanup_employees(created_employee_ids)
        _cleanup_positions(created_position_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_update_employee_date_from_after_date_to_returns_422(client, seed, privileged_headers):
    created_position_ids: List[int] = []
    created_employee_ids: List[int] = []

    try:
        with engine.begin() as conn:
            position_id = _create_position(conn, name=f"pytest_upd_pos_{uuid4().hex[:8]}")
            created_position_ids.append(position_id)
            employee_id = _create_employee(
                conn,
                full_name=f"PytestUpdate Term {uuid4().hex[:8]}",
                org_unit_id=int(seed["unit_id"]),
                position_id=int(position_id),
                date_from="2024-01-01",
                date_to="2024-06-30",
                is_active=False,
            )
            created_employee_ids.append(employee_id)

        resp = client.patch(
            f"/directory/employees/{employee_id}",
            json={"date_from": "2024-12-01"},
            headers=privileged_headers,
        )
        assert resp.status_code == 422, resp.text
        assert "date_from" in resp.text
    finally:
        _cleanup_employees(created_employee_ids)
        _cleanup_positions(created_position_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_update_employee_forbidden_fields_return_422(client, seed, privileged_headers):
    employee_id, _, _, created_employee_ids, created_position_ids = _make_employee(seed)

    try:
        for payload in (
            {"org_unit_id": int(seed["unit_id"])},
            {"is_active": False},
            {"date_to": "2026-01-01"},
            {"employee_id": 12345},
        ):
            resp = client.patch(
                f"/directory/employees/{employee_id}",
                json=payload,
                headers=privileged_headers,
            )
            assert resp.status_code == 422, resp.text
    finally:
        _cleanup_employees(created_employee_ids)
        _cleanup_positions(created_position_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_update_employee_empty_body_returns_422(client, seed, privileged_headers):
    employee_id, _, _, created_employee_ids, created_position_ids = _make_employee(seed)

    try:
        resp = client.patch(
            f"/directory/employees/{employee_id}",
            json={},
            headers=privileged_headers,
        )
        assert resp.status_code == 422, resp.text
    finally:
        _cleanup_employees(created_employee_ids)
        _cleanup_positions(created_position_ids)


@pytest.mark.parametrize("employment_rate", [0, -0.5, 2.5, 3])
@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_update_employee_bad_employment_rate_returns_422(
    client, seed, privileged_headers, employment_rate
):
    employee_id, _, _, created_employee_ids, created_position_ids = _make_employee(seed)

    try:
        resp = client.patch(
            f"/directory/employees/{employee_id}",
            json={"employment_rate": employment_rate},
            headers=privileged_headers,
        )
        assert resp.status_code == 422, resp.text
    finally:
        _cleanup_employees(created_employee_ids)
        _cleanup_positions(created_position_ids)
