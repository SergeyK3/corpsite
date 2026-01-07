# tests/test_tasks_actions_endpoint.py
from __future__ import annotations

from tests.conftest import create_task, cleanup_task, upsert_report


def test_actions_report_moves_to_waiting_approval(client, seed):
    task_id = create_task(
        period_id=seed["period_id"],
        title=seed["title"],
        initiator_user_id=seed["initiator_user_id"],
        executor_role_id=seed["executor_role_id"],
        assignment_scope=seed["assignment_scope"],
        status_code="WAITING_REPORT",
    )

    try:
        payload = {"report_link": "https://example.com/r", "current_comment": "ok"}
        r = client.post(
            f"/tasks/{task_id}/actions/report",
            json=payload,
            headers={"X-User-Id": str(seed["executor_user_id"])},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status_code"] == "WAITING_APPROVAL"
        assert "report" not in data.get("allowed_actions", [])
    finally:
        cleanup_task(task_id)


def test_actions_reject_moves_back_to_waiting_report(client, seed):
    task_id = create_task(
        period_id=seed["period_id"],
        title=seed["title"],
        initiator_user_id=seed["initiator_user_id"],
        executor_role_id=seed["executor_role_id"],
        assignment_scope=seed["assignment_scope"],
        status_code="WAITING_APPROVAL",
    )

    try:
        upsert_report(
            task_id=task_id,
            submitted_by=seed["executor_user_id"],
            report_link="https://example.com/report",
            current_comment="initial",
        )

        r = client.post(
            f"/tasks/{task_id}/actions/reject",
            json={"current_comment": "need fix"},
            headers={"X-User-Id": str(seed["initiator_user_id"])},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status_code"] == "WAITING_REPORT"
    finally:
        cleanup_task(task_id)
