# tests/test_employee_correct.py
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
    employment_rate: float = 1.0,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
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
    return insert_returning_id(
        conn,
        table="employees",
        id_col="employee_id",
        values=values,
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


def _make_fixture(seed) -> tuple[int, int, int, int, str, List[int], List[int], List[int]]:
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
            name=f"pytest_correct_to_{uuid4().hex[:8]}",
            group_id=group_id,
        )
        created_unit_ids.append(to_unit_id)

        position_id = _create_position(conn, name=f"pytest_correct_pos_{uuid4().hex[:8]}")
        created_position_ids.append(position_id)
        alt_position_id = _create_position(conn, name=f"pytest_correct_pos2_{uuid4().hex[:8]}")
        created_position_ids.append(alt_position_id)

        full_name = f"PytestCorrect {uuid4().hex[:8]}"
        employee_id = _create_employee(
            conn,
            full_name=full_name,
            org_unit_id=from_unit_id,
            position_id=position_id,
            date_from="2024-01-15",
        )
        created_employee_ids.append(employee_id)

    return (
        int(employee_id),
        int(from_unit_id),
        int(to_unit_id),
        int(position_id),
        int(alt_position_id),
        full_name,
        created_employee_ids,
        created_position_ids,
        created_unit_ids,
    )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_correct_general_returns_correction_event_with_metadata(client, seed, privileged_headers):
    employee_id, _from, _to, _pos, _alt_pos, full_name, emp_ids, pos_ids, unit_ids = _make_fixture(seed)

    try:
        resp = client.post(
            f"/directory/employees/{employee_id}/correct",
            json={
                "domain": "general",
                "full_name": f"{full_name} Updated",
                "effective_date": "2026-07-01",
                "reason": "Опечатка в ФИО",
                "comment": "Исправлено по паспорту",
            },
            headers=privileged_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["item"]["fio"] == f"{full_name} Updated"
        assert body["event"]["event_type"] == "CORRECTION"
        metadata = body["event"]["metadata"]
        assert metadata["domain"] == "general"
        assert metadata["reason"] == "Опечатка в ФИО"
        assert metadata["changes"]["full_name"]["from"] == full_name
        assert metadata["changes"]["full_name"]["to"] == f"{full_name} Updated"
        assert body["event"]["comment"] == "Исправлено по паспорту"

        history = client.get(
            f"/directory/employees/{employee_id}/events",
            params={"event_type": "CORRECTION"},
            headers=privileged_headers,
        )
        assert history.status_code == 200, history.text
        assert history.json()["total"] == 1
        assert history.json()["items"][0]["metadata"]["domain"] == "general"
    finally:
        _cleanup_employees(emp_ids)
        _cleanup_positions(pos_ids)
        _cleanup_units(unit_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_correct_assignment_returns_correction_event_with_metadata(client, seed, privileged_headers):
    employee_id, from_unit_id, to_unit_id, position_id, alt_position_id, _name, emp_ids, pos_ids, unit_ids = (
        _make_fixture(seed)
    )

    try:
        resp = client.post(
            f"/directory/employees/{employee_id}/correct",
            json={
                "domain": "assignment",
                "org_unit_id": to_unit_id,
                "position_id": alt_position_id,
                "employment_rate": 0.5,
                "date_from": "2024-02-01",
                "date_to": None,
                "effective_date": "2026-07-01",
                "reason": "Ошибка импорта",
                "comment": "Сверка с приказом",
            },
            headers=privileged_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["item"]["org_unit"]["unit_id"] == to_unit_id
        assert body["item"]["position"]["id"] == alt_position_id
        assert float(body["item"]["rate"]) == 0.5
        assert body["item"]["date_from"] == "2024-02-01"

        metadata = body["event"]["metadata"]
        assert metadata["domain"] == "assignment"
        assert metadata["reason"] == "Ошибка импорта"
        assert metadata["changes"]["org_unit_id"]["from"] == from_unit_id
        assert metadata["changes"]["org_unit_id"]["to"] == to_unit_id
        assert metadata["changes"]["position_id"]["from"] == position_id
        assert metadata["changes"]["position_id"]["to"] == alt_position_id
        assert metadata["changes"]["employment_rate"]["from"] == 1.0
        assert metadata["changes"]["employment_rate"]["to"] == 0.5
        assert metadata["changes"]["date_from"]["from"] == "2024-01-15"
        assert metadata["changes"]["date_from"]["to"] == "2024-02-01"
    finally:
        _cleanup_employees(emp_ids)
        _cleanup_positions(pos_ids)
        _cleanup_units(unit_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_correct_assignment_null_date_from_date_to(client, seed, privileged_headers):
    employee_id, from_unit_id, _to, position_id, _alt, _name, emp_ids, pos_ids, unit_ids = _make_fixture(seed)

    try:
        resp = client.post(
            f"/directory/employees/{employee_id}/correct",
            json={
                "domain": "assignment",
                "org_unit_id": from_unit_id,
                "position_id": position_id,
                "employment_rate": 1.0,
                "date_from": None,
                "date_to": None,
                "effective_date": "2026-07-01",
                "reason": "Сброс дат",
                "comment": "Даты неизвестны",
            },
            headers=privileged_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["item"]["date_from"] is None
        assert body["item"]["date_to"] is None
        changes = body["event"]["metadata"]["changes"]
        assert changes["date_from"]["from"] == "2024-01-15"
        assert changes["date_from"]["to"] is None
    finally:
        _cleanup_employees(emp_ids)
        _cleanup_positions(pos_ids)
        _cleanup_units(unit_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_correct_general_no_changes_returns_422(client, seed, privileged_headers):
    employee_id, _from, _to, _pos, _alt, full_name, emp_ids, pos_ids, unit_ids = _make_fixture(seed)

    try:
        resp = client.post(
            f"/directory/employees/{employee_id}/correct",
            json={
                "domain": "general",
                "full_name": full_name,
                "effective_date": "2026-07-01",
                "reason": "Проверка",
                "comment": "Без изменений",
            },
            headers=privileged_headers,
        )
        assert resp.status_code == 422, resp.text
        assert resp.json()["detail"] == "No changes detected."
    finally:
        _cleanup_employees(emp_ids)
        _cleanup_positions(pos_ids)
        _cleanup_units(unit_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_correct_general_without_comment_returns_422(client, seed, privileged_headers):
    employee_id, _from, _to, _pos, _alt, full_name, emp_ids, pos_ids, unit_ids = _make_fixture(seed)

    try:
        resp = client.post(
            f"/directory/employees/{employee_id}/correct",
            json={
                "domain": "general",
                "full_name": f"{full_name} X",
                "effective_date": "2026-07-01",
                "reason": "Проверка",
                "comment": "   ",
            },
            headers=privileged_headers,
        )
        assert resp.status_code == 422, resp.text
        assert resp.json()["detail"] == "comment is required."
    finally:
        _cleanup_employees(emp_ids)
        _cleanup_positions(pos_ids)
        _cleanup_units(unit_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_correct_assignment_no_changes_returns_422(client, seed, privileged_headers):
    employee_id, from_unit_id, _to, position_id, _alt, _name, emp_ids, pos_ids, unit_ids = _make_fixture(seed)

    try:
        resp = client.post(
            f"/directory/employees/{employee_id}/correct",
            json={
                "domain": "assignment",
                "org_unit_id": from_unit_id,
                "position_id": position_id,
                "employment_rate": 1.0,
                "date_from": "2024-01-15",
                "date_to": None,
                "effective_date": "2026-07-01",
                "reason": "Проверка",
                "comment": "Без изменений",
            },
            headers=privileged_headers,
        )
        assert resp.status_code == 422, resp.text
        assert resp.json()["detail"] == "No changes detected."
    finally:
        _cleanup_employees(emp_ids)
        _cleanup_positions(pos_ids)
        _cleanup_units(unit_ids)
