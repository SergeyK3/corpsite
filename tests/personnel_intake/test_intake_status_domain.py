# tests/personnel_intake/test_intake_status_domain.py
"""Domain status tests for Personnel Intake."""
from __future__ import annotations

from app.personnel_intake.domain.status import (
    INTAKE_LINK_STATUS_ISSUED,
    INTAKE_LINK_STATUS_OPENED,
    INTAKE_LINK_STATUS_REVOKED,
    INTAKE_LINK_STATUS_SUBMITTED,
    is_intake_draft_editable,
    is_intake_link_usable,
)


def test_link_usable_statuses() -> None:
    assert is_intake_link_usable(INTAKE_LINK_STATUS_ISSUED) is True
    assert is_intake_link_usable(INTAKE_LINK_STATUS_OPENED) is True
    assert is_intake_link_usable(INTAKE_LINK_STATUS_SUBMITTED) is False
    assert is_intake_link_usable(INTAKE_LINK_STATUS_REVOKED) is False


def test_draft_editable() -> None:
    assert is_intake_draft_editable("editable") is True
    assert is_intake_draft_editable("submitted") is False
