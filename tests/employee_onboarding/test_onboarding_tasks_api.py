# tests/employee_onboarding/test_onboarding_tasks_api.py
"""API tests for onboarding tasks (WP-ONBOARDING-002)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.employee_onboarding.application.bootstrap_service import create_onboarding_from_hire
from app.employee_onboarding.domain.status import NOTIFICATION_TASK_ASSIGNED, NOTIFICATION_TASK_COMPLETED
from app.main import app
from tests.conftest import auth_headers, table_exists
from tests.ppr.conftest import cleanup_person_graph, insert_employee, insert_person, ppr_db_available

pytestmark = pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def onboarding_schema_ready():
    with engine.begin() as conn:
        if not table_exists(conn, "employee_onboardings"):
            pytest.skip("employee_onboardings missing — run: alembic upgrade head")
        if not table_exists(conn, "employee_onboarding_notifications"):
            pytest.skip("WP-ONBOARDING-002 migration missing — run: alembic upgrade head")


def _bootstrap(conn, seed, full_name: str) -> tuple[int, int, list[int], list[int]]:
    person_ids: list[int] = []
    employee_ids: list[int] = []
    person_id = insert_person(conn, full_name=full_name)
    person_ids.append(person_id)
    employee_id = insert_employee(conn, full_name=full_name, person_id=person_id)
    employee_ids.append(employee_id)
    bootstrap = create_onboarding_from_hire(
        conn,
        employee_id=employee_id,
        application_id=None,
        responsible_hr_id=int(seed["initiator_user_id"]),
    )
    item_id = conn.execute(
        text(
            """
            SELECT item_id
            FROM public.employee_onboarding_checklist_items
            WHERE onboarding_id = :onboarding_id
            ORDER BY sort_order ASC
            LIMIT 1
            """
        ),
        {"onboarding_id": bootstrap.onboarding_id},
    ).scalar_one()
    return bootstrap.onboarding_id, int(item_id), person_ids, employee_ids


def test_patch_task_updates_due_date_and_priority(
    client, onboarding_schema_ready, privileged_headers, seed
) -> None:
    person_ids: list[int] = []
    employee_ids: list[int] = []
    try:
        with engine.begin() as conn:
            onboarding_id, item_id, person_ids, employee_ids = _bootstrap(
                conn, seed, "Task Patch Test"
            )
        due = (datetime.now(UTC) + timedelta(days=5)).isoformat()
        resp = client.patch(
            f"/directory/employee-onboarding/{onboarding_id}/checklist/{item_id}",
            json={"due_date": due, "priority": "high"},
            headers=privileged_headers,
        )
        assert resp.status_code == 200, resp.text
        item = resp.json()["checklist_items"][0]
        assert item["priority"] == "high"
        assert item["due_date"] is not None
    finally:
        with engine.begin() as conn:
            cleanup_person_graph(conn, person_ids=person_ids, employee_ids=employee_ids)


def test_add_attachment_and_audit(
    client, onboarding_schema_ready, privileged_headers, seed
) -> None:
    person_ids: list[int] = []
    employee_ids: list[int] = []
    try:
        with engine.begin() as conn:
            onboarding_id, item_id, person_ids, employee_ids = _bootstrap(
                conn, seed, "Attachment Test"
            )
        attach = client.post(
            f"/directory/employee-onboarding/{onboarding_id}/checklist/{item_id}/attachments",
            json={"file_url": "https://example.com/doc.pdf", "file_comment": "scan"},
            headers=privileged_headers,
        )
        assert attach.status_code == 200, attach.text
        item = next(i for i in attach.json()["checklist_items"] if i["item_id"] == item_id)
        assert len(item["attachments"]) == 1
        audit = client.get(
            f"/directory/employee-onboarding/{onboarding_id}/checklist/{item_id}/audit",
            headers=privileged_headers,
        )
        assert audit.status_code == 200, audit.text
        actions = [row["action"] for row in audit.json()["items"]]
        assert "attachment_added" in actions
    finally:
        with engine.begin() as conn:
            cleanup_person_graph(conn, person_ids=person_ids, employee_ids=employee_ids)


def test_bulk_complete_tasks(client, onboarding_schema_ready, privileged_headers, seed) -> None:
    person_ids: list[int] = []
    employee_ids: list[int] = []
    try:
        with engine.begin() as conn:
            onboarding_id, item_id, person_ids, employee_ids = _bootstrap(
                conn, seed, "Bulk Complete Test"
            )
            item_ids = conn.execute(
                text(
                    """
                    SELECT item_id
                    FROM public.employee_onboarding_checklist_items
                    WHERE onboarding_id = :onboarding_id
                    ORDER BY sort_order ASC
                    LIMIT 2
                    """
                ),
                {"onboarding_id": onboarding_id},
            ).scalars().all()
        resp = client.post(
            "/directory/employee-onboarding/tasks/bulk/complete",
            json={"item_ids": [int(x) for x in item_ids]},
            headers=privileged_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["succeeded"] >= 1
        assert body["failed"] == 0
    finally:
        with engine.begin() as conn:
            cleanup_person_graph(conn, person_ids=person_ids, employee_ids=employee_ids)


def test_dashboard_endpoint(client, onboarding_schema_ready, privileged_headers, seed) -> None:
    person_ids: list[int] = []
    employee_ids: list[int] = []
    try:
        with engine.begin() as conn:
            _, _, person_ids, employee_ids = _bootstrap(conn, seed, "Dashboard Test")
        resp = client.get("/directory/employee-onboarding/dashboard", headers=privileged_headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "active_programs_count" in body
        assert "overdue_tasks_count" in body
        assert "completion_percent" in body
    finally:
        with engine.begin() as conn:
            cleanup_person_graph(conn, person_ids=person_ids, employee_ids=employee_ids)


def test_task_journal_filters_overdue(client, onboarding_schema_ready, privileged_headers, seed) -> None:
    person_ids: list[int] = []
    employee_ids: list[int] = []
    try:
        with engine.begin() as conn:
            onboarding_id, item_id, person_ids, employee_ids = _bootstrap(
                conn, seed, "Overdue Journal Test"
            )
            conn.execute(
                text(
                    """
                    UPDATE public.employee_onboarding_checklist_items
                    SET due_date = :due_date
                    WHERE item_id = :item_id
                    """
                ),
                {
                    "item_id": item_id,
                    "due_date": datetime.now(UTC) - timedelta(days=2),
                },
            )
        resp = client.get(
            "/directory/employee-onboarding/tasks?overdue_only=true",
            headers=privileged_headers,
        )
        assert resp.status_code == 200, resp.text
        items = resp.json()["items"]
        assert any(row["item_id"] == item_id and row["is_overdue"] for row in items)
    finally:
        with engine.begin() as conn:
            cleanup_person_graph(conn, person_ids=person_ids, employee_ids=employee_ids)


def test_notification_on_complete(client, onboarding_schema_ready, privileged_headers, seed) -> None:
    person_ids: list[int] = []
    employee_ids: list[int] = []
    try:
        with engine.begin() as conn:
            onboarding_id, item_id, person_ids, employee_ids = _bootstrap(
                conn, seed, "Notification Complete Test"
            )
        complete = client.post(
            f"/directory/employee-onboarding/{onboarding_id}/checklist/{item_id}/complete",
            json={},
            headers=privileged_headers,
        )
        assert complete.status_code == 200, complete.text
        with engine.connect() as conn:
            count = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.employee_onboarding_notifications
                    WHERE item_id = :item_id
                      AND event_type IN (:assigned, :completed)
                    """
                ),
                {
                    "item_id": item_id,
                    "assigned": NOTIFICATION_TASK_ASSIGNED,
                    "completed": NOTIFICATION_TASK_COMPLETED,
                },
            ).scalar_one()
        assert int(count) >= 1
    finally:
        with engine.begin() as conn:
            cleanup_person_graph(conn, person_ids=person_ids, employee_ids=employee_ids)
