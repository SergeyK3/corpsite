# tests/test_regular_tasks_org_scope.py
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.tasks_service import SYSTEM_ADMIN_ROLE_ID
from tests.conftest import (
    auth_headers,
    create_unit,
    create_user,
    get_columns,
    insert_returning_id,
    table_exists,
    utcnow,
)


def _list_regular_tasks(client, user_id: int, **params):
    return client.get("/regular-tasks", params=params, headers=auth_headers(user_id))


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

    unit_id = create_unit(conn, "pytest_rt_org_scope_admin_unit")
    return create_user(
        conn,
        full_name="Pytest RT Org Scope Admin",
        role_id=int(SYSTEM_ADMIN_ROLE_ID),
        unit_id=unit_id,
    )


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


def _insert_regular_task_template(
    conn,
    *,
    title: str,
    owner_unit_id: Optional[int] = None,
    executor_role_id: int = 1,
) -> int:
    cols = get_columns(conn, "regular_tasks")
    now = utcnow()
    code_suffix = int(now.timestamp() * 1_000_000) % 1_000_000_000
    values: Dict[str, Any] = {
        "title": title,
        "is_active": True,
        "schedule_type": "weekly",
        "create_offset_days": 0,
        "executor_role_id": int(executor_role_id),
        "created_at": now,
        "updated_at": now,
    }
    insert_cols = ["title", "is_active", "schedule_type", "create_offset_days", "executor_role_id"]
    if "code" in cols:
        values["code"] = f"pytest_rt_org_scope_{code_suffix}"
        insert_cols.append("code")
    if "created_at" in cols:
        insert_cols.append("created_at")
    if "updated_at" in cols:
        insert_cols.append("updated_at")
    if "schedule_params" in cols:
        values["schedule_params"] = json.dumps({"byweekday": [4], "time": "00:00"}, ensure_ascii=False)
        insert_cols.append("schedule_params")
    if "assignment_scope" in cols:
        values["assignment_scope"] = "functional"
        insert_cols.append("assignment_scope")
    if owner_unit_id is not None and "owner_unit_id" in cols:
        values["owner_unit_id"] = int(owner_unit_id)
        insert_cols.append("owner_unit_id")

    values_sql = ", ".join(
        "CAST(:schedule_params AS jsonb)" if c == "schedule_params" else f":{c}" for c in insert_cols
    )
    cols_sql = ", ".join(insert_cols)
    return int(
        conn.execute(
            text(
                f"""
                INSERT INTO public.regular_tasks ({cols_sql})
                VALUES ({values_sql})
                RETURNING regular_task_id
                """
            ),
            values,
        ).scalar_one()
    )


