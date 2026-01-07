# tests/test_tasks_allowed_actions.py
from __future__ import annotations

from tests.conftest import create_task, cleanup_task, upsert_report


def test_executor_sees_report_action_on_waiting_report(client, seed):
    task_id = create_task(
        period_id=seed["period_id"],
        title=seed["title"],
        initiator_user_id=seed["initiator_user_id"],
        executor_role_id=seed["executor_role_id"],
        assignment_scope=seed["assignment_scope"],
        status_code="WAITING_REPORT",
    )

    try:
        r = client.get(f"/tasks/{task_id}", headers={"X-User-Id": str(seed["executor_user_id"])})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status_code"] == "WAITING_REPORT"
        assert "report" in data.get("allowed_actions", [])
    finally:
        cleanup_task(task_id)


def test_initiator_sees_approve_and_reject_on_waiting_approval(client, seed):
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
            current_comment="test",
        )

        r = client.get(f"/tasks/{task_id}", headers={"X-User-Id": str(seed["initiator_user_id"])})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status_code"] == "WAITING_APPROVAL"
        aa = data.get("allowed_actions", [])
        assert "approve" in aa
        assert "reject" in aa
    finally:
        cleanup_task(task_id)
