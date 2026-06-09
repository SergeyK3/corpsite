# tests/test_positions_org_scope.py
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import (
    auth_headers,
    get_columns,
    insert_returning_id,
    table_exists,
)


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


def _list_positions(client, privileged_headers, **params):
    return client.get(
        "/directory/positions",
        params=params,
        headers=privileged_headers,
    )


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


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


def _find_distinct_group_ids(conn, *, limit: int = 2) -> List[int]:
    rows = (
        conn.execute(
            text(
                """
                SELECT DISTINCT group_id
                FROM public.org_units
                WHERE group_id IS NOT NULL
                  AND group_id >= 1
                ORDER BY group_id
                LIMIT :limit
                """
            ),
            {"limit": int(limit)},
        )
        .mappings()
        .all()
    )
    return [int(r["group_id"]) for r in rows if r.get("group_id") is not None]


def _unit_group_id(conn, unit_id: int) -> Optional[int]:
    row = (
        conn.execute(
            text(
                """
                SELECT group_id
                FROM public.org_units
                WHERE unit_id = :unit_id
                LIMIT 1
                """
            ),
            {"unit_id": int(unit_id)},
        )
        .mappings()
        .first()
    )
    if not row or row.get("group_id") is None:
        return None
    return int(row["group_id"])


def _create_position(conn, *, name: str, category: str = "other") -> int:
    if not table_exists(conn, "positions"):
        pytest.skip("positions table not available")

    cols = get_columns(conn, "positions")
    values: Dict[str, Any] = {"name": name}
    if "category" in cols:
        values["category"] = category

    return insert_returning_id(conn, table="positions", id_col="position_id", values=values)


def _insert_employee_with_position(
    conn,
    *,
    full_name: str,
    org_unit_id: int,
    position_id: int,
) -> None:
    if not table_exists(conn, "employees"):
        pytest.skip("employees table not available")

    cols = get_columns(conn, "employees")
    values: Dict[str, Any] = {
        "full_name": full_name,
        "org_unit_id": int(org_unit_id),
        "position_id": int(position_id),
        "is_active": True,
    }
    if "employment_rate" in cols:
        values["employment_rate"] = 1.00
    if "date_from" in cols:
        values["date_from"] = date.today()

    filtered = {k: v for k, v in values.items() if k in cols}
    col_list = ", ".join(filtered.keys())
    bind_list = ", ".join(f":{k}" for k in filtered.keys())
    conn.execute(
        text(
            f"""
            INSERT INTO public.employees ({col_list})
            VALUES ({bind_list})
            """
        ),
        filtered,
    )


def _position_names_from_response(body: Dict[str, Any]) -> set[str]:
    return {str(x.get("name") or "") for x in body.get("items", [])}


def _cleanup_employees(full_names: List[str]) -> None:
    if not full_names:
        return
    with engine.begin() as conn:
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


