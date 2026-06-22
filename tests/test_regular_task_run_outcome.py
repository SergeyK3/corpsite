# FILE: tests/test_regular_task_run_outcome.py
from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.services.regular_task_run_outcome import (
    _compute_outcome_counts,
    load_regular_task_run_items_with_outcome,
)
from app.services.tasks_service import SYSTEM_ADMIN_ROLE_ID
from tests.conftest import auth_headers, create_unit, create_user, table_exists


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

    unit_id = create_unit(conn, "pytest_rt_outcome_admin_unit")
    return create_user(
        conn,
        full_name="Pytest RT Outcome Admin",
        role_id=int(SYSTEM_ADMIN_ROLE_ID),
        unit_id=unit_id,
    )


def _status_id(conn, code: str) -> int:
    row = conn.execute(
        text("SELECT status_id FROM public.task_statuses WHERE code = :code"),
        {"code": code},
    ).scalar_one()
    return int(row)


def test_compute_outcome_counts_buckets():
    today = date(2026, 6, 24)
    rows = [
        {"linked_task_id": 1, "resolved_task_id": 1, "task_status_code": "DONE", "task_due_date": today},
        {
            "linked_task_id": 2,
            "resolved_task_id": 2,
            "task_status_code": "IN_PROGRESS",
            "task_due_date": today - timedelta(days=1),
        },
        {
            "linked_task_id": 3,
            "resolved_task_id": 3,
            "task_status_code": "WAITING_REPORT",
            "task_due_date": today + timedelta(days=3),
        },
        {"linked_task_id": 4, "resolved_task_id": 4, "task_status_code": "ARCHIVED", "task_due_date": None},
        {"linked_task_id": 5, "resolved_task_id": None, "task_status_code": None, "task_due_date": None},
        {"linked_task_id": None, "resolved_task_id": None, "task_status_code": None, "task_due_date": None},
    ]

    counts = _compute_outcome_counts(rows, today=today)
    assert counts == {
        "linked": 4,
        "done": 1,
        "in_progress": 2,
        "overdue": 1,
        "archived": 1,
        "unlinked": 1,
        "other": 0,
    }


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_api_run_items_include_outcome_envelope(client: TestClient, seed):
    with engine.begin() as conn:
        if not table_exists(conn, "regular_task_runs") or not table_exists(conn, "regular_task_run_items"):
            pytest.skip("run journal tables not available")
        if not table_exists(conn, "tasks"):
            pytest.skip("tasks table not available")

        admin_user_id = _admin_user_id(conn)
        regular_task_id = conn.execute(
            text("SELECT regular_task_id FROM public.regular_tasks LIMIT 1")
        ).scalar()
        if regular_task_id is None:
            pytest.skip("regular_tasks table has no rows for FK")

        done_status_id = _status_id(conn, "DONE")
        in_progress_status_id = _status_id(conn, "IN_PROGRESS")
        archived_status_id = _status_id(conn, "ARCHIVED")
        today = date.today()

        task_done_id = conn.execute(
            text(
                """
                INSERT INTO public.tasks (
                    period_id, regular_task_id, title, initiator_user_id,
                    executor_role_id, assignment_scope, status_id, due_date,
                    task_kind, source_kind, requires_report, requires_approval
                )
                VALUES (
                    :period_id, NULL, 'pytest outcome done',
                    :initiator_user_id, :executor_role_id, :assignment_scope,
                    :status_id, :due_date, 'regular', 'regular_task', TRUE, TRUE
                )
                RETURNING task_id
                """
            ),
            {
                "period_id": int(seed["period_id"]),
                "regular_task_id": int(regular_task_id),
                "initiator_user_id": int(seed["initiator_user_id"]),
                "executor_role_id": int(seed["executor_role_id"]),
                "assignment_scope": seed["assignment_scope"],
                "status_id": done_status_id,
                "due_date": today,
            },
        ).scalar_one()

        task_overdue_id = conn.execute(
            text(
                """
                INSERT INTO public.tasks (
                    period_id, regular_task_id, title, initiator_user_id,
                    executor_role_id, assignment_scope, status_id, due_date,
                    task_kind, source_kind, requires_report, requires_approval
                )
                VALUES (
                    :period_id, NULL, 'pytest outcome overdue',
                    :initiator_user_id, :executor_role_id, :assignment_scope,
                    :status_id, :due_date, 'regular', 'regular_task', TRUE, TRUE
                )
                RETURNING task_id
                """
            ),
            {
                "period_id": int(seed["period_id"]),
                "regular_task_id": int(regular_task_id),
                "initiator_user_id": int(seed["initiator_user_id"]),
                "executor_role_id": int(seed["executor_role_id"]),
                "assignment_scope": seed["assignment_scope"],
                "status_id": in_progress_status_id,
                "due_date": today - timedelta(days=2),
            },
        ).scalar_one()

        task_archived_id = conn.execute(
            text(
                """
                INSERT INTO public.tasks (
                    period_id, regular_task_id, title, initiator_user_id,
                    executor_role_id, assignment_scope, status_id, due_date,
                    task_kind, source_kind, requires_report, requires_approval
                )
                VALUES (
                    :period_id, NULL, 'pytest outcome archived',
                    :initiator_user_id, :executor_role_id, :assignment_scope,
                    :status_id, :due_date, 'regular', 'regular_task', TRUE, TRUE
                )
                RETURNING task_id
                """
            ),
            {
                "period_id": int(seed["period_id"]),
                "regular_task_id": int(regular_task_id),
                "initiator_user_id": int(seed["initiator_user_id"]),
                "executor_role_id": int(seed["executor_role_id"]),
                "assignment_scope": seed["assignment_scope"],
                "status_id": archived_status_id,
                "due_date": today,
            },
        ).scalar_one()

        run_id = conn.execute(
            text(
                """
                INSERT INTO public.regular_task_runs (started_at, status, stats, errors)
                VALUES (now(), 'ok', '{}'::jsonb, '[]'::jsonb)
                RETURNING run_id
                """
            )
        ).scalar_one()

        meta_rows = [
            {
                "task_id": int(task_done_id),
                "period_start": "2026-06-17",
                "period_end": "2026-06-23",
            },
            {"task_id": int(task_overdue_id)},
            {"task_id": int(task_archived_id)},
            {"task_id": 999999999},
        ]
        for meta in meta_rows:
            conn.execute(
                text(
                    """
                    INSERT INTO public.regular_task_run_items (
                        run_id, regular_task_id, status, is_due, created_tasks, meta
                    )
                    VALUES (
                        :run_id, :regular_task_id, 'ok', TRUE, 1,
                        CAST(:meta AS jsonb)
                    )
                    """
                ),
                {
                    "run_id": int(run_id),
                    "regular_task_id": int(regular_task_id),
                    "meta": json.dumps(meta, ensure_ascii=False),
                },
            )

    try:
        resp = client.get(
            f"/regular-task-runs/{int(run_id)}/items",
            params={"include_outcome": "true"},
            headers=auth_headers(admin_user_id),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["run_id"] == int(run_id)
        assert len(body["items"]) == 4
        assert body["outcome"]["period_label"] == "2026-06-17–2026-06-23"
        counts = body["outcome"]["counts"]
        assert counts["linked"] == 3
        assert counts["done"] == 1
        assert counts["in_progress"] == 1
        assert counts["overdue"] == 1
        assert counts["archived"] == 1
        assert counts["unlinked"] == 1

        overdue_item = next(
            item for item in body["items"] if item["task"]["task_id"] == int(task_overdue_id)
        )
        assert overdue_item["task"]["lifecycle"] == "overdue"
        assert overdue_item["task"]["is_overdue"] is True

        with engine.begin() as conn:
            rows, outcome = load_regular_task_run_items_with_outcome(conn, run_id=int(run_id))
            assert len(rows) == 4
            assert outcome["counts"]["linked"] == 3
    finally:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM public.regular_task_run_items WHERE run_id = :run_id"),
                {"run_id": int(run_id)},
            )
            conn.execute(
                text("DELETE FROM public.regular_task_runs WHERE run_id = :run_id"),
                {"run_id": int(run_id)},
            )
            for task_id in (task_done_id, task_overdue_id, task_archived_id):
                conn.execute(
                    text("DELETE FROM public.tasks WHERE task_id = :task_id"),
                    {"task_id": int(task_id)},
                )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_api_run_items_default_still_returns_list(client: TestClient, seed):
    with engine.begin() as conn:
        if not table_exists(conn, "regular_task_runs"):
            pytest.skip("regular_task_runs table not available")
        admin_user_id = _admin_user_id(conn)
        run_id = conn.execute(
            text(
                """
                INSERT INTO public.regular_task_runs (started_at, status, stats, errors)
                VALUES (now(), 'ok', '{}'::jsonb, '[]'::jsonb)
                RETURNING run_id
                """
            )
        ).scalar_one()

    try:
        resp = client.get(
            f"/regular-task-runs/{int(run_id)}/items",
            headers=auth_headers(admin_user_id),
        )
        assert resp.status_code == 200, resp.text
        assert isinstance(resp.json(), list)
    finally:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM public.regular_task_runs WHERE run_id = :run_id"),
                {"run_id": int(run_id)},
            )
