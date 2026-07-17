# tests/employee_onboarding/test_onboarding_domain.py
"""Unit tests for employee onboarding domain."""
from __future__ import annotations

from app.employee_onboarding.domain.status import (
    ONBOARDING_STATUS_COMPLETED,
    is_onboarding_editable,
    is_terminal_onboarding_status,
)
from app.employee_onboarding.infrastructure.repository import compute_progress_percent
from app.employee_onboarding.domain.models import OnboardingChecklistItemSnapshot
from datetime import UTC, datetime


def _item(status: str) -> OnboardingChecklistItemSnapshot:
    now = datetime.now(UTC)
    return OnboardingChecklistItemSnapshot(
        item_id=1,
        onboarding_id=1,
        item_code="lna_introduction",
        title="Test",
        sort_order=0,
        is_custom=False,
        status=status,
        completed_at=None,
        completed_by_user_id=None,
        comment=None,
        due_date=None,
        assignee_kind="hr",
        assignee_user_id=None,
        assignee_employee_id=None,
        priority="normal",
        created_at=now,
        updated_at=now,
    )


def test_terminal_statuses() -> None:
    assert is_terminal_onboarding_status(ONBOARDING_STATUS_COMPLETED)
    assert not is_onboarding_editable(ONBOARDING_STATUS_COMPLETED)


def test_progress_percent() -> None:
    items = [_item("pending"), _item("completed"), _item("skipped"), _item("pending")]
    assert compute_progress_percent(items) == 50
