# tests/test_regular_tasks_origin_metadata.py
from __future__ import annotations

import json
from datetime import date

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.regular_tasks_service import (
    _append_origin_metadata_to_description,
    _compose_task_origin_metadata_block,
    run_regular_tasks_catch_up_tx,
    run_regular_tasks_generation_tx,
)
from tests.conftest import get_columns, table_exists


def test_compose_automatic_origin_metadata_block():
    block = _compose_task_origin_metadata_block(
        run_id=10,
        occurrence_date=date(2026, 6, 17),
        catch_up_meta=None,
        period_suffix="06.2026",
    )
    assert "Источник: Автоматический запуск регулярной задачи" in block
    assert "ID запуска: 10" in block
    assert "Дата возникновения задачи: 2026-06-17" in block
    assert "Тип запуска: автоматический" in block
    assert block.startswith("\n---\n")
    assert block.endswith("\n---")


def test_compose_catch_up_origin_metadata_block():
    block = _compose_task_origin_metadata_block(
        run_id=33,
        occurrence_date=date(2026, 6, 17),
        catch_up_meta={"preset": "past_week", "run_for_date": "2026-06-17"},
        period_suffix="09.06.2026–15.06.2026",
    )
    assert "Источник: Догоняющий запуск регулярной задачи" in block
    assert "ID запуска: 33" in block
    assert "Тип запуска: догоняющий" in block
    assert "Период: Прошлая неделя" in block


def test_append_origin_metadata_preserves_existing_description():
    block = _compose_task_origin_metadata_block(
        run_id=5,
        occurrence_date=date(2026, 6, 1),
        catch_up_meta=None,
        period_suffix="06.2026",
    )
    merged = _append_origin_metadata_to_description("User-authored body", block, run_id=5)
    assert merged.startswith("User-authored body")
    assert "ID запуска: 5" in merged
    again = _append_origin_metadata_to_description(merged, block, run_id=5)
    assert again == merged


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _insert_due_template(conn, *, title: str, description: str, executor_role_id: int) -> int:
    cols = get_columns(conn, "regular_tasks")
    values = {
        "title": title,
        "description": description,
        "is_active": True,
        "schedule_type": "monthly",
        "schedule_params": json.dumps({"bymonthday": [date.today().day], "time": "00:00"}, ensure_ascii=False),
        "create_offset_days": 0,
        "due_offset_days": 0,
        "executor_role_id": int(executor_role_id),
    }
    insert_cols = [
        "title",
        "description",
        "is_active",
        "schedule_type",
        "schedule_params",
        "create_offset_days",
        "due_offset_days",
        "executor_role_id",
    ]
    if "code" in cols:
        slug = "".join(c if c.isalnum() else "_" for c in title).strip("_").lower()[:40]
        values["code"] = f"pytest_meta_{slug}"
        insert_cols.append("code")
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


def _fetch_task_description(conn, regular_task_id: int) -> str | None:
    row = conn.execute(
        text(
            """
            SELECT description
            FROM public.tasks
            WHERE regular_task_id = :rid
            ORDER BY task_id DESC
            LIMIT 1
            """
        ),
        {"rid": int(regular_task_id)},
    ).mappings().first()
    return row.get("description") if row else None


