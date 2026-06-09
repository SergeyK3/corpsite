# tests/test_tasks_list_search.py
from __future__ import annotations

from tests.conftest import auth_headers, cleanup_task, create_task


def _list_tasks(client, user_id: int, **params):
    return client.get("/tasks", params=params, headers=auth_headers(user_id))


def test_search_finds_task_not_on_first_page(client, seed):
    unique_title = "PytestSearchBeyondFirstPage"
    task_ids: list[int] = []

    try:
        target_id = create_task(
            period_id=seed["period_id"],
            title=unique_title,
            initiator_user_id=seed["initiator_user_id"],
            executor_role_id=seed["executor_role_id"],
            assignment_scope=seed["assignment_scope"],
            status_code="WAITING_REPORT",
            unit_id=seed["unit_id"],
        )
        task_ids.append(target_id)

        for i in range(3):
            task_ids.append(
                create_task(
                    period_id=seed["period_id"],
                    title=f"Pytest filler task {i}",
                    initiator_user_id=seed["initiator_user_id"],
                    executor_role_id=seed["executor_role_id"],
                    assignment_scope=seed["assignment_scope"],
                    status_code="WAITING_REPORT",
                    unit_id=seed["unit_id"],
                )
            )

        first_page = _list_tasks(
            client,
            seed["executor_user_id"],
            scope="mine",
            limit=1,
            offset=0,
            status_filter="active",
        )
        assert first_page.status_code == 200, first_page.text
        first_body = first_page.json()
        assert first_body["total"] >= 4
        assert not any(unique_title == (it.get("title") or "") for it in first_body["items"])

        searched = _list_tasks(
            client,
            seed["executor_user_id"],
            scope="mine",
            limit=50,
            search=unique_title,
            status_filter="active",
        )
        assert searched.status_code == 200, searched.text
        searched_body = searched.json()
        assert searched_body["total"] == 1
        assert len(searched_body["items"]) == 1
        assert int(searched_body["items"][0]["task_id"]) == target_id
    finally:
        for task_id in task_ids:
            cleanup_task(task_id)


def test_search_by_executor_full_name(client, seed):
    unique_name = "Pytest Search Executor Unique"
    task_ids: list[int] = []

    try:
        from app.db.engine import engine
        from sqlalchemy import text

        with engine.begin() as conn:
            conn.execute(
                text("UPDATE public.users SET full_name = :name WHERE user_id = :uid"),
                {"name": unique_name, "uid": seed["executor_user_id"]},
            )

        task_ids.append(
            create_task(
                period_id=seed["period_id"],
                title="Pytest executor-name search task",
                initiator_user_id=seed["initiator_user_id"],
                executor_role_id=seed["executor_role_id"],
                assignment_scope=seed["assignment_scope"],
                status_code="WAITING_REPORT",
                unit_id=seed["unit_id"],
            )
        )

        searched = _list_tasks(
            client,
            seed["executor_user_id"],
            scope="mine",
            limit=50,
            search="Search Executor Unique",
            status_filter="active",
        )
        assert searched.status_code == 200, searched.text
        searched_body = searched.json()
        assert searched_body["total"] >= 1
        assert any(int(it["task_id"]) == task_ids[0] for it in searched_body["items"])
    finally:
        for task_id in task_ids:
            cleanup_task(task_id)


def test_search_with_status_filter_and_task_kind(client, seed):
    unique_title = "PytestSearchDoneAdhoc"
    task_ids: list[int] = []

    try:
        task_ids.append(
            create_task(
                period_id=seed["period_id"],
                title=unique_title,
                initiator_user_id=seed["initiator_user_id"],
                executor_role_id=seed["executor_role_id"],
                assignment_scope=seed["assignment_scope"],
                status_code="DONE",
                unit_id=seed["unit_id"],
            )
        )

        active_only = _list_tasks(
            client,
            seed["executor_user_id"],
            scope="mine",
            search=unique_title,
            status_filter="active",
            task_kind="adhoc",
        )
        assert active_only.status_code == 200, active_only.text
        assert active_only.json()["total"] == 0

        done_match = _list_tasks(
            client,
            seed["executor_user_id"],
            scope="mine",
            search=unique_title,
            status_filter="done",
            task_kind="adhoc",
        )
        assert done_match.status_code == 200, done_match.text
        done_body = done_match.json()
        assert done_body["total"] == 1
        assert int(done_body["items"][0]["task_id"]) == task_ids[0]
    finally:
        for task_id in task_ids:
            cleanup_task(task_id)


def test_search_does_not_leak_tasks_outside_mine_scope(client, seed):
    unique_title = "PytestSearchRbacHidden"
    task_ids: list[int] = []

    try:
        task_ids.append(
            create_task(
                period_id=seed["period_id"],
                title=unique_title,
                initiator_user_id=seed["initiator_user_id"],
                executor_role_id=seed["executor_role_id"],
                assignment_scope=seed["assignment_scope"],
                status_code="WAITING_REPORT",
                unit_id=seed["unit_id"],
            )
        )

        executor_view = _list_tasks(
            client,
            seed["executor_user_id"],
            scope="mine",
            search=unique_title,
            status_filter="active",
        )
        assert executor_view.status_code == 200, executor_view.text
        assert executor_view.json()["total"] == 1

        initiator_view = _list_tasks(
            client,
            seed["initiator_user_id"],
            scope="mine",
            search=unique_title,
            status_filter="active",
        )
        assert initiator_view.status_code == 200, initiator_view.text
        assert initiator_view.json()["total"] == 0
        assert initiator_view.json()["items"] == []
    finally:
        for task_id in task_ids:
            cleanup_task(task_id)
