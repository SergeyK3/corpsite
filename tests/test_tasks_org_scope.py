# tests/test_tasks_org_scope.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.tasks_service import SYSTEM_ADMIN_ROLE_ID
from tests.conftest import (
    auth_headers,
    cleanup_task,
    create_role,
    create_task,
    get_columns,
    get_status_id,
    insert_returning_id,
    table_exists,
    utcnow,
)


def _list_tasks(client, user_id: int, **params):
    return client.get("/tasks", params=params, headers=auth_headers(user_id))


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


def _create_task_with_owner_unit(
    *,
    period_id: int,
    title: str,
    initiator_user_id: int,
    executor_role_id: int,
    assignment_scope: Optional[str],
    status_code: str,
    owner_unit_id: int,
) -> tuple[int, int]:
    with engine.begin() as conn:
        status_id = get_status_id(conn, status_code)
        now = utcnow()
        rt_cols = get_columns(conn, "regular_tasks")
        code_suffix = int(now.timestamp() * 1_000_000) % 1_000_000_000
        rt_values: Dict[str, Any] = {
            "title": title,
            "is_active": True,
            "schedule_type": "daily",
            "create_offset_days": 0,
            "executor_role_id": int(executor_role_id),
            "created_at": now,
            "updated_at": now,
        }
        if "code" in rt_cols:
            rt_values["code"] = f"pytest_org_scope_{code_suffix}"
        if "owner_unit_id" in rt_cols:
            rt_values["owner_unit_id"] = int(owner_unit_id)
        if "assignment_scope" in rt_cols:
            rt_values["assignment_scope"] = assignment_scope or "unit"
        if "schedule_params" in rt_cols:
            rt_values["schedule_params"] = "{}"

        regular_task_id = insert_returning_id(
            conn,
            table="regular_tasks",
            id_col="regular_task_id",
            values=rt_values,
        )

        t_cols = get_columns(conn, "tasks")
        t_values: Dict[str, Any] = {
            "period_id": int(period_id),
            "regular_task_id": int(regular_task_id),
            "title": title,
            "description": None,
            "initiator_user_id": int(initiator_user_id),
            "created_by_user_id": int(initiator_user_id),
            "approver_user_id": int(initiator_user_id),
            "executor_role_id": int(executor_role_id),
            "assignment_scope": assignment_scope or "unit",
            "status_id": int(status_id),
            "task_kind": "regular",
            "requires_report": True,
            "requires_approval": True,
            "source_kind": "regular_task",
            "created_at": now,
            "updated_at": now,
        }
        task_id = insert_returning_id(conn, table="tasks", id_col="task_id", values=t_values)
        return int(task_id), int(regular_task_id)


def _cleanup_task_with_template(task_id: int, regular_task_id: int) -> None:
    cleanup_task(task_id)
    with engine.begin() as conn:
        if table_exists(conn, "regular_tasks"):
            conn.execute(
                text("DELETE FROM public.regular_tasks WHERE regular_task_id = :id"),
                {"id": int(regular_task_id)},
            )


