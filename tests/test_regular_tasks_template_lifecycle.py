# tests/test_regular_tasks_template_lifecycle.py
from __future__ import annotations

import json
from typing import Any, Dict, List

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.regular_tasks_service import _load_regular_task_templates
from app.services.tasks_service import SYSTEM_ADMIN_ROLE_ID
from tests.conftest import (
    auth_headers,
    create_unit,
    create_user,
    get_columns,
    table_exists,
    utcnow,
)


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _col_exists(conn, table: str, col: str) -> bool:
    return bool(
        conn.execute(
            text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema='public'
                  AND table_name=:t
                  AND column_name=:c
                LIMIT 1
                """
            ),
            {"t": table, "c": col},
        ).scalar()
    )


def _ensure_archived_at_column(conn) -> None:
    if not _col_exists(conn, "regular_tasks", "archived_at"):
        conn.execute(
            text(
                """
                ALTER TABLE public.regular_tasks
                  ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ NULL
                """
            )
        )


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

    unit_id = create_unit(conn, "pytest_rt_lifecycle_admin_unit")
    return create_user(
        conn,
        full_name="Pytest RT Lifecycle Admin",
        role_id=int(SYSTEM_ADMIN_ROLE_ID),
        unit_id=unit_id,
    )


def _insert_template(
    conn,
    *,
    title: str,
    owner_unit_id: int,
    executor_role_id: int = 1,
    is_active: bool = True,
) -> int:
    cols = get_columns(conn, "regular_tasks")
    now = utcnow()
    code_suffix = int(now.timestamp() * 1_000_000) % 1_000_000_000
    values: Dict[str, Any] = {
        "title": title,
        "is_active": bool(is_active),
        "schedule_type": "weekly",
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
        values["code"] = f"pytest_rt_lifecycle_{code_suffix}"
        insert_cols.append("code")
    if "created_at" in cols:
        insert_cols.append("created_at")
    if "updated_at" in cols:
        insert_cols.append("updated_at")
    if "schedule_params" in cols:
        values["schedule_params"] = json.dumps({"byweekday": [3], "time": "10:00"}, ensure_ascii=False)
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


def _count_runs_for_template(conn, template_id: int) -> int:
    if not table_exists(conn, "regular_task_run_items"):
        return 0
    return int(
        conn.execute(
            text(
                """
                SELECT COUNT(1)
                FROM public.regular_task_run_items
                WHERE regular_task_id = :rid
                """
            ),
            {"rid": int(template_id)},
        ).scalar()
        or 0
    )


def _count_tasks_for_template(conn, template_id: int) -> int:
    if not table_exists(conn, "tasks"):
        return 0
    return int(
        conn.execute(
            text(
                """
                SELECT COUNT(1)
                FROM public.tasks
                WHERE regular_task_id = :rid
                """
            ),
            {"rid": int(template_id)},
        ).scalar()
        or 0
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


@pytest.mark.skipif(not _db_available(), reason="database unavailable")
def test_list_includes_created_at(client):
    template_ids: List[int] = []
    unit_ids: List[int] = []

    try:
        with engine.begin() as conn:
            _ensure_archived_at_column(conn)
            admin_id = _admin_user_id(conn)
            unit_id = create_unit(conn, "pytest_rt_lifecycle_list_unit")
            unit_ids.append(unit_id)
            template_id = _insert_template(
                conn,
                title="Pytest lifecycle list",
                owner_unit_id=unit_id,
            )
            template_ids.append(template_id)

        resp = client.get(
            "/regular-tasks",
            params={"status": "active", "limit": 200},
            headers=auth_headers(admin_id),
        )
        assert resp.status_code == 200, resp.text
        payload = resp.json()
        items = payload["items"] if isinstance(payload, dict) else payload
        row = next(x for x in items if int(x["regular_task_id"]) == template_id)
        assert row.get("created_at")
        assert "archived_at" in row
    finally:
        _cleanup(template_ids, unit_ids)


@pytest.mark.skipif(not _db_available(), reason="database unavailable")
def test_archive_hides_template_from_active_list(client):
    template_ids: List[int] = []
    unit_ids: List[int] = []

    try:
        with engine.begin() as conn:
            _ensure_archived_at_column(conn)
            admin_id = _admin_user_id(conn)
            unit_id = create_unit(conn, "pytest_rt_lifecycle_archive_unit")
            unit_ids.append(unit_id)
            template_id = _insert_template(
                conn,
                title="Pytest lifecycle archive",
                owner_unit_id=unit_id,
            )
            template_ids.append(template_id)

        archive_resp = client.post(
            f"/regular-tasks/{template_id}/archive",
            headers=auth_headers(admin_id),
        )
        assert archive_resp.status_code == 200, archive_resp.text
        archived = archive_resp.json()
        assert archived["is_active"] is False
        assert archived.get("archived_at")

        active_resp = client.get(
            "/regular-tasks",
            params={"status": "active", "limit": 200},
            headers=auth_headers(admin_id),
        )
        assert active_resp.status_code == 200
        active_items = active_resp.json()["items"]
        assert not any(int(x["regular_task_id"]) == template_id for x in active_items)

        archived_resp = client.get(
            "/regular-tasks",
            params={"status": "inactive", "limit": 200},
            headers=auth_headers(admin_id),
        )
        assert archived_resp.status_code == 200
        archived_items = archived_resp.json()["items"]
        assert any(int(x["regular_task_id"]) == template_id for x in archived_items)
    finally:
        _cleanup(template_ids, unit_ids)


@pytest.mark.skipif(not _db_available(), reason="database unavailable")
def test_archived_template_not_used_in_catch_up():
    template_ids: List[int] = []
    unit_ids: List[int] = []

    try:
        with engine.begin() as conn:
            _ensure_archived_at_column(conn)
            unit_id = create_unit(conn, "pytest_rt_lifecycle_catchup_unit")
            unit_ids.append(unit_id)
            template_id = _insert_template(
                conn,
                title="Pytest lifecycle catch-up",
                owner_unit_id=unit_id,
            )
            template_ids.append(template_id)
            conn.execute(
                text(
                    """
                    UPDATE public.regular_tasks
                    SET is_active = false, archived_at = now()
                    WHERE regular_task_id = :rid
                    """
                ),
                {"rid": template_id},
            )

        with engine.connect() as conn:
            active_ids = [
                int(r["regular_task_id"])
                for r in _load_regular_task_templates(conn)
                if r.get("regular_task_id") is not None
            ]
        assert template_id not in active_ids
    finally:
        _cleanup(template_ids, unit_ids)


@pytest.mark.skipif(not _db_available(), reason="database unavailable")
def test_copy_creates_new_active_template_without_runs_or_tasks(client):
    template_ids: List[int] = []
    unit_ids: List[int] = []

    try:
        with engine.begin() as conn:
            _ensure_archived_at_column(conn)
            admin_id = _admin_user_id(conn)
            unit_id = create_unit(conn, "pytest_rt_lifecycle_copy_unit")
            unit_ids.append(unit_id)
            source_id = _insert_template(
                conn,
                title="Pytest lifecycle source",
                owner_unit_id=unit_id,
            )
            template_ids.append(source_id)

            if table_exists(conn, "regular_task_run_items"):
                run_id = conn.execute(
                    text(
                        """
                        INSERT INTO public.regular_task_runs (status, stats, errors)
                        VALUES ('ok', '{}'::jsonb, '[]'::jsonb)
                        RETURNING run_id
                        """
                    )
                ).scalar_one()
                conn.execute(
                    text(
                        """
                        INSERT INTO public.regular_task_run_items (
                          run_id, regular_task_id, status, is_due, created_tasks
                        ) VALUES (
                          :run_id, :rid, 'ok', true, 0
                        )
                        """
                    ),
                    {"run_id": int(run_id), "rid": source_id},
                )

        source_runs = 0
        source_tasks = 0
        with engine.connect() as conn:
            source_runs = _count_runs_for_template(conn, source_id)
            source_tasks = _count_tasks_for_template(conn, source_id)

        copy_resp = client.post(
            f"/regular-tasks/{source_id}/copy",
            headers=auth_headers(admin_id),
        )
        assert copy_resp.status_code == 200, copy_resp.text
        copied = copy_resp.json()
        copied_id = int(copied["regular_task_id"])
        template_ids.append(copied_id)

        assert copied_id != source_id
        assert copied["is_active"] is True
        assert copied.get("archived_at") in (None, "")
        assert copied["title"] == "Pytest lifecycle source — копия"
        assert copied.get("created_at")
        assert copied["owner_unit_id"] == unit_id
        assert copied["schedule_type"] == "weekly"

        with engine.connect() as conn:
            assert _count_runs_for_template(conn, copied_id) == 0
            assert _count_tasks_for_template(conn, copied_id) == 0
            assert _count_runs_for_template(conn, source_id) == source_runs
            assert _count_tasks_for_template(conn, source_id) == source_tasks
    finally:
        _cleanup(template_ids, unit_ids)


@pytest.mark.skipif(not _db_available(), reason="database unavailable")
def test_patch_archived_template_rejected(client):
    template_ids: List[int] = []
    unit_ids: List[int] = []

    try:
        with engine.begin() as conn:
            _ensure_archived_at_column(conn)
            admin_id = _admin_user_id(conn)
            unit_id = create_unit(conn, "pytest_rt_lifecycle_patch_unit")
            unit_ids.append(unit_id)
            template_id = _insert_template(
                conn,
                title="Pytest lifecycle patch",
                owner_unit_id=unit_id,
                is_active=False,
            )
            template_ids.append(template_id)
            conn.execute(
                text(
                    """
                    UPDATE public.regular_tasks
                    SET archived_at = now()
                    WHERE regular_task_id = :rid
                    """
                ),
                {"rid": template_id},
            )

        resp = client.patch(
            f"/regular-tasks/{template_id}",
            json={"title": "Should not apply"},
            headers=auth_headers(admin_id),
        )
        assert resp.status_code == 422, resp.text
        assert "archived" in resp.text.lower()
    finally:
        _cleanup(template_ids, unit_ids)