def _cleanup_units(unit_ids: List[int]) -> None:
    if not unit_ids:
        return
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM public.org_units WHERE unit_id = ANY(:ids)"),
            {"ids": [int(x) for x in unit_ids]},
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_positions_without_org_group_id_unchanged(client, seed, privileged_headers):
    unique_position = "PytestPosOrgScopeNoGroupFilter"
    created_position_ids: List[int] = []
    created_employee_names: List[str] = []

    try:
        with engine.begin() as conn:
            position_id = _create_position(conn, name=unique_position)
            created_position_ids.append(position_id)
            _insert_employee_with_position(
                conn,
                full_name="PytestPosOrgScopeNoGroupFilterEmp",
                org_unit_id=int(seed["unit_id"]),
                position_id=position_id,
            )
            created_employee_names.append("PytestPosOrgScopeNoGroupFilterEmp")

        resp = _list_positions(
            client,
            privileged_headers,
            q=unique_position,
            limit=50,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] >= 1
        assert unique_position in _position_names_from_response(body)
    finally:
        _cleanup_employees(created_employee_names)
        _cleanup_positions(created_position_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_positions_filters_by_org_group_id(client, seed, privileged_headers):
    unique_a = "PytestPosOrgScopeGroupA"
    unique_b = "PytestPosOrgScopeGroupB"
    created_position_ids: List[int] = []
    created_employee_names: List[str] = []
    created_unit_ids: List[int] = []

    try:
        with engine.begin() as conn:
            group_ids = _find_distinct_group_ids(conn, limit=2)
            if len(group_ids) < 2:
                group_a = 1
                group_b = 3
            else:
                group_a, group_b = group_ids[0], group_ids[1]

            unit_a = _create_unit_with_group(conn, name="pytest_pos_org_scope_a", group_id=group_a)
            unit_b = _create_unit_with_group(conn, name="pytest_pos_org_scope_b", group_id=group_b)
            created_unit_ids.extend([unit_a, unit_b])

            position_a = _create_position(conn, name=unique_a)
            position_b = _create_position(conn, name=unique_b)
            created_position_ids.extend([position_a, position_b])

            _insert_employee_with_position(
                conn,
                full_name="PytestPosOrgScopeGroupAEmp",
                org_unit_id=unit_a,
                position_id=position_a,
            )
            _insert_employee_with_position(
                conn,
                full_name="PytestPosOrgScopeGroupBEmp",
                org_unit_id=unit_b,
                position_id=position_b,
            )
            created_employee_names.extend(
                ["PytestPosOrgScopeGroupAEmp", "PytestPosOrgScopeGroupBEmp"]
            )

        filtered_a = _list_positions(
            client,
            privileged_headers,
            org_group_id=group_a,
            q=unique_a,
        )
        assert filtered_a.status_code == 200, filtered_a.text
        assert filtered_a.json()["total"] == 1
        assert unique_a in _position_names_from_response(filtered_a.json())

        filtered_b = _list_positions(
            client,
            privileged_headers,
            org_group_id=group_b,
            q=unique_b,
        )
        assert filtered_b.status_code == 200, filtered_b.text
        assert filtered_b.json()["total"] == 1
        assert unique_b in _position_names_from_response(filtered_b.json())

        cross = _list_positions(
            client,
            privileged_headers,
            org_group_id=group_a,
            q=unique_b,
        )
        assert cross.status_code == 200, cross.text
        assert cross.json()["total"] == 0
    finally:
        _cleanup_employees(created_employee_names)
        _cleanup_positions(created_position_ids)
        _cleanup_units(created_unit_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_positions_filters_by_org_unit_id_subtree(client, seed, privileged_headers):
    unique_position = "PytestPosOrgScopeSubtreeChild"
    created_position_ids: List[int] = []
    created_employee_names: List[str] = []
    created_unit_ids: List[int] = []

    try:
        with engine.begin() as conn:
            cols = get_columns(conn, "org_units")
            if "parent_unit_id" not in cols:
                pytest.skip("org_units.parent_unit_id not available")

            group_ids = _find_distinct_group_ids(conn, limit=1)
            group_id = group_ids[0] if group_ids else 1

            parent_unit = _create_unit_with_group(
                conn,
                name="pytest_pos_org_scope_parent",
                group_id=group_id,
            )
            child_unit = _create_unit_with_group(
                conn,
                name="pytest_pos_org_scope_child",
                group_id=group_id,
                parent_unit_id=parent_unit,
            )
            sibling_unit = _create_unit_with_group(
                conn,
                name="pytest_pos_org_scope_sibling",
                group_id=group_id,
            )
            created_unit_ids.extend([parent_unit, child_unit, sibling_unit])

            position_id = _create_position(conn, name=unique_position)
            created_position_ids.append(position_id)
            _insert_employee_with_position(
                conn,
                full_name="PytestPosOrgScopeSubtreeEmp",
                org_unit_id=child_unit,
                position_id=position_id,
            )
            created_employee_names.append("PytestPosOrgScopeSubtreeEmp")

        filtered_parent = _list_positions(
            client,
            privileged_headers,
            org_unit_id=parent_unit,
            q=unique_position,
        )
        assert filtered_parent.status_code == 200, filtered_parent.text
        assert filtered_parent.json()["total"] == 1
        assert unique_position in _position_names_from_response(filtered_parent.json())

        filtered_sibling = _list_positions(
            client,
            privileged_headers,
            org_unit_id=sibling_unit,
            q=unique_position,
        )
        assert filtered_sibling.status_code == 200, filtered_sibling.text
        assert filtered_sibling.json()["total"] == 0
    finally:
        _cleanup_employees(created_employee_names)
        _cleanup_positions(created_position_ids)
        _cleanup_units(created_unit_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_positions_org_group_id_and_org_unit_id_and(client, seed, privileged_headers):
    unique_child = "PytestPosOrgScopeAndChild"
    unique_sibling = "PytestPosOrgScopeAndSibling"
    created_position_ids: List[int] = []
    created_employee_names: List[str] = []
    created_unit_ids: List[int] = []

    try:
        with engine.begin() as conn:
            cols = get_columns(conn, "org_units")
            if "parent_unit_id" not in cols:
                pytest.skip("org_units.parent_unit_id not available")

            group_ids = _find_distinct_group_ids(conn, limit=1)
            group_id = group_ids[0] if group_ids else 1

            parent_unit = _create_unit_with_group(
                conn,
                name="pytest_pos_org_scope_and_parent",
                group_id=group_id,
            )
            child_unit = _create_unit_with_group(
                conn,
                name="pytest_pos_org_scope_and_child",
                group_id=group_id,
                parent_unit_id=parent_unit,
            )
            sibling_unit = _create_unit_with_group(
                conn,
                name="pytest_pos_org_scope_and_sibling",
                group_id=group_id,
            )
            created_unit_ids.extend([parent_unit, child_unit, sibling_unit])

            position_child = _create_position(conn, name=unique_child)
            position_sibling = _create_position(conn, name=unique_sibling)
            created_position_ids.extend([position_child, position_sibling])

            _insert_employee_with_position(
                conn,
                full_name="PytestPosOrgScopeAndChildEmp",
                org_unit_id=child_unit,
                position_id=position_child,
            )
            _insert_employee_with_position(
                conn,
                full_name="PytestPosOrgScopeAndSiblingEmp",
                org_unit_id=sibling_unit,
                position_id=position_sibling,
            )
            created_employee_names.extend(
                ["PytestPosOrgScopeAndChildEmp", "PytestPosOrgScopeAndSiblingEmp"]
            )

            group_id = _unit_group_id(conn, parent_unit) or group_id

        combined = _list_positions(
            client,
            privileged_headers,
            org_group_id=group_id,
            org_unit_id=parent_unit,
            q="PytestPosOrgScopeAnd",
        )
        assert combined.status_code == 200, combined.text
        combined_names = _position_names_from_response(combined.json())
        assert unique_child in combined_names
        assert unique_sibling not in combined_names

        group_only = _list_positions(
            client,
            privileged_headers,
            org_group_id=group_id,
            q="PytestPosOrgScopeAnd",
        )
        assert group_only.status_code == 200, group_only.text
        group_only_names = _position_names_from_response(group_only.json())
        assert unique_child in group_only_names
        assert unique_sibling in group_only_names
    finally:
        _cleanup_employees(created_employee_names)
        _cleanup_positions(created_position_ids)
        _cleanup_units(created_unit_ids)
