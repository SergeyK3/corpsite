# tests/test_tasks_admin_team_scope.py
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.tasks_service import SYSTEM_ADMIN_ROLE_ID
from tests.conftest import auth_headers, cleanup_task, create_task, create_user, create_unit


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

    unit_id = create_unit(conn, "pytest_admin_team_scope_unit")
    return create_user(
        conn,
        full_name="Pytest Admin Team Scope",
        role_id=int(SYSTEM_ADMIN_ROLE_ID),
        unit_id=unit_id,
    )


def _list_tasks(client, user_id: int, **params):
    return client.get("/tasks", params=params, headers=auth_headers(user_id))


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_admin_team_scope_lists_other_executor_and_admin_role_tasks(client, seed):
    admin_role_task_id: int | None = None
    other_role_task_id: int | None = None

    try:
        with engine.begin() as conn:
            admin_user_id = _admin_user_id(conn)

        admin_role_task_id = create_task(
            period_id=seed["period_id"],
            title="Pytest admin-scope admin-role executor",
            initiator_user_id=seed["initiator_user_id"],
            executor_role_id=int(SYSTEM_ADMIN_ROLE_ID),
            assignment_scope=seed["assignment_scope"],
            status_code="IN_PROGRESS",
            unit_id=seed.get("unit_id"),
        )
        other_role_task_id = create_task(
            period_id=seed["period_id"],
            title="Pytest admin-scope other executor",
            initiator_user_id=seed["initiator_user_id"],
            executor_role_id=seed["executor_role_id"],
            assignment_scope=seed["assignment_scope"],
            status_code="IN_PROGRESS",
            unit_id=seed.get("unit_id"),
        )

        with engine.begin() as conn:
            admin_user_id = _admin_user_id(conn)

        resp = _list_tasks(
            client,
            admin_user_id,
            scope="team",
            limit=200,
            status_filter="active",
            search="Pytest admin-scope",
        )
        assert resp.status_code == 200, resp.text
        ids = {int(x["task_id"]) for x in resp.json().get("items") or []}
        assert admin_role_task_id in ids
        assert other_role_task_id in ids
    finally:
        if admin_role_task_id is not None:
            cleanup_task(admin_role_task_id)
        if other_role_task_id is not None:
            cleanup_task(other_role_task_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_regular_executor_team_scope_forbidden(client, seed):
    resp = _list_tasks(
        client,
        seed["executor_user_id"],
        scope="team",
        limit=50,
        status_filter="active",
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_admin_can_archive_other_executor_task(client, seed):
    task_id: int | None = None
    try:
        task_id = create_task(
            period_id=seed["period_id"],
            title="Pytest admin archive other executor",
            initiator_user_id=seed["initiator_user_id"],
            executor_role_id=seed["executor_role_id"],
            assignment_scope=seed["assignment_scope"],
            status_code="IN_PROGRESS",
            unit_id=seed.get("unit_id"),
        )

        with engine.begin() as conn:
            admin_user_id = _admin_user_id(conn)

        archive = client.post(
            f"/tasks/{task_id}/archive",
            json={},
            headers=auth_headers(admin_user_id),
        )
        assert archive.status_code == 200, archive.text

        with engine.begin() as conn:
            code = conn.execute(
                text(
                    """
                    SELECT ts.code
                    FROM public.tasks t
                    JOIN public.task_statuses ts ON ts.status_id = t.status_id
                    WHERE t.task_id = :tid
                    """
                ),
                {"tid": int(task_id)},
            ).scalar_one()
        assert str(code) == "ARCHIVED"
    finally:
        if task_id is not None:
            cleanup_task(task_id)
