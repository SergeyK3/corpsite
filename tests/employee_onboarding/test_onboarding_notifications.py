# tests/employee_onboarding/test_onboarding_notifications.py
"""Notification and reminder tests (WP-ONBOARDING-002)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.employee_onboarding.application.bootstrap_service import create_onboarding_from_hire
from app.employee_onboarding.application.reminder_service import run_onboarding_reminders
from app.employee_onboarding.domain.status import NOTIFICATION_TASK_DUE_SOON, NOTIFICATION_TASK_OVERDUE
from tests.conftest import table_exists
from tests.ppr.conftest import cleanup_person_graph, insert_employee, insert_person, ppr_db_available

pytestmark = pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")


@pytest.fixture
def onboarding_schema_ready():
    with engine.begin() as conn:
        if not table_exists(conn, "employee_onboarding_notifications"):
            pytest.skip("WP-ONBOARDING-002 migration missing — run: alembic upgrade head")


def test_reminder_service_sends_due_soon_and_overdue(onboarding_schema_ready, seed) -> None:
    person_ids: list[int] = []
    employee_ids: list[int] = []
    try:
        with engine.begin() as conn:
            person_id = insert_person(conn, full_name="Reminder Test")
            person_ids.append(person_id)
            employee_id = insert_employee(conn, full_name="Reminder Test", person_id=person_id)
            employee_ids.append(employee_id)
            bootstrap = create_onboarding_from_hire(
                conn,
                employee_id=employee_id,
                application_id=None,
                responsible_hr_id=int(seed["initiator_user_id"]),
            )
            due_soon_item = conn.execute(
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
            overdue_item = conn.execute(
                text(
                    """
                    SELECT item_id
                    FROM public.employee_onboarding_checklist_items
                    WHERE onboarding_id = :onboarding_id
                    ORDER BY sort_order ASC
                    OFFSET 1
                    LIMIT 1
                    """
                ),
                {"onboarding_id": bootstrap.onboarding_id},
            ).scalar_one()
            now = datetime.now(UTC)
            conn.execute(
                text(
                    """
                    UPDATE public.employee_onboarding_checklist_items
                    SET due_date = :due_date
                    WHERE item_id = :item_id
                    """
                ),
                {"item_id": due_soon_item, "due_date": now + timedelta(days=2)},
            )
            conn.execute(
                text(
                    """
                    UPDATE public.employee_onboarding_checklist_items
                    SET due_date = :due_date
                    WHERE item_id = :item_id
                    """
                ),
                {"item_id": overdue_item, "due_date": now - timedelta(days=1)},
            )
            result = run_onboarding_reminders(conn, now=now)
        assert result.due_soon_sent >= 1
        assert result.overdue_sent >= 1
        with engine.connect() as conn:
            types = conn.execute(
                text(
                    """
                    SELECT DISTINCT event_type
                    FROM public.employee_onboarding_notifications
                    WHERE onboarding_id = :onboarding_id
                    """
                ),
                {"onboarding_id": bootstrap.onboarding_id},
            ).scalars().all()
        assert NOTIFICATION_TASK_DUE_SOON in types
        assert NOTIFICATION_TASK_OVERDUE in types
    finally:
        with engine.begin() as conn:
            cleanup_person_graph(conn, person_ids=person_ids, employee_ids=employee_ids)
