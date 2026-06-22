# FILE: tests/test_regular_tasks_run_items.py
# PURPOSE: Run journal item persistence, dedup meta, failure visibility, cleanup.

from __future__ import annotations

import json
from datetime import date
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.main import app
from app.services.regular_tasks_service import (
    JOURNAL_ORPHAN_WARNING,
    _log_run_item,
    _resolve_journal_warning,
    run_regular_tasks_catch_up_tx,
    run_regular_tasks_generation_tx,
)
from app.services.tasks_service import SYSTEM_ADMIN_ROLE_ID
from tests.conftest import auth_headers, create_unit, create_user


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

    unit_id = create_unit(conn, "pytest_rt_run_items_admin_unit")
    return create_user(
        conn,
        full_name="Pytest RT Run Items Admin",
        role_id=int(SYSTEM_ADMIN_ROLE_ID),
        unit_id=unit_id,
    )


def _today() -> date:
    return date.today()


def _table_exists(conn, table_name: str) -> bool:
    return bool(
        conn.execute(
            text(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema='public' AND table_name=:t
                LIMIT 1
                """
            ),
            {"t": table_name},
        ).scalar()
    )


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



def _insert_due_regular_task(
    conn,
    *,
    title_suffix: str | None = None,
    schedule_params: dict | None = None,
    executor_role_id: int = 1,
    owner_unit_id: int | None = None,
    schedule_type: str = "monthly",
) -> int:
    d = _today().day
    schedule_params = schedule_params or {"bymonthday": [d], "time": "00:00"}

    cols = []
    vals = {}

    if _col_exists(conn, "regular_tasks", "title"):
        cols.append("title")
        vals["title"] = f"TEST run_items {title_suffix or date.today().isoformat()}"

    if _col_exists(conn, "regular_tasks", "description"):
        cols.append("description")
        vals["description"] = "test template for run_items"

    if _col_exists(conn, "regular_tasks", "is_active"):
        cols.append("is_active")
        vals["is_active"] = True

    if _col_exists(conn, "regular_tasks", "schedule_type"):
        cols.append("schedule_type")
        vals["schedule_type"] = schedule_type

    if owner_unit_id is not None and _col_exists(conn, "regular_tasks", "owner_unit_id"):
        cols.append("owner_unit_id")
        vals["owner_unit_id"] = int(owner_unit_id)

    if _col_exists(conn, "regular_tasks", "schedule_params"):
        cols.append("schedule_params")
        vals["schedule_params"] = json.dumps(schedule_params, ensure_ascii=False)

    if _col_exists(conn, "regular_tasks", "create_offset_days"):
        cols.append("create_offset_days")
        vals["create_offset_days"] = 0

    if _col_exists(conn, "regular_tasks", "due_offset_days"):
        cols.append("due_offset_days")
        vals["due_offset_days"] = 0

    if _col_exists(conn, "regular_tasks", "executor_role_id"):
        cols.append("executor_role_id")
        vals["executor_role_id"] = int(executor_role_id)

    if _col_exists(conn, "regular_tasks", "assignment_scope"):
        cols.append("assignment_scope")
        vals["assignment_scope"] = "functional"

    if _col_exists(conn, "regular_tasks", "periodicity"):
        cols.append("periodicity")
        vals["periodicity"] = "MONTH"

    for c in ("initiator_role_id", "target_role_id"):
        if _col_exists(conn, "regular_tasks", c):
            cols.append(c)
            vals[c] = 1

    if not cols:
        pytest.fail("Не удалось собрать ни одной колонки для INSERT в regular_tasks (схема неожиданная).")

    values_sql_parts = []
    for c in cols:
        if c == "schedule_params":
            values_sql_parts.append("CAST(:schedule_params AS jsonb)")
        else:
            values_sql_parts.append(f":{c}")
    values_sql = ", ".join(values_sql_parts)
    cols_sql = ", ".join(cols)

    q = text(
        f"""
        INSERT INTO public.regular_tasks ({cols_sql})
        VALUES ({values_sql})
        RETURNING regular_task_id
        """
    )
    rid = conn.execute(q, vals).scalar_one()
    return int(rid)


def _fetch_run_items(conn, *, run_id: int) -> list[dict]:
    rows = conn.execute(
        text(
            """
            SELECT item_id, regular_task_id, status, is_due, created_tasks, error, meta
            FROM public.regular_task_run_items
            WHERE run_id = :run_id
            ORDER BY item_id
            """
        ),
        {"run_id": int(run_id)},
    ).mappings().all()
    return [dict(r) for r in rows]


def _fetch_run(conn, *, run_id: int) -> dict:
    row = conn.execute(
        text(
            """
            SELECT run_id, status, stats, errors
            FROM public.regular_task_runs
            WHERE run_id = :run_id
            """
        ),
        {"run_id": int(run_id)},
    ).mappings().first()
    assert row is not None
    out = dict(row)
    if isinstance(out.get("stats"), str):
        out["stats"] = json.loads(out["stats"])
    if isinstance(out.get("errors"), str):
        out["errors"] = json.loads(out["errors"])
    return out


def _cleanup_run(conn, run_id: int):
    conn.execute(
        text("DELETE FROM public.regular_task_run_items WHERE run_id = :run_id"),
        {"run_id": int(run_id)},
    )
    conn.execute(
        text("DELETE FROM public.regular_task_runs WHERE run_id = :run_id"),
        {"run_id": int(run_id)},
    )


def _cleanup_template(conn, regular_task_id: int):
    if _table_exists(conn, "regular_task_run_items"):
        conn.execute(
            text("DELETE FROM public.regular_task_run_items WHERE regular_task_id = :rid"),
            {"rid": int(regular_task_id)},
        )
    if _table_exists(conn, "tasks") and _col_exists(conn, "tasks", "regular_task_id"):
        conn.execute(
            text("DELETE FROM public.tasks WHERE regular_task_id = :rid"),
            {"rid": int(regular_task_id)},
        )
    conn.execute(
        text("DELETE FROM public.regular_tasks WHERE regular_task_id = :rid"),
        {"rid": int(regular_task_id)},
    )


def test_log_run_item_failure_is_visible_not_swallowed():
    journal_errors: list[dict] = []
    conn = MagicMock()
    conn.begin_nested.side_effect = Exception("savepoint failed")
    conn.execute.side_effect = Exception("insert failed")

    ok = _log_run_item(
        conn,
        run_id=1,
        regular_task_id=2,
        period_id=None,
        executor_role_id=1,
        is_due=True,
        created_tasks=0,
        status="ok",
        error=None,
        meta={"run_kind": "automatic"},
        journal_errors=journal_errors,
    )

    assert ok is False
    assert len(journal_errors) == 1
    assert journal_errors[0]["kind"] == "journal_insert_failed"
    assert journal_errors[0]["regular_task_id"] == 2
    assert "savepoint failed" in journal_errors[0]["error"]


def test_resolve_journal_warning_orphan_run():
    warning = _resolve_journal_warning(
        stats={"created": 1, "deduped": 0, "errors": 0, "templates_due": 1},
        item_count=0,
        templates_due=1,
    )
    assert warning == JOURNAL_ORPHAN_WARNING


def test_resolve_journal_warning_no_orphan_for_non_due_schedule_errors():
    """Non-due schedule validation errors must not trigger orphan warning."""
    warning = _resolve_journal_warning(
        stats={
            "templates_due": 0,
            "created": 0,
            "deduped": 0,
            "errors": 3,
        },
        item_count=0,
        templates_due=0,
    )
    assert warning is None

@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_run_now_writes_run_item_for_regular_task(seed):
    run_id: int | None = None
    rid: int | None = None
    with engine.begin() as conn:
        if not _table_exists(conn, "regular_task_run_items"):
            pytest.skip("Таблица regular_task_run_items отсутствует. Сначала примените миграцию.")
        if not _table_exists(conn, "regular_tasks"):
            pytest.skip("Таблица regular_tasks отсутствует.")

        rid = _insert_due_regular_task(conn, executor_role_id=int(seed["executor_role_id"]))
        before = int(
            conn.execute(
                text(
                    "SELECT COUNT(1) FROM public.regular_task_run_items WHERE regular_task_id = :rid"
                ),
                {"rid": int(rid)},
            ).scalar()
            or 0
        )
        run_id, stats = run_regular_tasks_generation_tx(conn, dry_run=False, force_due=True)
        after = int(
            conn.execute(
                text(
                    "SELECT COUNT(1) FROM public.regular_task_run_items WHERE regular_task_id = :rid"
                ),
                {"rid": int(rid)},
            ).scalar()
            or 0
        )
        items = _fetch_run_items(conn, run_id=int(run_id))
        template_items = [it for it in items if it["regular_task_id"] == rid]
        assert after >= before + 1
        assert len(template_items) >= 1
        assert stats.get("item_count") == len(items)

    with engine.begin() as conn:
        if run_id:
            _cleanup_run(conn, int(run_id))
        if rid:
            _cleanup_template(conn, int(rid))


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_created_task_writes_run_item(seed):
    run_id: int | None = None
    rid: int | None = None
    with engine.begin() as conn:
        if not _table_exists(conn, "regular_task_run_items"):
            pytest.skip("regular_task_run_items table not available")
        rid = _insert_due_regular_task(conn, executor_role_id=int(seed["executor_role_id"]))
        run_id, stats = run_regular_tasks_generation_tx(conn, dry_run=False, force_due=True)
        items = _fetch_run_items(conn, run_id=int(run_id))
        due_items = [it for it in items if it["regular_task_id"] == rid]
        assert stats["created"] >= 1
        assert len(due_items) >= 1
        assert due_items[0]["created_tasks"] == 1
        assert due_items[0]["status"] == "ok"

    with engine.begin() as conn:
        if run_id:
            _cleanup_run(conn, int(run_id))
        if rid:
            _cleanup_template(conn, int(rid))


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_deduped_task_writes_run_item_with_meta(seed):
    run_id_1: int | None = None
    run_id_2: int | None = None
    rid: int | None = None
    with engine.begin() as conn:
        if not _table_exists(conn, "regular_task_run_items"):
            pytest.skip("regular_task_run_items table not available")
        rid = _insert_due_regular_task(conn, executor_role_id=int(seed["executor_role_id"]))
        run_id_1, stats_1 = run_regular_tasks_generation_tx(conn, dry_run=False, force_due=True)
        assert stats_1["created"] >= 1
        run_id_2, stats_2 = run_regular_tasks_generation_tx(conn, dry_run=False, force_due=True)
        assert stats_2["deduped"] >= 1

        items = _fetch_run_items(conn, run_id=int(run_id_2))
        dedup_items = [it for it in items if it["regular_task_id"] == rid]
        assert len(dedup_items) == 1
        meta = dedup_items[0]["meta"] or {}
        if isinstance(meta, str):
            meta = json.loads(meta)
        for key in (
            "dedupe_mode",
            "task_id",
            "task_title",
            "regular_task_id",
            "executor_role_id",
            "period_id",
            "assignment_scope",
            "occurrence_date",
            "run_kind",
        ):
            assert key in meta, f"missing dedup meta key: {key}"
        assert meta["dedupe_mode"] == "same_executor_active_exists"

    with engine.begin() as conn:
        for rid_val in (run_id_1, run_id_2):
            if rid_val:
                _cleanup_run(conn, int(rid_val))
        if rid:
            _cleanup_template(conn, int(rid))


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_due_template_error_writes_run_item_or_visible_run_error(seed):
    run_id: int | None = None
    rid: int | None = None
    with engine.begin() as conn:
        if not _table_exists(conn, "regular_task_run_items"):
            pytest.skip("regular_task_run_items table not available")
        rid = _insert_due_regular_task(
            conn,
            title_suffix="missing_executor",
            executor_role_id=int(seed["executor_role_id"]),
        )
        conn.execute(
            text("UPDATE public.regular_tasks SET executor_role_id = NULL WHERE regular_task_id = :rid"),
            {"rid": int(rid)},
        )
        run_id, stats = run_regular_tasks_generation_tx(conn, dry_run=False, force_due=True)
        run = _fetch_run(conn, run_id=int(run_id))
        items = _fetch_run_items(conn, run_id=int(run_id))
        assert stats["errors"] >= 1
        assert run["status"] == "partial"
        err_items = [it for it in items if it["regular_task_id"] == rid]
        assert len(err_items) == 1
        assert err_items[0]["status"] == "error"
        assert "executor_role_id" in (err_items[0]["error"] or "")

    with engine.begin() as conn:
        if run_id:
            _cleanup_run(conn, int(run_id))
        if rid:
            _cleanup_template(conn, int(rid))


def _create_unit_with_group(conn, *, name: str, group_id: int) -> int:
    cols = [
        row[0]
        for row in conn.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'org_units'
                """
            )
        ).fetchall()
    ]
    values: dict = {"name": name}
    insert_cols = ["name"]
    if "code" in cols:
        values["code"] = name
        insert_cols.append("code")
    if "group_id" in cols:
        values["group_id"] = int(group_id)
        insert_cols.append("group_id")
    if "is_active" in cols:
        values["is_active"] = True
        insert_cols.append("is_active")

    cols_sql = ", ".join(insert_cols)
    vals_sql = ", ".join(f":{c}" for c in insert_cols)
    return int(
        conn.execute(
            text(
                f"""
                INSERT INTO public.org_units ({cols_sql})
                VALUES ({vals_sql})
                RETURNING unit_id
                """
            ),
            values,
        ).scalar_one()
    )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_catch_up_two_due_templates_writes_two_item_rows(seed):
    suffix = date.today().isoformat()
    run_id: int | None = None
    template_ids: list[int] = []
    unit_id: int | None = None
    with engine.begin() as conn:
        if not _table_exists(conn, "regular_task_run_items"):
            pytest.skip("regular_task_run_items table not available")
        unit_id = _create_unit_with_group(conn, name=f"pytest_rt_items_unit_{suffix}", group_id=1)
        for idx in range(2):
            template_ids.append(
                _insert_due_regular_task(
                    conn,
                    title_suffix=f"catchup_{idx}_{suffix}",
                    schedule_params={"byweekday": [4], "time": "00:00"},
                    executor_role_id=int(seed["executor_role_id"]),
                    owner_unit_id=int(unit_id),
                    schedule_type="weekly",
                )
            )

        run_id, stats, _resolved = run_regular_tasks_catch_up_tx(
            conn,
            preset="manual",
            dry_run=False,
            run_for_date_manual=date(2026, 3, 5),
            schedule_type="weekly",
            org_unit_id=int(unit_id),
        )
        items = _fetch_run_items(conn, run_id=int(run_id))
        assert stats["templates_due"] == 2
        assert len(items) == 2
        assert stats.get("item_count") == 2

    with engine.begin() as conn:
        if run_id:
            _cleanup_run(conn, int(run_id))
        for tid in template_ids:
            _cleanup_template(conn, int(tid))
        if unit_id:
            conn.execute(text("DELETE FROM public.org_units WHERE unit_id = :uid"), {"uid": int(unit_id)})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_api_orphan_run_exposes_journal_warning():
    client = TestClient(app)
    orphan_run_id: int | None = None
    with engine.begin() as conn:
        if not _table_exists(conn, "regular_task_runs"):
            pytest.skip("regular_task_runs table not available")
        admin_user_id = _admin_user_id(conn)
        orphan_run_id = int(
            conn.execute(
                text(
                    """
                    INSERT INTO public.regular_task_runs (started_at, finished_at, status, stats, errors)
                    VALUES (
                        now(),
                        now(),
                        'ok',
                        CAST(:stats AS jsonb),
                        '[]'::jsonb
                    )
                    RETURNING run_id
                    """
                ),
                {
                    "stats": json.dumps(
                        {
                            "templates_total": 1,
                            "templates_due": 1,
                            "created": 0,
                            "deduped": 1,
                            "errors": 0,
                        },
                        ensure_ascii=False,
                    ),
                },
            ).scalar_one()
        )

    try:
        resp = client.get(
            "/regular-task-runs",
            headers=auth_headers(admin_user_id),
        )
        assert resp.status_code == 200
        rows = resp.json()
        orphan = next((r for r in rows if int(r["run_id"]) == int(orphan_run_id)), None)
        assert orphan is not None
        assert orphan.get("journal_warning") == JOURNAL_ORPHAN_WARNING
        assert int(orphan.get("item_count") or 0) == 0
    finally:
        with engine.begin() as conn:
            if orphan_run_id:
                _cleanup_run(conn, int(orphan_run_id))