def _cleanup_templates(template_ids: List[int]) -> None:
    if not template_ids:
        return
    with engine.begin() as conn:
        if table_exists(conn, "regular_tasks"):
            conn.execute(
                text("DELETE FROM public.regular_tasks WHERE regular_task_id = ANY(:ids)"),
                {"ids": [int(x) for x in template_ids]},
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


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_regular_tasks_without_org_group_id_unchanged(client, seed):
    unique_title = "PytestRtOrgScopeNoGroupFilter"
    template_ids: List[int] = []
    admin_user_id: Optional[int] = None

    try:
        with engine.begin() as conn:
            admin_user_id = _admin_user_id(conn)
            template_ids.append(
                _insert_regular_task_template(
                    conn,
                    title=unique_title,
                    owner_unit_id=seed["unit_id"],
                    executor_role_id=seed["executor_role_id"],
                )
            )

        resp = _list_regular_tasks(
            client,
            int(admin_user_id),
            status="all",
            q=unique_title,
            limit=50,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] >= 1
        ids = {int(x["regular_task_id"]) for x in body["items"]}
        assert template_ids[0] in ids
    finally:
        _cleanup_templates(template_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_regular_tasks_filters_by_org_group_id(client, seed):
    unique_a = "PytestRtOrgScopeGroupA"
    unique_b = "PytestRtOrgScopeGroupB"
    template_ids: List[int] = []
    created_unit_ids: List[int] = []
    admin_user_id: Optional[int] = None

    try:
        with engine.begin() as conn:
            admin_user_id = _admin_user_id(conn)
            group_ids = _find_distinct_group_ids(conn, limit=2)
            if len(group_ids) < 2:
                group_a = 1
                group_b = 3
            else:
                group_a, group_b = group_ids[0], group_ids[1]

            unit_a = _create_unit_with_group(conn, name="pytest_rt_org_scope_a", group_id=group_a)
            unit_b = _create_unit_with_group(conn, name="pytest_rt_org_scope_b", group_id=group_b)
            created_unit_ids.extend([unit_a, unit_b])

            template_ids.append(
                _insert_regular_task_template(
                    conn,
                    title=unique_a,
                    owner_unit_id=unit_a,
                    executor_role_id=seed["executor_role_id"],
                )
            )
            template_ids.append(
                _insert_regular_task_template(
                    conn,
                    title=unique_b,
                    owner_unit_id=unit_b,
                    executor_role_id=seed["executor_role_id"],
                )
            )

        filtered_a = _list_regular_tasks(
            client,
            int(admin_user_id),
            status="all",
            org_group_id=group_a,
            q=unique_a,
        )
        assert filtered_a.status_code == 200, filtered_a.text
        body_a = filtered_a.json()
        assert body_a["total"] == 1
        assert int(body_a["items"][0]["regular_task_id"]) == template_ids[0]

        filtered_b = _list_regular_tasks(
            client,
            int(admin_user_id),
            status="all",
            org_group_id=group_b,
            q=unique_b,
        )
        assert filtered_b.status_code == 200, filtered_b.text
        body_b = filtered_b.json()
        assert body_b["total"] == 1
        assert int(body_b["items"][0]["regular_task_id"]) == template_ids[1]

        cross = _list_regular_tasks(
            client,
            int(admin_user_id),
            status="all",
            org_group_id=group_a,
            q=unique_b,
        )
        assert cross.status_code == 200, cross.text
        assert cross.json()["total"] == 0
    finally:
        _cleanup_templates(template_ids)
        _cleanup_units(created_unit_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_regular_tasks_filters_by_org_unit_id_subtree(client, seed):
    unique_child = "PytestRtOrgScopeSubtreeChild"
    template_ids: List[int] = []
    created_unit_ids: List[int] = []
    admin_user_id: Optional[int] = None

    try:
        with engine.begin() as conn:
            admin_user_id = _admin_user_id(conn)
            cols = get_columns(conn, "org_units")
            if "parent_unit_id" not in cols:
                pytest.skip("org_units.parent_unit_id not available")

            group_ids = _find_distinct_group_ids(conn, limit=1)
            group_id = group_ids[0] if group_ids else 1

            parent_unit = _create_unit_with_group(
                conn,
                name="pytest_rt_org_scope_parent",
                group_id=group_id,
            )
            child_unit = _create_unit_with_group(
                conn,
                name="pytest_rt_org_scope_child",
                group_id=group_id,
                parent_unit_id=parent_unit,
            )
            created_unit_ids.extend([parent_unit, child_unit])

            template_ids.append(
                _insert_regular_task_template(
                    conn,
                    title=unique_child,
                    owner_unit_id=child_unit,
                    executor_role_id=seed["executor_role_id"],
                )
            )

        filtered = _list_regular_tasks(
            client,
            int(admin_user_id),
            status="all",
            org_unit_id=parent_unit,
            q=unique_child,
        )
        assert filtered.status_code == 200, filtered.text
        body = filtered.json()
        assert body["total"] == 1
        assert int(body["items"][0]["regular_task_id"]) == template_ids[0]
    finally:
        _cleanup_templates(template_ids)
        _cleanup_units(created_unit_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_regular_tasks_org_group_and_unit_combined_with_and(client, seed):
    unique_child = "PytestRtOrgScopeAndChild"
    unique_sibling = "PytestRtOrgScopeAndSibling"
    template_ids: List[int] = []
    created_unit_ids: List[int] = []
    admin_user_id: Optional[int] = None

    try:
        with engine.begin() as conn:
            admin_user_id = _admin_user_id(conn)
            cols = get_columns(conn, "org_units")
            if "parent_unit_id" not in cols:
                pytest.skip("org_units.parent_unit_id not available")

            group_ids = _find_distinct_group_ids(conn, limit=1)
            group_id = group_ids[0] if group_ids else 1

            parent_unit = _create_unit_with_group(
                conn,
                name="pytest_rt_org_scope_and_parent",
                group_id=group_id,
            )
            child_unit = _create_unit_with_group(
                conn,
                name="pytest_rt_org_scope_and_child",
                group_id=group_id,
                parent_unit_id=parent_unit,
            )
            sibling_unit = _create_unit_with_group(
                conn,
                name="pytest_rt_org_scope_and_sibling",
                group_id=group_id,
            )
            created_unit_ids.extend([parent_unit, child_unit, sibling_unit])

            template_ids.append(
                _insert_regular_task_template(
                    conn,
                    title=unique_child,
                    owner_unit_id=child_unit,
                    executor_role_id=seed["executor_role_id"],
                )
            )
            template_ids.append(
                _insert_regular_task_template(
                    conn,
                    title=unique_sibling,
                    owner_unit_id=sibling_unit,
                    executor_role_id=seed["executor_role_id"],
                )
            )

            group_id = _unit_group_id(conn, parent_unit) or group_id

        combined = _list_regular_tasks(
            client,
            int(admin_user_id),
            status="all",
            org_group_id=group_id,
            org_unit_id=parent_unit,
            q="PytestRtOrgScopeAnd",
        )
        assert combined.status_code == 200, combined.text
        combined_ids = {int(x["regular_task_id"]) for x in combined.json()["items"]}
        assert template_ids[0] in combined_ids
        assert template_ids[1] not in combined_ids

        group_only = _list_regular_tasks(
            client,
            int(admin_user_id),
            status="all",
            org_group_id=group_id,
            q="PytestRtOrgScopeAnd",
        )
        assert group_only.status_code == 200, group_only.text
        group_ids_found = {int(x["regular_task_id"]) for x in group_only.json()["items"]}
        assert template_ids[0] in group_ids_found
        assert template_ids[1] in group_ids_found
    finally:
        _cleanup_templates(template_ids)
        _cleanup_units(created_unit_ids)
