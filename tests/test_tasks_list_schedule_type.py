from __future__ import annotations

from typing import Any, Dict, Optional

import pytest
from sqlalchemy import text

from tests.conftest import auth_headers, cleanup_task, engine, get_columns, get_status_id, insert_returning_id, table_exists, utcnow


def _db_available() -> bool:
    try:
        with engine.begin() as conn:
            conn.execute(text("SELECT 1"))
            return table_exists(conn, "tasks") and table_exists(conn, "regular_tasks")
    except Exception:
        return False


def _list_tasks(client, user_id: int, **params):
    return client.get("/tasks", params=params, headers=auth_headers(user_id))


def _create_regular_task_with_schedule(
    *,
    period_id: int,
    title: str,
    initiator_user_id: int,
    executor_role_id: int,
    assignment_scope: str,
    unit_id: int,
    schedule_type: str,
) -> int:
    with engine.begin() as conn:
        status_id = get_status_id(conn, "IN_PROGRESS")
        now = utcnow()
        rt_cols = get_columns(conn, "regular_tasks")
        rt_values: Dict[str, Any] = {
            "title": title,
            "is_active": True,
            "schedule_type": schedule_type,
            "create_offset_days": 0,
            "executor_role_id": int(executor_role_id),
            "created_at": now,
            "updated_at": now,
        }
        if "code" in rt_cols:
            rt_values["code"] = f"pytest_sched_{int(now.timestamp() * 1_000_000) % 1_000_000_000}"
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
            "initiator_user_id": int(initiator_user_id),
            "created_by_user_id": int(initiator_user_id),
            "executor_role_id": int(executor_role_id),
            "assignment_scope": assignment_scope,
            "status_id": int(status_id),
            "task_kind": "regular",
            "requires_report": True,
            "requires_approval": True,
            "source_kind": "regular_task",
            "created_at": now,
            "updated_at": now,
        }
        if "unit_id" in t_cols:
            t_values["unit_id"] = int(unit_id)
        if "org_unit_id" in t_cols:
            t_values["org_unit_id"] = int(unit_id)

        task_id = insert_returning_id(conn, table="tasks", id_col="task_id", values=t_values)
        return int(task_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_tasks_includes_schedule_type_from_template(client, seed):
    unique_title = "PytestScheduleTypeColumnWeekly"
    task_id: Optional[int] = None
    regular_task_id: Optional[int] = None

    try:
        task_id = _create_regular_task_with_schedule(
            period_id=seed["period_id"],
            title=unique_title,
            initiator_user_id=seed["initiator_user_id"],
            executor_role_id=seed["executor_role_id"],
            assignment_scope=seed["assignment_scope"],
            unit_id=seed["unit_id"],
            schedule_type="weekly",
        )

        with engine.begin() as conn:
            row = conn.execute(
                text("SELECT regular_task_id FROM public.tasks WHERE task_id = :id"),
                {"id": int(task_id)},
            ).mappings().first()
            if row:
                regular_task_id = int(row["regular_task_id"])

        resp = _list_tasks(
            client,
            seed["executor_user_id"],
            period_id=seed["period_id"],
            search=unique_title,
            scope="mine",
            status_filter="active",
            limit=10,
        )
        assert resp.status_code == 200, resp.text
        items = resp.json().get("items") or []
        hit = next((x for x in items if int(x.get("task_id") or 0) == int(task_id)), None)
        assert hit is not None, items
        assert hit.get("schedule_type") == "weekly"
        assert hit.get("task_kind") == "regular"

        detail = client.get(f"/tasks/{task_id}", headers=auth_headers(seed["executor_user_id"]))
        assert detail.status_code == 200, detail.text
        assert detail.json().get("schedule_type") == "weekly"
    finally:
        if task_id:
            cleanup_task(task_id)
        if regular_task_id:
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM public.regular_tasks WHERE regular_task_id = :id"),
                    {"id": int(regular_task_id)},
                )
