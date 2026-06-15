# tests/test_personnel_events_create.py
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


def _phase_1a_columns_present(conn) -> bool:
    if not table_exists(conn, "employee_events"):
        return False
    cols = get_columns(conn, "employee_events")
    return {"event_class", "lifecycle_status", "metadata"}.issubset(cols)


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


def _cleanup(employee_ids: List[int], position_ids: List[int]) -> None:
    if not employee_ids:
        return
    with engine.begin() as conn:
        if table_exists(conn, "employee_events"):
            conn.execute(
                text("DELETE FROM public.employee_events WHERE employee_id = ANY(:ids)"),
                {"ids": employee_ids},
            )
        if table_exists(conn, "employees"):
            conn.execute(
                text("DELETE FROM public.employees WHERE employee_id = ANY(:ids)"),
                {"ids": employee_ids},
            )
        if position_ids:
            conn.execute(
                text("DELETE FROM public.positions WHERE position_id = ANY(:ids)"),
                {"ids": position_ids},
            )


def _make_employee(seed) -> tuple[int, List[int], List[int]]:
    emp_ids: List[int] = []
    pos_ids: List[int] = []
    with engine.begin() as conn:
        if not _phase_1a_columns_present(conn):
            pytest.skip("Phase 1A employee_events columns not available")
        pos_id = _create_position(conn, name=f"pytest_pe_create_{uuid4().hex[:8]}")
        pos_ids.append(pos_id)
        emp_id = _create_employee(
            conn,
            full_name=f"PytestPECreate {uuid4().hex[:8]}",
            org_unit_id=int(seed["unit_id"]),
            position_id=pos_id,
        )
        emp_ids.append(emp_id)
    return emp_id, emp_ids, pos_ids


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_post_unknown_event_type_returns_422(client, seed, privileged_headers):
    emp_id, emp_ids, pos_ids = _make_employee(seed)
    try:
        resp = client.post(
            f"/directory/employees/{emp_id}/personnel-events",
            json={"event_type": "NOT_A_REAL_TYPE", "effective_date": "2026-06-15"},
            headers=privileged_headers,
        )
        assert resp.status_code == 422, resp.text
    finally:
        _cleanup(emp_ids, pos_ids)


@pytest.mark.parametrize("event_type", ["BONUS", "ANNUAL_LEAVE", "HIRE"])
@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_post_deferred_event_type_returns_422(client, seed, privileged_headers, event_type):
    emp_id, emp_ids, pos_ids = _make_employee(seed)
    try:
        resp = client.post(
            f"/directory/employees/{emp_id}/personnel-events",
            json={"event_type": event_type, "effective_date": "2026-06-15"},
            headers=privileged_headers,
        )
        assert resp.status_code == 422, resp.text
        assert "Phase 1A" in resp.text
    finally:
        _cleanup(emp_ids, pos_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_post_transfer_via_personnel_events_returns_item_and_event(client, seed, privileged_headers):
    emp_id, emp_ids, pos_ids = _make_employee(seed)
    with engine.begin() as conn:
        to_unit = insert_returning_id(
            conn,
            table="org_units",
            id_col="unit_id",
            values={"name": f"pytest_pe_xfer_{uuid4().hex[:8]}", "code": "x", "is_active": True},
        )
    try:
        resp = client.post(
            f"/directory/employees/{emp_id}/personnel-events",
            json={
                "event_type": "TRANSFER",
                "to_org_unit_id": to_unit,
                "effective_date": "2026-06-15",
            },
            headers=privileged_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "item" in body
        assert "event" in body
        assert body["event"]["event_type"] == "TRANSFER"
        assert body["event"]["event_class"] == "EMPLOYMENT"
    finally:
        _cleanup(emp_ids, pos_ids)
        _cleanup([], pos_ids)
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM public.org_units WHERE unit_id = :uid"), {"uid": to_unit})
