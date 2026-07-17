# tests/personnel_applications/test_status_domain.py
"""Unit tests for Personnel Application status predicates."""
from __future__ import annotations

from app.personnel_applications.domain.status import (
    APPLICATION_STATUS_EXPIRED,
    APPLICATION_STATUS_REGISTERED,
    APPLICATION_STATUS_WITHDRAWN,
    is_active_application_status,
    is_terminal_application_status,
    terminal_statuses_for_partial_index,
)


def test_terminal_and_active_complement() -> None:
    assert is_terminal_application_status(APPLICATION_STATUS_WITHDRAWN)
    assert not is_active_application_status(APPLICATION_STATUS_WITHDRAWN)
    assert is_active_application_status(APPLICATION_STATUS_REGISTERED)
    assert not is_terminal_application_status(APPLICATION_STATUS_REGISTERED)


def test_terminal_set_for_index_is_sorted_tuple() -> None:
    terminals = terminal_statuses_for_partial_index()
    assert terminals == tuple(sorted(terminals))
    assert "completed" in terminals
    assert "resolution_rejected" in terminals
    assert "rejected" in terminals
    assert "expired" in terminals
    assert is_terminal_application_status(APPLICATION_STATUS_EXPIRED)
    assert not is_active_application_status(APPLICATION_STATUS_EXPIRED)
