# tests/test_working_contacts_org_scope.py
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


def _list_working_contacts(client, privileged_headers, **params):
    return client.get(
        "/directory/working-contacts",
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


def _create_working_contact_user(
    conn,
    *,
    full_name: str,
    unit_id: int,
    role_id: int,
) -> int:
    return create_user(
        conn,
        full_name=full_name,
        role_id=role_id,
        unit_id=unit_id,
    )


def _cleanup_users(user_ids: List[int]) -> None:
    if not user_ids:
        return
    with engine.begin() as conn:
        safe_delete_many(conn, "users", "user_id", user_ids)


def _cleanup_units(unit_ids: List[int]) -> None:
    if not unit_ids:
        return
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM public.org_units WHERE unit_id = ANY(:ids)"),
            {"ids": [int(x) for x in unit_ids]},
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_working_contacts_without_org_group_id_unchanged(client, seed, privileged_headers):
    unique_name = "PytestWcOrgScopeNoGroupFilter"
    created_user_ids: List[int] = []
    role_id: Optional[int] = None

    try:
        with engine.begin() as conn:
            role_id = create_role(conn, "pytest_wc_org_scope_no_group")
            created_user_ids.append(
                _create_working_contact_user(
                    conn,
                    full_name=unique_name,
                    unit_id=int(seed["unit_id"]),
                    role_id=role_id,
                )
            )

        resp = _list_working_contacts(
            client,
            privileged_headers,
            q=unique_name,
            active_only=False,
            limit=50,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] >= 1
        ids = {int(x["user_id"]) for x in body["items"]}
        assert created_user_ids[0] in ids
    finally:
        _cleanup_users(created_user_ids)
        if role_id is not None:
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM public.roles WHERE role_id = :role_id"),
                    {"role_id": int(role_id)},
                )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_working_contacts_filters_by_org_group_id(client, seed, privileged_headers):
    unique_a = "PytestWcOrgScopeGroupA"
    unique_b = "PytestWcOrgScopeGroupB"
    created_user_ids: List[int] = []
    created_unit_ids: List[int] = []
    role_id: Optional[int] = None

    try:
        with engine.begin() as conn:
            role_id = create_role(conn, "pytest_wc_org_scope_group")
            group_ids = _find_distinct_group_ids(conn, limit=2)
            if len(group_ids) < 2:
                group_a = 1
                group_b = 3
            else:
                group_a, group_b = group_ids[0], group_ids[1]

            unit_a = _create_unit_with_group(conn, name="pytest_wc_org_scope_a", group_id=group_a)
            unit_b = _create_unit_with_group(conn, name="pytest_wc_org_scope_b", group_id=group_b)
            created_unit_ids.extend([unit_a, unit_b])

            created_user_ids.append(
                _create_working_contact_user(
                    conn,
                    full_name=unique_a,
                    unit_id=unit_a,
                    role_id=role_id,
                )
            )
            created_user_ids.append(
                _create_working_contact_user(
                    conn,
                    full_name=unique_b,
                    unit_id=unit_b,
                    role_id=role_id,
                )
            )

        filtered_a = _list_working_contacts(
            client,
            privileged_headers,
            org_group_id=group_a,
            q=unique_a,
            active_only=False,
        )
        assert filtered_a.status_code == 200, filtered_a.text
        body_a = filtered_a.json()
        assert body_a["total"] == 1
        assert int(body_a["items"][0]["user_id"]) == created_user_ids[0]

        filtered_b = _list_working_contacts(
            client,
            privileged_headers,
            org_group_id=group_b,
            q=unique_b,
            active_only=False,
        )
        assert filtered_b.status_code == 200, filtered_b.text
        body_b = filtered_b.json()
        assert body_b["total"] == 1
        assert int(body_b["items"][0]["user_id"]) == created_user_ids[1]

        cross = _list_working_contacts(
            client,
            privileged_headers,
            org_group_id=group_a,
            q=unique_b,
            active_only=False,
        )
        assert cross.status_code == 200, cross.text
        assert cross.json()["total"] == 0
    finally:
        _cleanup_users(created_user_ids)
        _cleanup_units(created_unit_ids)
        if role_id is not None:
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM public.roles WHERE role_id = :role_id"),
                    {"role_id": int(role_id)},
                )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_working_contacts_filters_by_org_unit_id_subtree(client, seed, privileged_headers):
    unique_name = "PytestWcOrgScopeSubtreeChild"
    created_user_ids: List[int] = []
    created_unit_ids: List[int] = []
    role_id: Optional[int] = None

    try:
        with engine.begin() as conn:
            cols = get_columns(conn, "org_units")
            if "parent_unit_id" not in cols:
                pytest.skip("org_units.parent_unit_id not available")

            role_id = create_role(conn, "pytest_wc_org_scope_subtree")
            group_ids = _find_distinct_group_ids(conn, limit=1)
            group_id = group_ids[0] if group_ids else 1

            parent_unit = _create_unit_with_group(
                conn,
                name="pytest_wc_org_scope_parent",
                group_id=group_id,
            )
            child_unit = _create_unit_with_group(
                conn,
                name="pytest_wc_org_scope_child",
                group_id=group_id,
                parent_unit_id=parent_unit,
            )
            created_unit_ids.extend([parent_unit, child_unit])

            created_user_ids.append(
                _create_working_contact_user(
                    conn,
                    full_name=unique_name,
                    unit_id=child_unit,
                    role_id=role_id,
                )
            )

        filtered = _list_working_contacts(
            client,
            privileged_headers,
            org_unit_id=parent_unit,
            q=unique_name,
            active_only=False,
        )
        assert filtered.status_code == 200, filtered.text
        body = filtered.json()
        assert body["total"] == 1
        assert int(body["items"][0]["user_id"]) == created_user_ids[0]
    finally:
        _cleanup_users(created_user_ids)
        _cleanup_units(created_unit_ids)
        if role_id is not None:
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM public.roles WHERE role_id = :role_id"),
                    {"role_id": int(role_id)},
                )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_working_contacts_org_group_and_unit_combined_with_and(client, seed, privileged_headers):
    unique_child = "PytestWcOrgScopeAndChild"
    unique_sibling = "PytestWcOrgScopeAndSibling"
    created_user_ids: List[int] = []
    created_unit_ids: List[int] = []
    role_id: Optional[int] = None

    try:
        with engine.begin() as conn:
            cols = get_columns(conn, "org_units")
            if "parent_unit_id" not in cols:
                pytest.skip("org_units.parent_unit_id not available")

            role_id = create_role(conn, "pytest_wc_org_scope_and")
            group_ids = _find_distinct_group_ids(conn, limit=1)
            group_id = group_ids[0] if group_ids else 1

            parent_unit = _create_unit_with_group(
                conn,
                name="pytest_wc_org_scope_and_parent",
                group_id=group_id,
            )
            child_unit = _create_unit_with_group(
                conn,
                name="pytest_wc_org_scope_and_child",
                group_id=group_id,
                parent_unit_id=parent_unit,
            )
            sibling_unit = _create_unit_with_group(
                conn,
                name="pytest_wc_org_scope_and_sibling",
                group_id=group_id,
            )
            created_unit_ids.extend([parent_unit, child_unit, sibling_unit])

            created_user_ids.append(
                _create_working_contact_user(
                    conn,
                    full_name=unique_child,
                    unit_id=child_unit,
                    role_id=role_id,
                )
            )
            created_user_ids.append(
                _create_working_contact_user(
                    conn,
                    full_name=unique_sibling,
                    unit_id=sibling_unit,
                    role_id=role_id,
                )
            )

            group_id = _unit_group_id(conn, parent_unit) or group_id

        combined = _list_working_contacts(
            client,
            privileged_headers,
            org_group_id=group_id,
            org_unit_id=parent_unit,
            q="PytestWcOrgScopeAnd",
            active_only=False,
        )
        assert combined.status_code == 200, combined.text
        combined_ids = {int(x["user_id"]) for x in combined.json()["items"]}
        assert created_user_ids[0] in combined_ids
        assert created_user_ids[1] not in combined_ids

        group_only = _list_working_contacts(
            client,
            privileged_headers,
            org_group_id=group_id,
            q="PytestWcOrgScopeAnd",
            active_only=False,
        )
        assert group_only.status_code == 200, group_only.text
        group_ids_found = {int(x["user_id"]) for x in group_only.json()["items"]}
        assert created_user_ids[0] in group_ids_found
        assert created_user_ids[1] in group_ids_found
    finally:
        _cleanup_users(created_user_ids)
        _cleanup_units(created_unit_ids)
        if role_id is not None:
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM public.roles WHERE role_id = :role_id"),
                    {"role_id": int(role_id)},
                )
