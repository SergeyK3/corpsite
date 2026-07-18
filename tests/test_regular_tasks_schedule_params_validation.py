# tests/test_regular_tasks_schedule_params_validation.py
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any, Dict, List

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.regular_tasks_public_service import _validate_regular_task_schedule
from app.services.regular_tasks_service import run_regular_tasks_catch_up_tx
from app.services.tasks_service import SYSTEM_ADMIN_ROLE_ID
from tests.conftest import auth_headers, create_unit, get_columns, table_exists, utcnow


def test_validate_regular_task_schedule_monthly_missing_bymonthday():
    with pytest.raises(ValueError, match="bymonthday"):
        _validate_regular_task_schedule("monthly", {"time": "10:00"})


def test_validate_regular_task_schedule_monthly_with_bymonthday_ok():
    _validate_regular_task_schedule("monthly", {"bymonthday": [1], "time": "10:00"})


def test_validate_regular_task_schedule_weekly_missing_byweekday():
    with pytest.raises(ValueError, match="byweekday"):
        _validate_regular_task_schedule("weekly", {"time": "10:00"})


def test_validate_regular_task_schedule_skips_when_schedule_type_empty():
    _validate_regular_task_schedule(None, {})


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
            WHERE role_id = :role_id AND is_active = true
            ORDER BY user_id
            LIMIT 1
            """
        ),
        {"role_id": int(SYSTEM_ADMIN_ROLE_ID)},
    ).scalar_one()
    return int(row)


def _insert_template(
    conn,
    *,
    title: str,
    owner_unit_id: int,
    schedule_type: str = "weekly",
    schedule_params: Dict[str, Any] | None = None,
    executor_role_id: int = 1,
    created_at: datetime | None = None,
) -> int:
    cols = get_columns(conn, "regular_tasks")
    now = created_at or utcnow()
    code_suffix = int(now.timestamp() * 1_000_000) % 1_000_000_000
    params = schedule_params if schedule_params is not None else {"byweekday": [3], "time": "10:00"}
    values: Dict[str, Any] = {
        "title": title,
        "is_active": True,
        "schedule_type": schedule_type,
        "create_offset_days": 0,
        "executor_role_id": int(executor_role_id),
        "owner_unit_id": int(owner_unit_id),
        "created_at": now,
        "updated_at": now,
    }
    insert_cols = [
        "title",
        "is_active",
        "schedule_type",
        "create_offset_days",
        "executor_role_id",
        "owner_unit_id",
    ]
    if "code" in cols:
        values["code"] = f"pytest_rt_sched_{code_suffix}"
        insert_cols.append("code")
    if "created_at" in cols:
        insert_cols.append("created_at")
    if "updated_at" in cols:
        insert_cols.append("updated_at")
    if "schedule_params" in cols:
        values["schedule_params"] = json.dumps(params, ensure_ascii=False)
        insert_cols.append("schedule_params")
    if "assignment_scope" in cols:
        values["assignment_scope"] = "functional"
        insert_cols.append("assignment_scope")

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


def _cleanup(template_ids: List[int], unit_ids: List[int]) -> None:
    with engine.begin() as conn:
        if template_ids and table_exists(conn, "regular_tasks"):
            conn.execute(
                text("DELETE FROM public.regular_tasks WHERE regular_task_id = ANY(:ids)"),
                {"ids": [int(x) for x in template_ids]},
            )
        if unit_ids and table_exists(conn, "org_units"):
            conn.execute(
                text("DELETE FROM public.org_units WHERE unit_id = ANY(:ids)"),
                {"ids": [int(x) for x in unit_ids]},
            )


def _create_payload(*, owner_unit_id: int, schedule_type: str, schedule_params: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": "Pytest schedule params validation",
        "owner_unit_id": owner_unit_id,
        "executor_role_id": 1,
        "schedule_type": schedule_type,
        "schedule_params": schedule_params,
        "create_offset_days": 0,
        "due_offset_days": 0,
    }


@pytest.mark.skipif(not _db_available(), reason="database unavailable")
def test_create_monthly_without_bymonthday_returns_422(client):
    unit_ids: List[int] = []
    template_ids: List[int] = []

    try:
        with engine.begin() as conn:
            admin_id = _admin_user_id(conn)
            unit_id = create_unit(conn, "pytest_rt_sched_create_invalid")
            unit_ids.append(unit_id)

        resp = client.post(
            "/regular-tasks",
            headers=auth_headers(admin_id),
            json=_create_payload(
                owner_unit_id=unit_id,
                schedule_type="monthly",
                schedule_params={"time": "10:00"},
            ),
        )
        assert resp.status_code == 422, resp.text
        assert "bymonthday" in resp.json()["detail"]
    finally:
        _cleanup(template_ids, unit_ids)


@pytest.mark.skipif(not _db_available(), reason="database unavailable")
def test_create_monthly_with_bymonthday_ok(client):
    unit_ids: List[int] = []
    template_ids: List[int] = []

    try:
        with engine.begin() as conn:
            admin_id = _admin_user_id(conn)
            unit_id = create_unit(conn, "pytest_rt_sched_create_valid")
            unit_ids.append(unit_id)

        resp = client.post(
            "/regular-tasks",
            headers=auth_headers(admin_id),
            json=_create_payload(
                owner_unit_id=unit_id,
                schedule_type="monthly",
                schedule_params={"bymonthday": [1], "time": "10:00"},
            ),
        )
        assert resp.status_code == 200, resp.text
        created = resp.json()
        template_ids.append(int(created["regular_task_id"]))
        assert created["schedule_type"] == "monthly"
        assert created["schedule_params"]["bymonthday"] == [1]
    finally:
        _cleanup(template_ids, unit_ids)


@pytest.mark.skipif(not _db_available(), reason="database unavailable")
def test_patch_monthly_invalid_schedule_params_returns_422(client):
    unit_ids: List[int] = []
    template_ids: List[int] = []

    try:
        with engine.begin() as conn:
            admin_id = _admin_user_id(conn)
            unit_id = create_unit(conn, "pytest_rt_sched_patch_invalid")
            unit_ids.append(unit_id)
            template_id = _insert_template(
                conn,
                title="Pytest schedule patch invalid",
                owner_unit_id=unit_id,
                schedule_type="monthly",
                schedule_params={"bymonthday": [1], "time": "10:00"},
            )
            template_ids.append(template_id)

        resp = client.patch(
            f"/regular-tasks/{template_id}",
            headers=auth_headers(admin_id),
            json={"schedule_params": {"time": "10:00"}},
        )
        assert resp.status_code == 422, resp.text
        assert "bymonthday" in resp.json()["detail"]
    finally:
        _cleanup(template_ids, unit_ids)


@pytest.mark.skipif(not _db_available(), reason="database unavailable")
def test_catch_up_monthly_valid_template_has_zero_schedule_errors():
    unit_ids: List[int] = []
    template_ids: List[int] = []

    try:
        with engine.begin() as conn:
            unit_id = create_unit(conn, "pytest_rt_sched_catchup_valid")
            unit_ids.append(unit_id)
            template_id = _insert_template(
                conn,
                title="Pytest schedule catch-up valid monthly",
                owner_unit_id=unit_id,
                schedule_type="monthly",
                schedule_params={"bymonthday": [1], "time": "00:00"},
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
            template_ids.append(template_id)

            _run_id, stats, _resolved = run_regular_tasks_catch_up_tx(
                conn,
                preset="manual",
                dry_run=True,
                run_for_date_manual=date(2026, 2, 1),
                schedule_type="monthly",
            )

            assert stats["errors"] == 0, stats
            assert stats["templates_due"] >= 1
    finally:
        _cleanup(template_ids, unit_ids)
