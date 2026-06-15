# tests/test_personnel_demo_routes.py
from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import auth_headers, get_columns, insert_returning_id, table_exists


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


def _find_group_id(conn) -> int:
    row = conn.execute(
        text(
            """
            SELECT group_id
            FROM public.org_units
            WHERE group_id IS NOT NULL
            LIMIT 1
            """
        )
    ).first()
    if row:
        return int(row[0])
    return 1


def _create_unit_with_group(
    conn,
    *,
    name: str,
    group_id: int,
) -> int:
    cols = get_columns(conn, "org_units")
    values: Dict[str, Any] = {"name": name}
    if "code" in cols:
        values["code"] = name
    if "group_id" in cols:
        values["group_id"] = int(group_id)
    if "is_active" in cols:
        values["is_active"] = True
    return insert_returning_id(conn, table="org_units", id_col="unit_id", values=values)


def _create_position(conn, *, name: str) -> int:
    cols = get_columns(conn, "positions")
    values: Dict[str, Any] = {"name": name}
    if "category" in cols:
        values["category"] = "other"
    return insert_returning_id(conn, table="positions", id_col="position_id", values=values)


def _create_employee_without_position(
    conn,
    *,
    full_name: str,
    org_unit_id: int,
) -> int:
    return insert_returning_id(
        conn,
        table="employees",
        id_col="employee_id",
        values={
            "full_name": full_name,
            "org_unit_id": int(org_unit_id),
            "position_id": None,
            "employment_rate": None,
            "is_active": True,
        },
    )


def _cleanup_employee_events(employee_ids: List[int]) -> None:
    if not employee_ids:
        return
    with engine.begin() as conn:
        if table_exists(conn, "employee_events"):
            conn.execute(
                text("DELETE FROM public.employee_events WHERE employee_id = ANY(:ids)"),
                {"ids": [int(x) for x in employee_ids]},
            )


def _cleanup_employees(employee_ids: List[int]) -> None:
    if not employee_ids:
        return
    with engine.begin() as conn:
        _cleanup_employee_events(employee_ids)
        if table_exists(conn, "employees"):
            conn.execute(
                text("DELETE FROM public.employees WHERE employee_id = ANY(:ids)"),
                {"ids": [int(x) for x in employee_ids]},
            )


def _cleanup_positions(position_ids: List[int]) -> None:
    if not position_ids:
        return
    with engine.begin() as conn:
        if table_exists(conn, "positions"):
            conn.execute(
                text("DELETE FROM public.positions WHERE position_id = ANY(:ids)"),
                {"ids": [int(x) for x in position_ids]},
            )


def _cleanup_units(unit_ids: List[int]) -> None:
    if not unit_ids:
        return
    with engine.begin() as conn:
        if table_exists(conn, "org_units"):
            conn.execute(
                text("DELETE FROM public.org_units WHERE unit_id = ANY(:ids)"),
                {"ids": [int(x) for x in unit_ids]},
            )


def _make_null_from_transfer_fixture(seed) -> tuple[int, int, int, List[int], List[int], List[int]]:
    created_unit_ids: List[int] = []
    created_position_ids: List[int] = []
    created_employee_ids: List[int] = []

    with engine.begin() as conn:
        if not table_exists(conn, "employee_events"):
            pytest.skip("employee_events table not available")

        group_id = _find_group_id(conn)
        from_unit_id = int(seed["unit_id"])
        to_unit_id = _create_unit_with_group(
            conn,
            name=f"pytest_pers_to_{uuid4().hex[:8]}",
            group_id=group_id,
        )
        created_unit_ids.append(to_unit_id)

        target_position_id = _create_position(
            conn,
            name=f"pytest_pers_pos_{uuid4().hex[:8]}",
        )
        created_position_ids.append(target_position_id)

        employee_id = _create_employee_without_position(
            conn,
            full_name=f"PytestPersonnelNull {uuid4().hex[:8]}",
            org_unit_id=from_unit_id,
        )
        created_employee_ids.append(employee_id)

    return (
        int(employee_id),
        int(from_unit_id),
        int(to_unit_id),
        created_employee_ids,
        created_position_ids,
        created_unit_ids,
    )


def _professional_documents_tables_available() -> bool:
    with engine.begin() as conn:
        return table_exists(conn, "certificate_types") and table_exists(
            conn, "employee_certificates"
        )


def test_list_personnel_events_privileged(client, seed, privileged_headers):
    with engine.begin() as conn:
        if not table_exists(conn, "employee_events"):
            pytest.skip("employee_events table not available")

    resp = client.get("/directory/personnel-events", headers=privileged_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert isinstance(body["items"], list)
    if body["items"]:
        row = body["items"][0]
        for key in (
            "from_position_id",
            "from_position_name",
            "to_position_id",
            "to_position_name",
            "from_rate",
            "to_rate",
            "comment",
        ):
            assert key in row


def test_list_personnel_events_includes_transfer_position_and_rate_fields(
    client, seed, privileged_headers
):
    employee_id, _from_unit_id, to_unit_id, emp_ids, pos_ids, unit_ids = _make_null_from_transfer_fixture(
        seed
    )

    try:
        transfer = client.post(
            f"/directory/employees/{employee_id}/transfer",
            json={
                "to_org_unit_id": to_unit_id,
                "to_position_id": pos_ids[0],
                "effective_date": "2026-06-15",
                "comment": "Personnel journal enrichment test",
            },
            headers=privileged_headers,
        )
        assert transfer.status_code == 200, transfer.text

        resp = client.get(
            "/directory/personnel-events",
            params={"event_type": "TRANSFER", "limit": 200},
            headers=privileged_headers,
        )
        assert resp.status_code == 200, resp.text
        assert "TypeError" not in resp.text

        body = resp.json()
        row = next((item for item in body["items"] if item["employee_id"] == employee_id), None)
        assert row is not None, body["items"]
        assert row["event_type"] == "TRANSFER"
        assert row["from_position_id"] is None
        assert row["from_position_name"] is None
        assert row["from_rate"] is None
        assert row["to_position_id"] == pos_ids[0]
        assert isinstance(row["to_position_name"], str)
        assert row["to_position_name"]
        assert row["to_rate"] == 1.0
        assert row["comment"] == "Personnel journal enrichment test"
    finally:
        _cleanup_employees(emp_ids)
        _cleanup_positions(pos_ids)
        _cleanup_units(unit_ids)


def test_list_personnel_events_unprivileged_returns_403(client, seed):
    resp = client.get(
        "/directory/personnel-events",
        headers=auth_headers(seed["executor_user_id"]),
    )
    assert resp.status_code == 403


def test_professional_documents_availability(client, seed):
    expected = _professional_documents_tables_available()
    resp = client.get(
        "/directory/professional-documents/availability",
        headers=auth_headers(seed["initiator_user_id"]),
    )
    assert resp.status_code == 200
    assert resp.json() == {"available": expected}


def test_list_professional_documents_graceful_without_tables(client, seed, privileged_headers):
    resp = client.get("/directory/professional-documents", headers=privileged_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("available") is _professional_documents_tables_available()
    assert isinstance(body.get("items"), list)
    assert body.get("total") == len(body["items"])
    if not body["available"]:
        assert body["items"] == []
        assert body["total"] == 0


def test_list_professional_documents_with_tables_returns_rows(client, seed, privileged_headers):
    if not _professional_documents_tables_available():
        pytest.skip("professional documents tables not available")

    resp = client.get("/directory/professional-documents", headers=privileged_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("available") is True
    if body["items"]:
        row = body["items"][0]
        assert "employee_name" in row
        assert "status" in row
