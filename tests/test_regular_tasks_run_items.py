# FILE: tests/test_regular_tasks_run_items.py
# PURPOSE: Integration test:
# - create a due-today regular_task template
# - call run endpoint
# - assert regular_task_run_items row is written for that regular_task_id

from __future__ import annotations

import json
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.main import app


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


def _call_run_now(client: TestClient, regular_task_id: int):
    candidates = [
        (f"/regular-tasks/{regular_task_id}/run-now", None),
        (f"/internal/regular-tasks/{regular_task_id}/run-now", None),
        (f"/internal/regular-tasks/run-now/{regular_task_id}", None),
        (f"/internal/regular-tasks/{regular_task_id}/run", None),
        ("/internal/regular-tasks/run", {"regular_task_id": regular_task_id}),
    ]

    for path, payload in candidates:
        r = client.post(path, json=payload, headers={"X-User-Id": "1"})
        if r.status_code != 404:
            return path, r

    pytest.fail("Не найден endpoint run-now (все кандидаты вернули 404).")


def _insert_due_regular_task(conn) -> int:
    """
    Вставляет минимально достаточную regular_task, которая будет due сегодня.
    Состав колонок берём по факту схемы (что есть — заполняем).
    Возвращает regular_task_id.
    """
    d = _today().day
    schedule_params = {"bymonthday": [d], "time": "00:00"}

    cols = []
    vals = {}
    # PK: regular_task_id bigserial/bigint may be generated; если нет default — зададим вручную.
    # В большинстве схем regular_task_id генерится. Поэтому INSERT без него, с RETURNING.
    if _col_exists(conn, "regular_tasks", "title"):
        cols.append("title")
        vals["title"] = f"TEST run_items {date.today().isoformat()}"

    if _col_exists(conn, "regular_tasks", "description"):
        cols.append("description")
        vals["description"] = "test template for run_items"

    if _col_exists(conn, "regular_tasks", "is_active"):
        cols.append("is_active")
        vals["is_active"] = True

    if _col_exists(conn, "regular_tasks", "schedule_type"):
        cols.append("schedule_type")
        vals["schedule_type"] = "monthly"

    if _col_exists(conn, "regular_tasks", "schedule_params"):
        cols.append("schedule_params")
        vals["schedule_params"] = json.dumps(schedule_params, ensure_ascii=False)

    if _col_exists(conn, "regular_tasks", "create_offset_days"):
        cols.append("create_offset_days")
        vals["create_offset_days"] = 0

    if _col_exists(conn, "regular_tasks", "due_offset_days"):
        cols.append("due_offset_days")
        vals["due_offset_days"] = 0

    # executor_role_id обязателен в текущей логике сервиса
    if _col_exists(conn, "regular_tasks", "executor_role_id"):
        cols.append("executor_role_id")
        vals["executor_role_id"] = 1

    # assignment_scope может быть enum/текст; ставим дефолтное безопасное значение
    if _col_exists(conn, "regular_tasks", "assignment_scope"):
        cols.append("assignment_scope")
        vals["assignment_scope"] = "functional"

    # periodicity (enum period_kind_t) — если колонка есть, ставим MONTH
    if _col_exists(conn, "regular_tasks", "periodicity"):
        cols.append("periodicity")
        vals["periodicity"] = "MONTH"

    # initiator/target roles — если обязательны, подставим 1
    for c in ("initiator_role_id", "target_role_id"):
        if _col_exists(conn, "regular_tasks", c):
            cols.append(c)
            vals[c] = 1

    if not cols:
        pytest.fail("Не удалось собрать ни одной колонки для INSERT в regular_tasks (схема неожиданная).")

    placeholders = ", ".join([f":{c}" for c in cols])
    cols_sql = ", ".join(cols)

    # schedule_params в БД может быть jsonb -> CAST
    # Подготовим SQL со спец. обработкой schedule_params
    values_sql_parts = []
    for c in cols:
        if c == "schedule_params":
            values_sql_parts.append("CAST(:schedule_params AS jsonb)")
        else:
            values_sql_parts.append(f":{c}")
    values_sql = ", ".join(values_sql_parts)

    q = text(
        f"""
        INSERT INTO public.regular_tasks ({cols_sql})
        VALUES ({values_sql})
        RETURNING regular_task_id
        """
    )
    rid = conn.execute(q, vals).scalar_one()
    return int(rid)


def _count_run_items(conn, regular_task_id: int) -> int:
    return int(
        conn.execute(
            text(
                """
                SELECT COUNT(1)
                FROM public.regular_task_run_items
                WHERE regular_task_id = :rid
                """
            ),
            {"rid": int(regular_task_id)},
        ).scalar()
        or 0
    )


def _cleanup(conn, regular_task_id: int):
    # чистим run_items и tasks (если есть), затем regular_task
    if _table_exists(conn, "regular_task_run_items"):
        conn.execute(
            text("DELETE FROM public.regular_task_run_items WHERE regular_task_id=:rid"),
            {"rid": int(regular_task_id)},
        )
    if _table_exists(conn, "tasks") and _col_exists(conn, "tasks", "regular_task_id"):
        conn.execute(
            text("DELETE FROM public.tasks WHERE regular_task_id=:rid"),
            {"rid": int(regular_task_id)},
        )
    conn.execute(
        text("DELETE FROM public.regular_tasks WHERE regular_task_id=:rid"),
        {"rid": int(regular_task_id)},
    )


def test_run_now_writes_run_item_for_regular_task():
    client = TestClient(app)

    with engine.begin() as conn:
        if not _table_exists(conn, "regular_task_run_items"):
            pytest.skip("Таблица regular_task_run_items отсутствует. Сначала примените миграцию.")
        if not _table_exists(conn, "regular_tasks"):
            pytest.skip("Таблица regular_tasks отсутствует.")

        rid = _insert_due_regular_task(conn)
        before = _count_run_items(conn, rid)

    try:
        path, resp = _call_run_now(client, rid)
        assert resp.status_code in (200, 201, 202), f"{path} вернул {resp.status_code}"

        with engine.connect() as conn:
            after = _count_run_items(conn, rid)

        assert after >= before + 1, (
            "После run-now не появилась запись в regular_task_run_items для regular_task_id.\n"
            f"before={before}, after={after}, regular_task_id={rid}, endpoint={path}"
        )
    finally:
        with engine.begin() as conn:
            _cleanup(conn, rid)
