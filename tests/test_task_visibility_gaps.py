# tests/test_task_visibility_gaps.py
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.db.engine import engine
from app.services.tasks_service import ensure_task_visible_or_404, get_user_role_id, load_task_full


@pytest.mark.parametrize(
    "user_id, task_id",
    [
        (5, 10001),  # pure legacy approver
        (3, 10002),  # historical report author
    ],
)
def test_fixture_visibility_gaps_pass_ensure(user_id: int, task_id: int) -> None:
    with engine.begin() as conn:
        role_id = get_user_role_id(conn, int(user_id))
        task = load_task_full(conn, task_id=int(task_id))
        if task is None:
            pytest.skip(f"fixture task_id={task_id} not present; apply rbac_visibility_gaps_fixture.sql")

        result = ensure_task_visible_or_404(
            conn=conn,
            current_user_id=int(user_id),
            current_role_id=int(role_id),
            task_row=task,
            include_archived=False,
        )
        assert int(result["task_id"]) == int(task_id)


@pytest.mark.parametrize(
    "user_id, task_id",
    [
        (5, 10001),
        (3, 10002),
    ],
)
def test_fixture_visibility_gaps_do_not_raise_404_on_ensure(user_id: int, task_id: int) -> None:
    with engine.begin() as conn:
        role_id = get_user_role_id(conn, int(user_id))
        task = load_task_full(conn, task_id=int(task_id))
        if task is None:
            pytest.skip(f"fixture task_id={task_id} not present; apply rbac_visibility_gaps_fixture.sql")

        try:
            ensure_task_visible_or_404(
                conn=conn,
                current_user_id=int(user_id),
                current_role_id=int(role_id),
                task_row=task,
                include_archived=False,
            )
        except HTTPException as exc:
            pytest.fail(f"ensure_task_visible_or_404 raised {exc.status_code}: {exc.detail}")
