# tests/test_regular_tasks_run_journal_acl.py
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.main import app
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

    unit_id = create_unit(conn, "pytest_rt_run_journal_admin_unit")
    return create_user(
        conn,
        full_name="Pytest RT Run Journal Admin",
        role_id=int(SYSTEM_ADMIN_ROLE_ID),
        unit_id=unit_id,
    )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_sysadmin_can_list_regular_task_runs(client: TestClient, seed):
    with engine.begin() as conn:
        if not table_exists(conn, "regular_task_runs"):
            pytest.skip("regular_task_runs table not available")
        admin_user_id = _admin_user_id(conn)

    resp = client.get("/regular-task-runs", headers=auth_headers(admin_user_id))
    assert resp.status_code == 200, resp.text
    assert isinstance(resp.json(), list)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_sysadmin_can_list_regular_task_run_items(client: TestClient, seed):
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


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_run_items_with_null_timestamps(client: TestClient, seed):
    with engine.begin() as conn:
        if not table_exists(conn, "regular_task_runs"):
            pytest.skip("regular_task_runs table not available")
        if not table_exists(conn, "regular_task_run_items"):
            pytest.skip("regular_task_run_items table not available")
        admin_user_id = _admin_user_id(conn)
        regular_task_id = conn.execute(
            text("SELECT regular_task_id FROM public.regular_tasks LIMIT 1")
        ).scalar()
        if regular_task_id is None:
            pytest.skip("regular_tasks table has no rows for FK")
        run_id = conn.execute(
            text(
                """
                INSERT INTO public.regular_task_runs (started_at, status, stats, errors)
                VALUES (now(), 'ok', '{}'::jsonb, '[]'::jsonb)
                RETURNING run_id
                """
            )
        ).scalar_one()
        item_id = conn.execute(
            text(
                """
                INSERT INTO public.regular_task_run_items (
                    run_id,
                    regular_task_id,
                    status,
                    is_due,
                    created_tasks,
                    started_at,
                    finished_at,
                    meta
                )
                VALUES (
                    :run_id,
                    :regular_task_id,
                    'ok',
                    TRUE,
                    0,
                    NULL,
                    NULL,
                    '{}'::jsonb
                )
                RETURNING item_id
                """
            ),
            {"run_id": int(run_id), "regular_task_id": int(regular_task_id)},
        ).scalar_one()

    try:
        resp = client.get(
            f"/regular-task-runs/{int(run_id)}/items",
            headers=auth_headers(admin_user_id),
        )
        assert resp.status_code == 200, resp.text
        items = resp.json()
        assert isinstance(items, list)
        assert len(items) == 1
        assert items[0]["item_id"] == int(item_id)
        assert items[0]["started_at"] is None
        assert items[0]["finished_at"] is None
    finally:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM public.regular_task_runs WHERE run_id = :run_id"),
                {"run_id": int(run_id)},
            )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_regular_employee_cannot_access_run_journal(client: TestClient, seed):
    with engine.begin() as conn:
        if not table_exists(conn, "regular_task_runs"):
            pytest.skip("regular_task_runs table not available")

    resp = client.get(
        "/regular-task-runs",
        headers=auth_headers(int(seed["executor_user_id"])),
    )
    assert resp.status_code == 403