def _cleanup_units(unit_ids: List[int]) -> None:
    if not unit_ids:
        return
    with engine.begin() as conn:
        if not table_exists(conn, "org_units"):
            return
        cols = get_columns(conn, "org_units")
        if "unit_id" not in cols:
            return
        conn.execute(
            text("DELETE FROM public.org_units WHERE unit_id = ANY(:ids)"),
            {"ids": [int(x) for x in unit_ids]},
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_tasks_without_org_group_id_unchanged(client, seed):
    unique_title = "PytestOrgScopeNoGroupFilter"
    task_id: Optional[int] = None

    try:
        task_id = create_task(
            period_id=seed["period_id"],
            title=unique_title,
            initiator_user_id=seed["initiator_user_id"],
            executor_role_id=seed["executor_role_id"],
            assignment_scope=seed["assignment_scope"],
            status_code="WAITING_REPORT",
            unit_id=seed["unit_id"],
        )

        resp = _list_tasks(
            client,
            seed["executor_user_id"],
            scope="mine",
            limit=50,
            status_filter="active",
            search=unique_title,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] == 1
        assert len(body["items"]) == 1
        assert int(body["items"][0]["task_id"]) == task_id
    finally:
        if task_id is not None:
            cleanup_task(task_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_tasks_filters_by_org_group_id(client, seed):
    unique_a = "PytestOrgScopeGroupA"
    unique_b = "PytestOrgScopeGroupB"
    task_ids: List[int] = []
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

            unit_a = _create_unit_with_group(conn, name="pytest_org_scope_a", group_id=group_a)
            unit_b = _create_unit_with_group(conn, name="pytest_org_scope_b", group_id=group_b)
            created_unit_ids.extend([unit_a, unit_b])

        task_a, template_a = _create_task_with_owner_unit(
            period_id=seed["period_id"],
            title=unique_a,
            initiator_user_id=seed["initiator_user_id"],
            executor_role_id=seed["executor_role_id"],
            assignment_scope=seed["assignment_scope"],
            status_code="WAITING_REPORT",
            owner_unit_id=unit_a,
        )
        task_b, template_b = _create_task_with_owner_unit(
            period_id=seed["period_id"],
            title=unique_b,
            initiator_user_id=seed["initiator_user_id"],
            executor_role_id=seed["executor_role_id"],
            assignment_scope=seed["assignment_scope"],
            status_code="WAITING_REPORT",
            owner_unit_id=unit_b,
        )
        task_ids.extend([task_a, task_b])
        template_ids.extend([template_a, template_b])

        filtered_a = _list_tasks(
            client,
            int(admin_user_id),
            scope="team",
            org_group_id=group_a,
            search=unique_a,
            status_filter="active",
        )
        assert filtered_a.status_code == 200, filtered_a.text
        body_a = filtered_a.json()
        assert body_a["total"] == 1
        assert int(body_a["items"][0]["task_id"]) == task_ids[0]

        filtered_b = _list_tasks(
            client,
            int(admin_user_id),
            scope="team",
            org_group_id=group_b,
            search=unique_b,
            status_filter="active",
        )
        assert filtered_b.status_code == 200, filtered_b.text
        body_b = filtered_b.json()
        assert body_b["total"] == 1
        assert int(body_b["items"][0]["task_id"]) == task_ids[1]

        cross = _list_tasks(
            client,
            int(admin_user_id),
            scope="team",
            org_group_id=group_a,
            search=unique_b,
            status_filter="active",
        )
        assert cross.status_code == 200, cross.text
        assert cross.json()["total"] == 0
    finally:
        for task_id, template_id in zip(task_ids, template_ids):
            _cleanup_task_with_template(task_id, template_id)
        _cleanup_units(created_unit_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_tasks_org_group_and_unit_combined_with_and(client, seed):
    unique_child = "PytestOrgScopeAndChild"
    unique_sibling = "PytestOrgScopeAndSibling"
    task_ids: List[int] = []
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
                name="pytest_org_scope_parent",
                group_id=group_id,
            )
            child_unit = _create_unit_with_group(
                conn,
                name="pytest_org_scope_child",
                group_id=group_id,
                parent_unit_id=parent_unit,
            )
            sibling_unit = _create_unit_with_group(
                conn,
                name="pytest_org_scope_sibling",
                group_id=group_id,
            )
            created_unit_ids.extend([parent_unit, child_unit, sibling_unit])

        task_child, template_child = _create_task_with_owner_unit(
            period_id=seed["period_id"],
            title=unique_child,
            initiator_user_id=seed["initiator_user_id"],
            executor_role_id=seed["executor_role_id"],
            assignment_scope=seed["assignment_scope"],
            status_code="WAITING_REPORT",
            owner_unit_id=child_unit,
        )
        task_sibling, template_sibling = _create_task_with_owner_unit(
            period_id=seed["period_id"],
            title=unique_sibling,
            initiator_user_id=seed["initiator_user_id"],
            executor_role_id=seed["executor_role_id"],
            assignment_scope=seed["assignment_scope"],
            status_code="WAITING_REPORT",
            owner_unit_id=sibling_unit,
        )
        task_ids.extend([task_child, task_sibling])
        template_ids.extend([template_child, template_sibling])

        with engine.begin() as conn:
            group_id = _unit_group_id(conn, parent_unit) or group_id

        combined = _list_tasks(
            client,
            int(admin_user_id),
            scope="team",
            org_group_id=group_id,
            org_unit_id=parent_unit,
            status_filter="active",
            search="PytestOrgScopeAnd",
        )
        assert combined.status_code == 200, combined.text
        combined_ids = {int(x["task_id"]) for x in combined.json()["items"]}
        assert task_ids[0] in combined_ids
        assert task_ids[1] not in combined_ids

        group_only = _list_tasks(
            client,
            int(admin_user_id),
            scope="team",
            org_group_id=group_id,
            status_filter="active",
            search="PytestOrgScopeAnd",
        )
        assert group_only.status_code == 200, group_only.text
        group_ids_found = {int(x["task_id"]) for x in group_only.json()["items"]}
        assert task_ids[0] in group_ids_found
        assert task_ids[1] in group_ids_found
    finally:
        for task_id, template_id in zip(task_ids, template_ids):
            _cleanup_task_with_template(task_id, template_id)
        _cleanup_units(created_unit_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_org_filter_ignores_executor_role_id_change(client, seed):
    unique_title = "PytestOrgScopeExecutorRole"
    task_ids: List[int] = []
    template_ids: List[int] = []
    created_unit_ids: List[int] = []
    created_role_ids: List[int] = []

    try:
        with engine.begin() as conn:
            group_ids = _find_distinct_group_ids(conn, limit=1)
            group_id = group_ids[0] if group_ids else 1
            unit_id = _create_unit_with_group(
                conn,
                name="pytest_org_scope_executor",
                group_id=group_id,
            )
            created_unit_ids.append(unit_id)

            alt_role_id = create_role(conn, "pytest_org_scope_alt_executor")
            created_role_ids.append(alt_role_id)

        task_a, template_a = _create_task_with_owner_unit(
            period_id=seed["period_id"],
            title=f"{unique_title} A",
            initiator_user_id=seed["initiator_user_id"],
            executor_role_id=seed["executor_role_id"],
            assignment_scope=seed["assignment_scope"],
            status_code="WAITING_APPROVAL",
            owner_unit_id=unit_id,
        )
        task_b, template_b = _create_task_with_owner_unit(
            period_id=seed["period_id"],
            title=f"{unique_title} B",
            initiator_user_id=seed["initiator_user_id"],
            executor_role_id=alt_role_id,
            assignment_scope=seed["assignment_scope"],
            status_code="WAITING_APPROVAL",
            owner_unit_id=unit_id,
        )
        task_ids.extend([task_a, task_b])
        template_ids.extend([template_a, template_b])

        with engine.begin() as conn:
            group_id = _unit_group_id(conn, unit_id) or group_id

        list_user_id = seed["initiator_user_id"]

        before = _list_tasks(
            client,
            list_user_id,
            scope="mine",
            org_group_id=group_id,
            search=unique_title,
            status_filter="active",
        )
        assert before.status_code == 200, before.text
        before_ids = sorted(int(x["task_id"]) for x in before.json()["items"])
        assert before_ids == sorted(task_ids)

        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE public.tasks
                    SET executor_role_id = :new_role_id
                    WHERE task_id = :task_id
                    """
                ),
                {"new_role_id": int(seed["initiator_role_id"]), "task_id": int(task_ids[0])},
            )

        after = _list_tasks(
            client,
            list_user_id,
            scope="mine",
            org_group_id=group_id,
            search=unique_title,
            status_filter="active",
        )
        assert after.status_code == 200, after.text
        after_ids = sorted(int(x["task_id"]) for x in after.json()["items"])
        assert after_ids == sorted(task_ids)
    finally:
        for task_id, template_id in zip(task_ids, template_ids):
            _cleanup_task_with_template(task_id, template_id)
        _cleanup_units(created_unit_ids)
        with engine.begin() as conn:
            if table_exists(conn, "roles") and created_role_ids:
                conn.execute(
                    text("DELETE FROM public.roles WHERE role_id = ANY(:ids)"),
                    {"ids": created_role_ids},
                )
