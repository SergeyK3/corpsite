# tests/test_org_units_org_scope.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.tasks_service import SYSTEM_ADMIN_ROLE_ID
from tests.conftest import (
    auth_headers,
    get_columns,
    insert_returning_id,
    table_exists,
)


def _list_org_units_flat(client, user_id: int, **params):
    return client.get(
        "/directory/org-units",
        params=params,
        headers=auth_headers(user_id),
    )


def _org_units_tree(client, user_id: int, **params):
    return client.get(
        "/directory/org-units/tree",
        params=params,
        headers=auth_headers(user_id),
    )


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _admin_user_id(conn) -> int:
    row = conn.execute(
        text(
            """
            SELECT user_id
            FROM public.users
            WHERE role_id = :role_id
              AND COALESCE(is_active, TRUE) = TRUE
            LIMIT 1
            """
        ),
        {"role_id": int(SYSTEM_ADMIN_ROLE_ID)},
    ).first()
    if row:
        return int(row[0])
    return 1


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


def _cleanup_units(unit_ids: List[int]) -> None:
    if not unit_ids:
        return
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM public.org_units WHERE unit_id = ANY(:ids)"),
            {"ids": [int(x) for x in unit_ids]},
        )


def _flat_unit_ids(body: Dict[str, Any]) -> set[int]:
    items = body.get("items") or []
    out: set[int] = set()
    for row in items:
        raw = row.get("unit_id") if row.get("unit_id") is not None else row.get("id")
        if raw is not None:
            out.add(int(raw))
    return out


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_org_units_without_org_filter_unchanged(client, seed):
    admin_user_id: Optional[int] = None

    with engine.begin() as conn:
        admin_user_id = _admin_user_id(conn)

    baseline = _list_org_units_flat(client, int(admin_user_id), include_inactive=True)
    assert baseline.status_code == 200, baseline.text
    baseline_ids = _flat_unit_ids(baseline.json())

    repeat = _list_org_units_flat(client, int(admin_user_id), include_inactive=True)
    assert repeat.status_code == 200, repeat.text
    assert _flat_unit_ids(repeat.json()) == baseline_ids
    assert int(seed["unit_id"]) in baseline_ids


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_org_units_filters_by_org_group_id(client, seed):
    created_unit_ids: List[int] = []
    admin_user_id: Optional[int] = None

    try:
        with engine.begin() as conn:
            admin_user_id = _admin_user_id(conn)
            group_ids = _find_distinct_group_ids(conn, limit=2)
            if len(group_ids) < 2:
                group_a, group_b = 1, 3
            else:
                group_a, group_b = group_ids[0], group_ids[1]

            unit_a = _create_unit_with_group(conn, name="pytest_ou_org_scope_a", group_id=group_a)
            unit_b = _create_unit_with_group(conn, name="pytest_ou_org_scope_b", group_id=group_b)
            created_unit_ids.extend([unit_a, unit_b])

        filtered_a = _list_org_units_flat(
            client,
            int(admin_user_id),
            org_group_id=group_a,
            include_inactive=True,
        )
        assert filtered_a.status_code == 200, filtered_a.text
        ids_a = _flat_unit_ids(filtered_a.json())
        assert unit_a in ids_a
        assert unit_b not in ids_a

        filtered_b = _list_org_units_flat(
            client,
            int(admin_user_id),
            org_group_id=group_b,
            include_inactive=True,
        )
        assert filtered_b.status_code == 200, filtered_b.text
        ids_b = _flat_unit_ids(filtered_b.json())
        assert unit_b in ids_b
        assert unit_a not in ids_b
    finally:
        _cleanup_units(created_unit_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_org_units_filters_by_org_unit_id_subtree(client, seed):
    created_unit_ids: List[int] = []
    admin_user_id: Optional[int] = None

    try:
        with engine.begin() as conn:
            cols = get_columns(conn, "org_units")
            if "parent_unit_id" not in cols:
                pytest.skip("org_units.parent_unit_id not available")

            admin_user_id = _admin_user_id(conn)
            group_ids = _find_distinct_group_ids(conn, limit=1)
            group_id = group_ids[0] if group_ids else 1

            parent_unit = _create_unit_with_group(
                conn,
                name="pytest_ou_org_scope_parent",
                group_id=group_id,
            )
            child_unit = _create_unit_with_group(
                conn,
                name="pytest_ou_org_scope_child",
                group_id=group_id,
                parent_unit_id=parent_unit,
            )
            sibling_unit = _create_unit_with_group(
                conn,
                name="pytest_ou_org_scope_sibling",
                group_id=group_id,
            )
            created_unit_ids.extend([parent_unit, child_unit, sibling_unit])

        filtered = _list_org_units_flat(
            client,
            int(admin_user_id),
            org_unit_id=parent_unit,
            include_inactive=True,
        )
        assert filtered.status_code == 200, filtered.text
        ids = _flat_unit_ids(filtered.json())
        assert parent_unit in ids
        assert child_unit in ids
        assert sibling_unit not in ids
    finally:
        _cleanup_units(created_unit_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_org_units_org_group_and_unit_combined_with_and(client, seed):
    created_unit_ids: List[int] = []
    admin_user_id: Optional[int] = None

    try:
        with engine.begin() as conn:
            cols = get_columns(conn, "org_units")
            if "parent_unit_id" not in cols:
                pytest.skip("org_units.parent_unit_id not available")

            admin_user_id = _admin_user_id(conn)
            group_ids = _find_distinct_group_ids(conn, limit=2)
            if len(group_ids) < 2:
                group_a, group_b = 1, 3
            else:
                group_a, group_b = group_ids[0], group_ids[1]

            parent_unit = _create_unit_with_group(
                conn,
                name="pytest_ou_org_scope_and_parent",
                group_id=group_a,
            )
            child_unit = _create_unit_with_group(
                conn,
                name="pytest_ou_org_scope_and_child",
                group_id=group_a,
                parent_unit_id=parent_unit,
            )
            sibling_unit = _create_unit_with_group(
                conn,
                name="pytest_ou_org_scope_and_sibling",
                group_id=group_b,
            )
            created_unit_ids.extend([parent_unit, child_unit, sibling_unit])

            group_id = _unit_group_id(conn, parent_unit) or group_a

        combined = _list_org_units_flat(
            client,
            int(admin_user_id),
            org_group_id=group_id,
            org_unit_id=parent_unit,
            include_inactive=True,
        )
        assert combined.status_code == 200, combined.text
        ids = _flat_unit_ids(combined.json())
        assert child_unit in ids
        assert sibling_unit not in ids

        group_only = _list_org_units_flat(
            client,
            int(admin_user_id),
            org_group_id=group_b,
            include_inactive=True,
        )
        assert group_only.status_code == 200, group_only.text
        ids_b = _flat_unit_ids(group_only.json())
        assert sibling_unit in ids_b
        assert child_unit not in ids_b
    finally:
        _cleanup_units(created_unit_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_org_units_rbac_not_bypassed_by_org_group_id(client, seed, monkeypatch):
    created_unit_ids: List[int] = []
    admin_user_id: Optional[int] = None

    monkeypatch.setenv("DIRECTORY_RBAC_MODE", "dept")

    try:
        with engine.begin() as conn:
            admin_user_id = _admin_user_id(conn)
            group_ids = _find_distinct_group_ids(conn, limit=1)
            group_id = group_ids[0] if group_ids else 3

            outsider_unit = _create_unit_with_group(
                conn,
                name="pytest_ou_org_scope_rbac_outsider",
                group_id=group_id,
            )
            created_unit_ids.append(outsider_unit)

        scoped_resp = _list_org_units_flat(
            client,
            int(seed["executor_user_id"]),
            org_group_id=group_id,
            include_inactive=True,
        )
        assert scoped_resp.status_code == 200, scoped_resp.text
        assert outsider_unit not in _flat_unit_ids(scoped_resp.json())

        admin_resp = _list_org_units_flat(
            client,
            int(admin_user_id),
            org_group_id=group_id,
            include_inactive=True,
        )
        assert admin_resp.status_code == 200, admin_resp.text
        assert outsider_unit in _flat_unit_ids(admin_resp.json())
    finally:
        _cleanup_units(created_unit_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_org_units_tree_root_id_matches_org_unit_id_filter(client, seed):
    created_unit_ids: List[int] = []
    admin_user_id: Optional[int] = None

    try:
        with engine.begin() as conn:
            cols = get_columns(conn, "org_units")
            if "parent_unit_id" not in cols:
                pytest.skip("org_units.parent_unit_id not available")

            admin_user_id = _admin_user_id(conn)
            group_ids = _find_distinct_group_ids(conn, limit=1)
            group_id = group_ids[0] if group_ids else 1

            parent_unit = _create_unit_with_group(
                conn,
                name="pytest_ou_tree_root_parent",
                group_id=group_id,
            )
            child_unit = _create_unit_with_group(
                conn,
                name="pytest_ou_tree_root_child",
                group_id=group_id,
                parent_unit_id=parent_unit,
            )
            created_unit_ids.extend([parent_unit, child_unit])

        tree_resp = _org_units_tree(
            client,
            int(admin_user_id),
            org_unit_id=parent_unit,
            include_inactive=True,
        )
        assert tree_resp.status_code == 200, tree_resp.text
        body = tree_resp.json()
        assert body.get("root_id") == parent_unit
        items = body.get("items") or []
        assert len(items) == 1
        assert str(items[0].get("id")) == str(parent_unit)
        child_ids = {str(c.get("id")) for c in (items[0].get("children") or [])}
        assert str(child_unit) in child_ids
    finally:
        _cleanup_units(created_unit_ids)
