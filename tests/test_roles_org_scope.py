# tests/test_roles_org_scope.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import (
    auth_headers,
    create_role,
    create_user,
    get_columns,
    insert_returning_id,
    safe_delete_many,
    table_exists,
)


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


def _list_roles(client, privileged_headers, **params):
    return client.get(
        "/directory/roles",
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


def _role_codes_from_response(body: Dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for item in body.get("items", []):
        code = str(item.get("role_code") or item.get("code") or "").strip()
        if code:
            out.add(code)
    return out


def _cleanup_users(user_ids: List[int]) -> None:
    if not user_ids:
        return
    with engine.begin() as conn:
        safe_delete_many(conn, "users", "user_id", user_ids)


def _cleanup_roles(role_ids: List[int]) -> None:
    if not role_ids:
        return
    with engine.begin() as conn:
        safe_delete_many(conn, "roles", "role_id", role_ids)


def _cleanup_units(unit_ids: List[int]) -> None:
    if not unit_ids:
        return
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM public.org_units WHERE unit_id = ANY(:ids)"),
            {"ids": [int(x) for x in unit_ids]},
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_roles_without_org_group_id_unchanged(client, seed, privileged_headers):
    unique_role = "PytestRoleOrgScopeNoGroupFilter"
    created_role_ids: List[int] = []
    created_user_ids: List[int] = []

    try:
        with engine.begin() as conn:
            role_id = create_role(conn, unique_role)
            created_role_ids.append(role_id)
            created_user_ids.append(
                create_user(
                    conn,
                    full_name="PytestRoleOrgScopeNoGroupFilterUser",
                    role_id=role_id,
                    unit_id=int(seed["unit_id"]),
                )
            )

        resp = _list_roles(
            client,
            privileged_headers,
            q=unique_role,
            limit=50,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] >= 1
        assert unique_role in _role_codes_from_response(body)
    finally:
        _cleanup_users(created_user_ids)
        _cleanup_roles(created_role_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_roles_filters_by_org_group_id(client, seed, privileged_headers):
    unique_a = "PytestRoleOrgScopeGroupA"
    unique_b = "PytestRoleOrgScopeGroupB"
    created_role_ids: List[int] = []
    created_user_ids: List[int] = []
    created_unit_ids: List[int] = []

    try:
        with engine.begin() as conn:
            group_ids = _find_distinct_group_ids(conn, limit=2)
            if len(group_ids) < 2:
                group_a = 1
                group_b = 3
            else:
                group_a, group_b = group_ids[0], group_ids[1]

            unit_a = _create_unit_with_group(conn, name="pytest_role_org_scope_a", group_id=group_a)
            unit_b = _create_unit_with_group(conn, name="pytest_role_org_scope_b", group_id=group_b)
            created_unit_ids.extend([unit_a, unit_b])

            role_a = create_role(conn, unique_a)
            role_b = create_role(conn, unique_b)
            created_role_ids.extend([role_a, role_b])

            created_user_ids.append(
                create_user(
                    conn,
                    full_name="PytestRoleOrgScopeGroupAUser",
                    role_id=role_a,
                    unit_id=unit_a,
                )
            )
            created_user_ids.append(
                create_user(
                    conn,
                    full_name="PytestRoleOrgScopeGroupBUser",
                    role_id=role_b,
                    unit_id=unit_b,
                )
            )

        filtered_a = _list_roles(
            client,
            privileged_headers,
            org_group_id=group_a,
            q=unique_a,
        )
        assert filtered_a.status_code == 200, filtered_a.text
        assert filtered_a.json()["total"] == 1
        assert unique_a in _role_codes_from_response(filtered_a.json())

        filtered_b = _list_roles(
            client,
            privileged_headers,
            org_group_id=group_b,
            q=unique_b,
        )
        assert filtered_b.status_code == 200, filtered_b.text
        assert filtered_b.json()["total"] == 1
        assert unique_b in _role_codes_from_response(filtered_b.json())

        cross = _list_roles(
            client,
            privileged_headers,
            org_group_id=group_a,
            q=unique_b,
        )
        assert cross.status_code == 200, cross.text
        assert cross.json()["total"] == 0
    finally:
        _cleanup_users(created_user_ids)
        _cleanup_roles(created_role_ids)
        _cleanup_units(created_unit_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_roles_filters_by_org_unit_id_subtree(client, seed, privileged_headers):
    unique_role = "PytestRoleOrgScopeSubtreeChild"
    created_role_ids: List[int] = []
    created_user_ids: List[int] = []
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
                name="pytest_role_org_scope_parent",
                group_id=group_id,
            )
            child_unit = _create_unit_with_group(
                conn,
                name="pytest_role_org_scope_child",
                group_id=group_id,
                parent_unit_id=parent_unit,
            )
            sibling_unit = _create_unit_with_group(
                conn,
                name="pytest_role_org_scope_sibling",
                group_id=group_id,
            )
            created_unit_ids.extend([parent_unit, child_unit, sibling_unit])

            role_id = create_role(conn, unique_role)
            created_role_ids.append(role_id)
            created_user_ids.append(
                create_user(
                    conn,
                    full_name="PytestRoleOrgScopeSubtreeUser",
                    role_id=role_id,
                    unit_id=child_unit,
                )
            )

        filtered_parent = _list_roles(
            client,
            privileged_headers,
            org_unit_id=parent_unit,
            q=unique_role,
        )
        assert filtered_parent.status_code == 200, filtered_parent.text
        assert filtered_parent.json()["total"] == 1
        assert unique_role in _role_codes_from_response(filtered_parent.json())

        filtered_sibling = _list_roles(
            client,
            privileged_headers,
            org_unit_id=sibling_unit,
            q=unique_role,
        )
        assert filtered_sibling.status_code == 200, filtered_sibling.text
        assert filtered_sibling.json()["total"] == 0
    finally:
        _cleanup_users(created_user_ids)
        _cleanup_roles(created_role_ids)
        _cleanup_units(created_unit_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_roles_org_group_id_and_org_unit_id_and(client, seed, privileged_headers):
    unique_child = "PytestRoleOrgScopeAndChild"
    unique_sibling = "PytestRoleOrgScopeAndSibling"
    created_role_ids: List[int] = []
    created_user_ids: List[int] = []
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
                name="pytest_role_org_scope_and_parent",
                group_id=group_id,
            )
            child_unit = _create_unit_with_group(
                conn,
                name="pytest_role_org_scope_and_child",
                group_id=group_id,
                parent_unit_id=parent_unit,
            )
            sibling_unit = _create_unit_with_group(
                conn,
                name="pytest_role_org_scope_and_sibling",
                group_id=group_id,
            )
            created_unit_ids.extend([parent_unit, child_unit, sibling_unit])

            role_child = create_role(conn, unique_child)
            role_sibling = create_role(conn, unique_sibling)
            created_role_ids.extend([role_child, role_sibling])

            created_user_ids.append(
                create_user(
                    conn,
                    full_name="PytestRoleOrgScopeAndChildUser",
                    role_id=role_child,
                    unit_id=child_unit,
                )
            )
            created_user_ids.append(
                create_user(
                    conn,
                    full_name="PytestRoleOrgScopeAndSiblingUser",
                    role_id=role_sibling,
                    unit_id=sibling_unit,
                )
            )

            group_id = _unit_group_id(conn, parent_unit) or group_id

        combined = _list_roles(
            client,
            privileged_headers,
            org_group_id=group_id,
            org_unit_id=parent_unit,
            q="PytestRoleOrgScopeAnd",
        )
        assert combined.status_code == 200, combined.text
        combined_codes = _role_codes_from_response(combined.json())
        assert unique_child in combined_codes
        assert unique_sibling not in combined_codes

        group_only = _list_roles(
            client,
            privileged_headers,
            org_group_id=group_id,
            q="PytestRoleOrgScopeAnd",
        )
        assert group_only.status_code == 200, group_only.text
        group_only_codes = _role_codes_from_response(group_only.json())
        assert unique_child in group_only_codes
        assert unique_sibling in group_only_codes
    finally:
        _cleanup_users(created_user_ids)
        _cleanup_roles(created_role_ids)
        _cleanup_units(created_unit_ids)
