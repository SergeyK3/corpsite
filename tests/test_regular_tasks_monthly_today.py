# FILE: tests/test_regular_tasks_monthly_today.py
# PURPOSE: Integration test (fast variant):
# run-now endpoint works + engine run is logged in regular_task_runs

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.main import app


def _pick_any_month_regular_task_id(conn) -> int | None:
    q = text(
        """
        SELECT regular_task_id
        FROM regular_tasks
        WHERE is_active = true
          AND periodicity = 'MONTH'
        ORDER BY regular_task_id
        LIMIT 1
        """
    )
    v = conn.execute(q).scalar()
    return int(v) if v is not None else None


def _count_runs_total(conn) -> int:
    return int(
        conn.execute(text("SELECT COUNT(1) FROM regular_task_runs")).scalar() or 0
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


def test_run_now_logs_engine_run():
    client = TestClient(app)

    with engine.connect() as conn:
        rid = _pick_any_month_regular_task_id(conn)
        if not rid:
            pytest.skip("В БД нет active MONTH regular_tasks. Нечего тестировать.")

        before_runs = _count_runs_total(conn)

    path, resp = _call_run_now(client, rid)
    assert resp.status_code in (200, 201, 202), f"{path} вернул {resp.status_code}"

    with engine.connect() as conn:
        after_runs = _count_runs_total(conn)

    assert after_runs >= before_runs + 1, (
        "После run-now не добавилась запись в regular_task_runs.\n"
        f"before={before_runs}, after={after_runs}\n"
        f"endpoint={path}"
    )
