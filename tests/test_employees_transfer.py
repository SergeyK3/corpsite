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


def _create_employee_without_position(
    conn,
    *,
    full_name: str,
    org_unit_id: int,
    is_active: bool = True,
) -> int:
    return insert_returning_id(
        conn,
        table="employees",
        id_col="employee_id",
        values={
            "full_name": full_name,
            "org_unit_id": int(org_unit_id),
            "position_id": None,
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


def _position_name(position_id: int) -> str:
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT name FROM public.positions WHERE position_id = :position_id"),
            {"position_id": int(position_id)},
        ).mappings().first()
    assert row is not None
    return str(row["name"])


def _create_linked_user(
    client,
    *,
    employee_id: int,
    role_id: int,
    headers: Dict[str, str],
) -> tuple[int, str]:
    login = f"pytest_xfer_{uuid4().hex[:10]}"
    create_user = client.post(
        "/directory/users",
        json={
            "employee_id": employee_id,
            "role_id": int(role_id),
            "login": login,
            "password": "SecretPass1",
        },
        headers=headers,
    )
    assert create_user.status_code == 201, create_user.text
    return int(create_user.json()["user_id"]), login


def _working_contact_user_ids(client, headers: Dict[str, str], **params) -> set[int]:
    resp = client.get("/directory/working-contacts", params=params, headers=headers)
    assert resp.status_code == 200, resp.text
    return {
        int(x.get("user_id") or x.get("id") or 0)
        for x in (resp.json().get("items") or [])
    }


def _make_three_unit_fixture(seed) -> tuple[int, int, int, int, List[int], List[int], List[int]]:
    """Employee in from_unit; to_unit and third_unit available for chained transfers."""
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
        third_unit_id = _create_unit_with_group(
            conn,
            name=f"pytest_xfer_third_{uuid4().hex[:8]}",
            group_id=group_id,
        )
        created_unit_ids.extend([to_unit_id, third_unit_id])

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
        int(third_unit_id),
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


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_working_contacts_reflects_transfer_unit_and_position(client, seed, privileged_headers):
    employee_id, from_unit_id, to_unit_id, emp_ids, pos_ids, unit_ids = _make_transfer_fixture(seed)
    new_position_name = _position_name(pos_ids[1])
    login: str | None = None

    try:
        created_user_id, login = _create_linked_user(
            client,
            employee_id=employee_id,
            role_id=int(seed["executor_role_id"]),
            headers=privileged_headers,
        )

        before_old = _working_contact_user_ids(
            client,
            privileged_headers,
            org_unit_id=from_unit_id,
        )
        before_new = _working_contact_user_ids(
            client,
            privileged_headers,
            org_unit_id=to_unit_id,
        )
        assert created_user_id in before_old
        assert created_user_id not in before_new

        transfer = client.post(
            f"/directory/employees/{employee_id}/transfer",
            json={
                "to_org_unit_id": to_unit_id,
                "to_position_id": pos_ids[1],
                "effective_date": "2026-06-15",
            },
            headers=privileged_headers,
        )
        assert transfer.status_code == 200, transfer.text

        after_old = _working_contact_user_ids(
            client,
            privileged_headers,
            org_unit_id=from_unit_id,
        )
        after_new = _working_contact_user_ids(
            client,
            privileged_headers,
            org_unit_id=to_unit_id,
        )
        assert created_user_id not in after_old
        assert created_user_id in after_new

        detail = client.get(
            f"/directory/working-contacts/{created_user_id}",
            headers=privileged_headers,
        )
        assert detail.status_code == 200, detail.text
        contact = detail.json()
        assert contact["org_unit_id"] == to_unit_id
        assert contact["position_id"] == pos_ids[1]
        assert contact["position_name"] == new_position_name
    finally:
        if login:
            _cleanup_users_by_logins([login])
        _cleanup_employees(emp_ids)
        _cleanup_positions(pos_ids)
        _cleanup_units(unit_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_transfer_inactive_employee_returns_409(client, seed, privileged_headers):
    employee_id, from_unit_id, to_unit_id, emp_ids, pos_ids, unit_ids = _make_transfer_fixture(seed)

    try:
        terminate = client.post(
            f"/directory/employees/{employee_id}/terminate",
            headers=privileged_headers,
        )
        assert terminate.status_code == 200, terminate.text

        resp = client.post(
            f"/directory/employees/{employee_id}/transfer",
            json={
                "to_org_unit_id": to_unit_id,
                "effective_date": "2026-06-15",
            },
            headers=privileged_headers,
        )
        assert resp.status_code == 409, resp.text
        assert resp.json()["detail"] == "Employee is inactive."
    finally:
        _cleanup_employees(emp_ids)
        _cleanup_positions(pos_ids)
        _cleanup_units(unit_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_correct_org_unit_on_inactive_employee_returns_200(client, seed, privileged_headers):
    employee_id, from_unit_id, to_unit_id, emp_ids, pos_ids, unit_ids = _make_transfer_fixture(seed)

    try:
        terminate = client.post(
            f"/directory/employees/{employee_id}/terminate",
            headers=privileged_headers,
        )
        assert terminate.status_code == 200, terminate.text

        resp = client.post(
            f"/directory/employees/{employee_id}/correct-org-unit",
            json={
                "to_org_unit_id": to_unit_id,
                "effective_date": "2026-06-01",
                "comment": "Fix org unit after import on terminated record",
            },
            headers=privileged_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["item"]["org_unit"]["unit_id"] == to_unit_id
        assert body["item"]["status"] == "inactive"
        assert body["event"]["event_type"] == "CORRECTION"
        assert body["event"]["from_org_unit_id"] == from_unit_id
        assert body["event"]["to_org_unit_id"] == to_unit_id
    finally:
        _cleanup_employees(emp_ids)
        _cleanup_positions(pos_ids)
        _cleanup_units(unit_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_employee_events_same_effective_date_orders_by_event_id_desc(client, seed, privileged_headers):
    employee_id, from_unit_id, to_unit_id, third_unit_id, emp_ids, pos_ids, unit_ids = _make_three_unit_fixture(
        seed
    )

    try:
        first = client.post(
            f"/directory/employees/{employee_id}/transfer",
            json={
                "to_org_unit_id": to_unit_id,
                "effective_date": "2026-06-15",
                "comment": "First transfer",
            },
            headers=privileged_headers,
        )
        assert first.status_code == 200, first.text
        first_event_id = int(first.json()["event"]["event_id"])

        second = client.post(
            f"/directory/employees/{employee_id}/transfer",
            json={
                "to_org_unit_id": third_unit_id,
                "effective_date": "2026-06-15",
                "comment": "Second transfer same date",
            },
            headers=privileged_headers,
        )
        assert second.status_code == 200, second.text
        second_event_id = int(second.json()["event"]["event_id"])

        assert second_event_id > first_event_id

        resp = client.get(
            f"/directory/employees/{employee_id}/events",
            headers=privileged_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] == 2
        assert [e["event_id"] for e in body["items"]] == [second_event_id, first_event_id]
        assert all(e["effective_date"] == "2026-06-15" for e in body["items"])
        assert body["items"][0]["to_org_unit_id"] == third_unit_id
        assert body["items"][1]["to_org_unit_id"] == to_unit_id
        assert body["items"][1]["from_org_unit_id"] == from_unit_id
    finally:
        _cleanup_employees(emp_ids)
        _cleanup_positions(pos_ids)
        _cleanup_units(unit_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_employee_events_pagination_and_type_filters(client, seed, privileged_headers):
    employee_id, from_unit_id, to_unit_id, third_unit_id, emp_ids, pos_ids, unit_ids = _make_three_unit_fixture(
        seed
    )

    try:
        transfer = client.post(
            f"/directory/employees/{employee_id}/transfer",
            json={
                "to_org_unit_id": to_unit_id,
                "effective_date": "2026-06-20",
            },
            headers=privileged_headers,
        )
        assert transfer.status_code == 200, transfer.text

        second_transfer = client.post(
            f"/directory/employees/{employee_id}/transfer",
            json={
                "to_org_unit_id": third_unit_id,
                "effective_date": "2026-06-25",
            },
            headers=privileged_headers,
        )
        assert second_transfer.status_code == 200, second_transfer.text

        correction = client.post(
            f"/directory/employees/{employee_id}/correct-org-unit",
            json={
                "to_org_unit_id": third_unit_id,
                "to_position_id": pos_ids[1],
                "effective_date": "2026-06-10",
                "comment": "Corrected position after data review",
            },
            headers=privileged_headers,
        )
        assert correction.status_code == 200, correction.text

        all_events = client.get(
            f"/directory/employees/{employee_id}/events",
            headers=privileged_headers,
        )
        assert all_events.status_code == 200, all_events.text
        assert all_events.json()["total"] == 3

        page_one = client.get(
            f"/directory/employees/{employee_id}/events",
            params={"limit": 1, "offset": 0},
            headers=privileged_headers,
        )
        assert page_one.status_code == 200, page_one.text
        page_one_body = page_one.json()
        assert page_one_body["total"] == 3
        assert len(page_one_body["items"]) == 1

        page_two = client.get(
            f"/directory/employees/{employee_id}/events",
            params={"limit": 1, "offset": 1},
            headers=privileged_headers,
        )
        assert page_two.status_code == 200, page_two.text
        page_two_body = page_two.json()
        assert page_two_body["total"] == 3
        assert len(page_two_body["items"]) == 1
        assert page_two_body["items"][0]["event_id"] != page_one_body["items"][0]["event_id"]

        page_three = client.get(
            f"/directory/employees/{employee_id}/events",
            params={"limit": 2, "offset": 1},
            headers=privileged_headers,
        )
        assert page_three.status_code == 200, page_three.text
        page_three_body = page_three.json()
        assert page_three_body["total"] == 3
        assert len(page_three_body["items"]) == 2

        transfers_only = client.get(
            f"/directory/employees/{employee_id}/events",
            params={"event_type": "TRANSFER"},
            headers=privileged_headers,
        )
        assert transfers_only.status_code == 200, transfers_only.text
        transfers_body = transfers_only.json()
        assert transfers_body["total"] == 2
        assert all(e["event_type"] == "TRANSFER" for e in transfers_body["items"])

        corrections_only = client.get(
            f"/directory/employees/{employee_id}/events",
            params={"event_type": "CORRECTION"},
            headers=privileged_headers,
        )
        assert corrections_only.status_code == 200, corrections_only.text
        corrections_body = corrections_only.json()
        assert corrections_body["total"] == 1
        assert corrections_body["items"][0]["event_type"] == "CORRECTION"
        assert corrections_body["items"][0]["from_org_unit_id"] == third_unit_id
        assert corrections_body["items"][0]["to_org_unit_id"] == third_unit_id
        assert corrections_body["items"][0]["to_position_id"] == pos_ids[1]
    finally:
        _cleanup_employees(emp_ids)
        _cleanup_positions(pos_ids)
        _cleanup_units(unit_ids)


def _make_null_position_transfer_fixture(seed) -> tuple[int, int, int, List[int], List[int], List[int]]:
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
            name=f"pytest_xfer_null_from_{uuid4().hex[:8]}",
            group_id=group_id,
        )
        created_unit_ids.append(to_unit_id)

        target_position_id = _create_position(conn, name=f"pytest_xfer_null_pos_{uuid4().hex[:8]}")
        created_position_ids.append(target_position_id)

        employee_id = _create_employee_without_position(
            conn,
            full_name=f"PytestTransferNullPos {uuid4().hex[:8]}",
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


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_transfer_employee_null_current_position_with_explicit_target_returns_200(
    client, seed, privileged_headers
):
    employee_id, from_unit_id, to_unit_id, emp_ids, pos_ids, unit_ids = _make_null_position_transfer_fixture(
        seed
    )

    try:
        resp = client.post(
            f"/directory/employees/{employee_id}/transfer",
            json={
                "to_org_unit_id": to_unit_id,
                "to_position_id": pos_ids[0],
                "effective_date": "2026-06-15",
            },
            headers=privileged_headers,
        )
        assert resp.status_code == 200, resp.text
        assert "TypeError" not in resp.text

        body = resp.json()
        assert body["item"]["org_unit"]["unit_id"] == to_unit_id
        assert body["item"]["position"]["id"] == pos_ids[0]
        assert body["event"]["event_type"] == "TRANSFER"
        assert body["event"]["from_org_unit_id"] == from_unit_id
        assert body["event"]["from_position_id"] is None
        assert body["event"]["to_org_unit_id"] == to_unit_id
        assert body["event"]["to_position_id"] == pos_ids[0]
    finally:
        _cleanup_employees(emp_ids)
        _cleanup_positions(pos_ids)
        _cleanup_units(unit_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_transfer_employee_null_current_position_without_target_returns_422(
    client, seed, privileged_headers
):
    employee_id, _from_unit_id, to_unit_id, emp_ids, pos_ids, unit_ids = _make_null_position_transfer_fixture(
        seed
    )

    try:
        resp = client.post(
            f"/directory/employees/{employee_id}/transfer",
            json={
                "to_org_unit_id": to_unit_id,
                "effective_date": "2026-06-15",
            },
            headers=privileged_headers,
        )
        assert resp.status_code == 422, resp.text
        assert "TypeError" not in resp.text
        assert resp.json()["detail"] == "Current position is missing; choose target position"
    finally:
        _cleanup_employees(emp_ids)
        _cleanup_positions(pos_ids)
        _cleanup_units(unit_ids)