def _fetch_run_item_meta(conn, run_id: int, regular_task_id: int) -> dict:
    row = conn.execute(
        text(
            """
            SELECT meta
            FROM public.regular_task_run_items
            WHERE run_id = :run_id AND regular_task_id = :rid
            ORDER BY item_id DESC
            LIMIT 1
            """
        ),
        {"run_id": int(run_id), "rid": int(regular_task_id)},
    ).mappings().first()
    meta = row.get("meta") if row else None
    return dict(meta) if isinstance(meta, dict) else {}


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_automatic_run_writes_origin_metadata_to_task_and_journal(seed):
    title = f"Pytest RT Origin Auto {date.today().isoformat()}"
    rid: int | None = None
    run_id: int | None = None
    try:
        with engine.begin() as conn:
            if not table_exists(conn, "regular_task_run_items"):
                pytest.skip("regular_task_run_items table not available")
            rid = _insert_due_template(
                conn,
                title=title,
                description="Template body for automatic run",
                executor_role_id=seed["executor_role_id"],
            )
            run_id, stats = run_regular_tasks_generation_tx(conn, dry_run=False)
            assert stats["created"] >= 1
            assert stats.get("run_kind") == "automatic"
            assert stats.get("occurrence_date")

            desc = _fetch_task_description(conn, rid)
            assert desc is not None
            assert "Template body for automatic run" in desc
            assert "Источник: Автоматический запуск регулярной задачи" in desc
            assert f"ID запуска: {run_id}" in desc

            meta = _fetch_run_item_meta(conn, run_id, rid)
            assert "origin_metadata_text" in meta
            assert "Автоматический запуск" in str(meta["origin_metadata_text"])
            assert meta.get("run_kind") == "automatic"
            assert meta.get("occurrence_date")
    finally:
        if rid is not None:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM public.regular_task_run_items WHERE regular_task_id = :rid"), {"rid": rid})
                conn.execute(text("DELETE FROM public.tasks WHERE regular_task_id = :rid"), {"rid": rid})
                conn.execute(text("DELETE FROM public.regular_tasks WHERE regular_task_id = :rid"), {"rid": rid})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_second_run_dedup_appends_metadata_and_journal_records_it(seed):
    title = f"Pytest RT Origin Dedup {date.today().isoformat()}"
    rid: int | None = None
    try:
        with engine.begin() as conn:
            if not table_exists(conn, "regular_task_run_items"):
                pytest.skip("regular_task_run_items table not available")
            rid = _insert_due_template(
                conn,
                title=title,
                description="Keep this user text",
                executor_role_id=seed["executor_role_id"],
            )
            run_id_1, stats_1 = run_regular_tasks_generation_tx(conn, dry_run=False)
            assert stats_1["created"] >= 1

            run_id_2, stats_2 = run_regular_tasks_generation_tx(conn, dry_run=False)
            assert stats_2["deduped"] >= 1
            assert stats_2["created"] == 0

            desc = _fetch_task_description(conn, rid)
            assert desc is not None
            assert desc.startswith("Keep this user text")
            assert f"ID запуска: {run_id_1}" in desc
            assert f"ID запуска: {run_id_2}" in desc

            meta = _fetch_run_item_meta(conn, run_id_2, rid)
            assert meta.get("deduped") is True
            assert meta.get("description_metadata_appended") is True
            assert "origin_metadata_text" in meta
    finally:
        if rid is not None:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM public.regular_task_run_items WHERE regular_task_id = :rid"), {"rid": rid})
                conn.execute(text("DELETE FROM public.tasks WHERE regular_task_id = :rid"), {"rid": rid})
                conn.execute(text("DELETE FROM public.regular_tasks WHERE regular_task_id = :rid"), {"rid": rid})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_catch_up_run_writes_catch_up_origin_metadata(seed):
    title = f"Pytest RT Origin CatchUp {date.today().isoformat()}"
    rid: int | None = None
    try:
        with engine.begin() as conn:
            if not table_exists(conn, "regular_task_run_items"):
                pytest.skip("regular_task_run_items table not available")
            rid = _insert_due_template(
                conn,
                title=title,
                description="Catch-up template body",
                executor_role_id=seed["executor_role_id"],
            )
            run_id, stats, resolved = run_regular_tasks_catch_up_tx(
                conn,
                preset="manual",
                dry_run=False,
                run_for_date_manual=date(2026, 6, 17),
                schedule_type="monthly",
            )
            assert resolved["preset"] == "manual"
            assert stats["templates_due"] >= 1
            assert stats.get("run_kind") == "catch_up"
            assert stats.get("occurrence_date") == "2026-06-17"

            desc = _fetch_task_description(conn, rid)
            assert desc is not None
            assert "Catch-up template body" in desc
            assert "Догоняющий запуск регулярной задачи" in desc
            assert f"ID запуска: {run_id}" in desc
            assert "Дата возникновения задачи: 2026-06-17" in desc

            meta = _fetch_run_item_meta(conn, run_id, rid)
            assert "origin_metadata_text" in meta
            assert "догоняющий" in str(meta["origin_metadata_text"]).lower()
            assert meta.get("run_kind") == "catch_up"
            assert meta.get("occurrence_date") == "2026-06-17"
    finally:
        if rid is not None:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM public.regular_task_run_items WHERE regular_task_id = :rid"), {"rid": rid})
                conn.execute(text("DELETE FROM public.tasks WHERE regular_task_id = :rid"), {"rid": rid})
                conn.execute(text("DELETE FROM public.regular_tasks WHERE regular_task_id = :rid"), {"rid": rid})
