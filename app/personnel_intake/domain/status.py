"""Intake link and draft status constants (WP-PPR-INTAKE-001)."""
from __future__ import annotations

INTAKE_LINK_STATUS_ISSUED = "issued"
INTAKE_LINK_STATUS_OPENED = "opened"
INTAKE_LINK_STATUS_SUBMITTED = "submitted"
INTAKE_LINK_STATUS_EXPIRED = "expired"
INTAKE_LINK_STATUS_REVOKED = "revoked"

INTAKE_LINK_STATUSES: tuple[str, ...] = (
    INTAKE_LINK_STATUS_ISSUED,
    INTAKE_LINK_STATUS_OPENED,
    INTAKE_LINK_STATUS_SUBMITTED,
    INTAKE_LINK_STATUS_EXPIRED,
    INTAKE_LINK_STATUS_REVOKED,
)

INTAKE_DRAFT_STATUS_EDITABLE = "editable"
INTAKE_DRAFT_STATUS_SUBMITTED = "submitted"

INTAKE_DRAFT_STATUSES: tuple[str, ...] = (
    INTAKE_DRAFT_STATUS_EDITABLE,
    INTAKE_DRAFT_STATUS_SUBMITTED,
)

# Link statuses that allow candidate read/write access.
INTAKE_LINK_ACTIVE_STATUSES: frozenset[str] = frozenset(
    {
        INTAKE_LINK_STATUS_ISSUED,
        INTAKE_LINK_STATUS_OPENED,
    }
)

# Link statuses HR can revoke from the personnel application card.
INTAKE_LINK_REVOCABLE_STATUSES: frozenset[str] = frozenset(
    {
        INTAKE_LINK_STATUS_ISSUED,
        INTAKE_LINK_STATUS_OPENED,
        INTAKE_LINK_STATUS_SUBMITTED,
    }
)


def is_intake_link_usable(status: str) -> bool:
    return status in INTAKE_LINK_ACTIVE_STATUSES


def is_intake_draft_editable(status: str) -> bool:
    return status == INTAKE_DRAFT_STATUS_EDITABLE
