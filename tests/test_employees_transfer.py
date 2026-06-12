# tests/test_employees_transfer.py
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


def _create_unit_with_group(
    conn,
    *,
    name: str,
    group_id: int,
    parent_unit_id: Optional[int] = None,
) -> int:
    if not table_exists(conn, "org_units"):
        pytest.skip("org_units table not available")

    cols = get_columns(conn, "org_units")
    values: Dict[str, Any] = {"name": name}
    if "code" in cols:
        values["code"] = name
    if "group_id" in cols:
        values["group_id"] = int(group_id)
    if parent_unit_id is not None and "parent_unit_id" in cols:
        values["parent_unit_id"] = int(parent_unit_id)
    if "is_active" in cols:
        values["is_active"] = True

    return insert_returning_id(conn, table="org_units", id_col="unit_id", values=values)


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
    is_active: bool = True,
) -> int:
    return insert_returning_id(
        conn,
        table="employees",
        id_col="employee_id",
        values={
            "full_name": full_name,
            "org_unit_id": int(org_unit_id),
            "position_id": int(position_id),
            "employment_rate": 1.0,
            "is_active": is_active,
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


def _cleanup_users_by_logins(logins: List[str]) -> None:
    if not logins:
        return
    with engine.begin() as conn:
        if table_exists(conn, "users"):
            conn.execute(
                text("DELETE FROM public.users WHERE login = ANY(:logins)"),
                {"logins": logins},
            )


def _cleanup_employees(employee_ids: List[int]) -> None:
    if not employee_ids:
        return
    with engine.begin() as conn:
        _cleanup_employee_events(employee_ids)
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


def _cleanup_units(unit_ids: List[int]) -> None:
    if not unit_ids:
        return
    with engine.begin() as conn:
        if table_exists(conn, "org_units"):
            conn.execute(
                text("DELETE FROM public.org_units WHERE unit_id = ANY(:ids)"),
                {"ids": [int(x) for x in unit_ids]},
            )


def _make_transfer_fixture(seed) -> tuple[int, int, int, List[int], List[int], List[int]]:
    created_unit_ids: List[int] = []
    created_position_ids: List[int] = []
    created_employee_ids: List[int] = []

    with engine.begin() as conn:
        if not table_exists(conn, "employees"):
            pytest.skip("employees table not available")
        if not table_exists(conn, "employee_events"):
            pytest.skip("employee_events table not available")

        group_id = _find_group_id(conn)
        from_unit_id = int(seed["unit_id"])
        to_unit_id = _create_unit_with_group(
            conn,
            name=f"pytest_xfer_to_{uuid4().hex[:8]}",
            group_id=group_id,
        )
        created_unit_ids.append(to_unit_id)

        position_id = _create_position(conn, name=f"pytest_xfer_pos_{uuid4().hex[:8]}")
        created_position_ids.append(position_id)
        new_position_id = _create_position(conn, name=f"pytest_xfer_pos2_{uuid4().hex[:8]}")
        created_position_ids.append(new_position_id)

        employee_id = _create_employee(
            conn,
            full_name=f"PytestTransfer {uuid4().hex[:8]}",
            org_unit_id=from_unit_id,
            position_id=position_id,
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


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_transfer_employee_returns_item_and_event(client, seed, privileged_headers):
    employee_id, from_unit_id, to_unit_id, emp_ids, pos_ids, unit_ids = _make_transfer_fixture(seed)

    try:
        resp = client.post(
            f"/directory/employees/{employee_id}/transfer",
            json={
                "to_org_unit_id": to_unit_id,
                "to_position_id": pos_ids[1],
                "effective_date": "2026-06-15",
                "order_ref": "123-к",
                "comment": "Transfer test",
            },
            headers=privileged_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["item"]["org_unit"]["unit_id"] == to_unit_id
        assert body["item"]["position"]["id"] == pos_ids[1]
        assert body["event"]["event_type"] == "TRANSFER"
        assert body["event"]["from_org_unit_id"] == from_unit_id
        assert body["event"]["to_org_unit_id"] == to_unit_id
        assert body["event"]["order_ref"] == "123-к"

        with engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT org_unit_id, position_id
                    FROM public.employees
                    WHERE employee_id = :employee_id
                    """
                ),
                {"employee_id": employee_id},
            ).mappings().first()
        assert row is not None
        assert int(row["org_unit_id"]) == to_unit_id
        assert int(row["position_id"]) == pos_ids[1]
    finally:
        _cleanup_employees(emp_ids)
        _cleanup_positions(pos_ids)
        _cleanup_units(unit_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_transfer_employee_same_org_unit_returns_422(client, seed, privileged_headers):
    employee_id, from_unit_id, _to_unit_id, emp_ids, pos_ids, unit_ids = _make_transfer_fixture(seed)

    try:
        resp = client.post(
            f"/directory/employees/{employee_id}/transfer",
            json={
                "to_org_unit_id": from_unit_id,
                "effective_date": "2026-06-15",
            },
            headers=privileged_headers,
        )
        assert resp.status_code == 422, resp.text
    finally:
        _cleanup_employees(emp_ids)
        _cleanup_positions(pos_ids)
        _cleanup_units(unit_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_transfer_employee_unprivileged_returns_403(client, seed):
    employee_id, _from_unit_id, to_unit_id, emp_ids, pos_ids, unit_ids = _make_transfer_fixture(seed)

    try:
        resp = client.post(
            f"/directory/employees/{employee_id}/transfer",
            json={
                "to_org_unit_id": to_unit_id,
                "effective_date": "2026-06-15",
            },
            headers=auth_headers(seed["executor_user_id"]),
        )
        assert resp.status_code == 403, resp.text
    finally:
        _cleanup_employees(emp_ids)
        _cleanup_positions(pos_ids)
        _cleanup_units(unit_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_transfer_employee_with_linked_user_syncs_unit_id(client, seed, privileged_headers):
    employee_id, from_unit_id, to_unit_id, emp_ids, pos_ids, unit_ids = _make_transfer_fixture(seed)
    login = f"pytest_xfer_{uuid4().hex[:10]}"
    created_user_id: int | None = None

    try:
        create_user = client.post(
            "/directory/users",
            json={
                "employee_id": employee_id,
                "role_id": int(seed["executor_role_id"]),
                "login": login,
                "password": "SecretPass1",
            },
            headers=privileged_headers,
        )
        assert create_user.status_code == 201, create_user.text
        created_user_id = int(create_user.json()["user_id"])

        with engine.begin() as conn:
            before = conn.execute(
                text("SELECT unit_id FROM public.users WHERE user_id = :uid"),
                {"uid": created_user_id},
            ).mappings().first()
        assert before is not None
        assert int(before["unit_id"]) == from_unit_id

        resp = client.post(
            f"/directory/employees/{employee_id}/transfer",
            json={
                "to_org_unit_id": to_unit_id,
                "effective_date": "2026-06-15",
            },
            headers=privileged_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["item"]["user"]["user_id"] == created_user_id

        with engine.begin() as conn:
            after = conn.execute(
                text("SELECT unit_id, role_id FROM public.users WHERE user_id = :uid"),
                {"uid": created_user_id},
            ).mappings().first()
        assert after is not None
        assert int(after["unit_id"]) == to_unit_id
        assert int(after["role_id"]) == int(seed["executor_role_id"])
    finally:
        _cleanup_users_by_logins([login])
        _cleanup_employees(emp_ids)
        _cleanup_positions(pos_ids)
        _cleanup_units(unit_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_correct_org_unit_returns_correction_event(client, seed, privileged_headers):
    employee_id, from_unit_id, to_unit_id, emp_ids, pos_ids, unit_ids = _make_transfer_fixture(seed)

    try:
        resp = client.post(
            f"/directory/employees/{employee_id}/correct-org-unit",
            json={
                "to_org_unit_id": to_unit_id,
                "effective_date": "2026-06-01",
                "comment": "Import error fix",
            },
            headers=privileged_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["item"]["org_unit"]["unit_id"] == to_unit_id
        assert body["event"]["event_type"] == "CORRECTION"
        assert body["event"]["from_org_unit_id"] == from_unit_id
        assert body["event"]["comment"] == "Import error fix"
    finally:
        _cleanup_employees(emp_ids)
        _cleanup_positions(pos_ids)
        _cleanup_units(unit_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_employee_events_returns_history(client, seed, privileged_headers):
    employee_id, _from_unit_id, to_unit_id, emp_ids, pos_ids, unit_ids = _make_transfer_fixture(seed)

    try:
        transfer = client.post(
            f"/directory/employees/{employee_id}/transfer",
            json={
                "to_org_unit_id": to_unit_id,
                "effective_date": "2026-06-15",
            },
            headers=privileged_headers,
        )
        assert transfer.status_code == 200, transfer.text

        resp = client.get(
            f"/directory/employees/{employee_id}/events",
            headers=privileged_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] == 1
        assert len(body["items"]) == 1
        assert body["items"][0]["event_type"] == "TRANSFER"

        filtered = client.get(
            f"/directory/employees/{employee_id}/events",
            params={"event_type": "CORRECTION"},
            headers=privileged_headers,
        )
        assert filtered.status_code == 200, filtered.text
        assert filtered.json()["total"] == 0
    finally:
        _cleanup_employees(emp_ids)
        _cleanup_positions(pos_ids)
        _cleanup_units(unit_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_employee_events_unprivileged_returns_403(client, seed):
    employee_id, _from_unit_id, _to_unit_id, emp_ids, pos_ids, unit_ids = _make_transfer_fixture(seed)

    try:
        resp = client.get(
            f"/directory/employees/{employee_id}/events",
            headers=auth_headers(seed["executor_user_id"]),
        )
        assert resp.status_code == 403, resp.text
    finally:
        _cleanup_employees(emp_ids)
        _cleanup_positions(pos_ids)
        _cleanup_units(unit_ids)
