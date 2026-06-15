# tests/test_personnel_events_position_change.py
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


def _make_fixture(seed) -> tuple[int, int, int, int, List[int], List[int]]:
    emp_ids: List[int] = []
    pos_ids: List[int] = []
    with engine.begin() as conn:
        if not _phase_1a_columns_present(conn):
            pytest.skip("Phase 1A employee_events columns not available")
        org_unit_id = int(seed["unit_id"])
        from_pos = _create_position(conn, name=f"pytest_pos_from_{uuid4().hex[:8]}")
        to_pos = _create_position(conn, name=f"pytest_pos_to_{uuid4().hex[:8]}")
        pos_ids.extend([from_pos, to_pos])
        emp_id = insert_returning_id(
            conn,
            table="employees",
            id_col="employee_id",
            values={
                "full_name": f"PytestPosChange {uuid4().hex[:8]}",
                "org_unit_id": org_unit_id,
                "position_id": from_pos,
                "employment_rate": 1.0,
                "is_active": True,
            },
        )
        emp_ids.append(emp_id)
    return emp_id, org_unit_id, from_pos, to_pos, emp_ids, pos_ids


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_position_change_updates_snapshot_and_event(client, seed, privileged_headers):
    emp_id, org_unit_id, from_pos, to_pos, emp_ids, pos_ids = _make_fixture(seed)

    try:
        resp = client.post(
            f"/directory/employees/{emp_id}/personnel-events",
            json={
                "event_type": "POSITION_CHANGE",
                "to_position_id": to_pos,
                "effective_date": "2026-06-15",
            },
            headers=privileged_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["item"]["org_unit"]["unit_id"] == org_unit_id
        assert int(body["item"]["position"]["id"]) == to_pos
        assert body["event"]["event_type"] == "POSITION_CHANGE"
        assert body["event"]["event_class"] == "EMPLOYMENT"
        assert body["event"]["lifecycle_status"] == "APPROVED"
        assert body["event"]["event_label"] == "Смена должности"

        with engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT org_unit_id, position_id, event_type, event_class, lifecycle_status
                    FROM public.employees e
                    JOIN public.employee_events ev ON ev.employee_id = e.employee_id
                    WHERE e.employee_id = :employee_id
                    ORDER BY ev.event_id DESC
                    LIMIT 1
                    """
                ),
                {"employee_id": emp_id},
            ).mappings().first()
        assert row is not None
        assert int(row["org_unit_id"]) == org_unit_id
        assert int(row["position_id"]) == to_pos
        assert row["event_type"] == "POSITION_CHANGE"
        assert row["event_class"] == "EMPLOYMENT"
        assert row["lifecycle_status"] == "APPROVED"

        journal = client.get("/directory/personnel-events", headers=privileged_headers)
        assert journal.status_code == 200, journal.text
        match = [x for x in journal.json()["items"] if x["event_id"] == body["event"]["event_id"]]
        assert len(match) == 1
        assert match[0]["event_label"] == "Смена должности"

        history = client.get(f"/directory/employees/{emp_id}/events", headers=privileged_headers)
        assert history.status_code == 200, history.text
        assert history.json()["items"][0]["event_label"] == "Смена должности"
    finally:
        _cleanup(emp_ids, pos_ids)
