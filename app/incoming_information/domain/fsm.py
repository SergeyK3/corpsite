"""Incoming Information workflow FSM rules."""
from __future__ import annotations

from app.incoming_information.domain.status import (
    STATUS_ASSIGNED,
    STATUS_CANCELLED,
    STATUS_CLOSED,
    STATUS_IN_PROGRESS,
    STATUS_REGISTERED,
    STATUS_RESOLVED,
    STATUS_TRANSFERRED,
    STATUS_WAITING_INFORMATION,
)

ASSIGN_SOURCE_STATUSES: frozenset[str] = frozenset({STATUS_REGISTERED})

REASSIGN_SOURCE_STATUSES: frozenset[str] = frozenset(
    {STATUS_ASSIGNED, STATUS_IN_PROGRESS, STATUS_WAITING_INFORMATION}
)

INTERNAL_TRANSFER_SOURCE_STATUSES: frozenset[str] = frozenset(
    {STATUS_REGISTERED, STATUS_ASSIGNED, STATUS_IN_PROGRESS, STATUS_WAITING_INFORMATION}
)

EXTERNAL_TRANSFER_SOURCE_STATUSES: frozenset[str] = frozenset(
    {STATUS_REGISTERED, STATUS_ASSIGNED, STATUS_IN_PROGRESS, STATUS_WAITING_INFORMATION}
)

START_SOURCE_STATUSES: frozenset[str] = frozenset({STATUS_ASSIGNED})

WAIT_SOURCE_STATUSES: frozenset[str] = frozenset({STATUS_IN_PROGRESS})

RESUME_SOURCE_STATUSES: frozenset[str] = frozenset({STATUS_WAITING_INFORMATION})

CHANGE_DEADLINE_SOURCE_STATUSES: frozenset[str] = frozenset(
    {
        STATUS_REGISTERED,
        STATUS_ASSIGNED,
        STATUS_IN_PROGRESS,
        STATUS_WAITING_INFORMATION,
    }
)

RESOLVE_SOURCE_STATUSES: frozenset[str] = frozenset(
    {STATUS_IN_PROGRESS, STATUS_WAITING_INFORMATION}
)

CLOSE_SOURCE_STATUSES: frozenset[str] = frozenset({STATUS_RESOLVED})

REOPEN_SOURCE_STATUSES: frozenset[str] = frozenset({STATUS_CLOSED})

CANCEL_REGISTER_STATUSES: frozenset[str] = frozenset({STATUS_REGISTERED, STATUS_ASSIGNED})

CANCEL_CONTROL_STATUSES: frozenset[str] = frozenset(
    {STATUS_IN_PROGRESS, STATUS_WAITING_INFORMATION}
)

STATUSES_REQUIRING_ACTIVE_PRIMARY: frozenset[str] = frozenset(
    {STATUS_ASSIGNED, STATUS_IN_PROGRESS, STATUS_WAITING_INFORMATION}
)


def assert_status_in(source_status: str, allowed: frozenset[str], *, operation: str) -> None:
    if source_status not in allowed:
        raise ValueError(
            f"Operation {operation} is not allowed from status {source_status}."
        )
