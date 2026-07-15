"""PPR lifecycle transition rules (WP-PR-004 — R5 application validation)."""
from __future__ import annotations

from app.ppr.domain.errors import PprLifecycleTransitionError
from app.ppr.domain.models import (
    PPR_LIFECYCLE_ACTIVE,
    PPR_LIFECYCLE_ARCHIVED,
    PPR_LIFECYCLE_COLLECTING,
    PPR_LIFECYCLE_CREATED,
    PPR_LIFECYCLE_MERGED,
    PPR_LIFECYCLE_READY,
)

COMMAND_TYPE_START_COLLECTION = "StartCollection"
COMMAND_TYPE_ACTIVATE_PPR = "ActivatePPR"

LIFECYCLE_MUTATION_ALLOWED = frozenset(
    {
        PPR_LIFECYCLE_CREATED,
        PPR_LIFECYCLE_COLLECTING,
        PPR_LIFECYCLE_READY,
        PPR_LIFECYCLE_ACTIVE,
    }
)


def validate_start_collection(current_state: str) -> str:
    if current_state == PPR_LIFECYCLE_CREATED:
        return PPR_LIFECYCLE_COLLECTING
    if current_state == PPR_LIFECYCLE_COLLECTING:
        return PPR_LIFECYCLE_COLLECTING
    raise PprLifecycleTransitionError(
        f"StartCollection not allowed from lifecycle_state={current_state!r}"
    )


def validate_activate_ppr(current_state: str) -> str:
    if current_state in {PPR_LIFECYCLE_CREATED, PPR_LIFECYCLE_COLLECTING, PPR_LIFECYCLE_READY}:
        return PPR_LIFECYCLE_ACTIVE
    if current_state == PPR_LIFECYCLE_ACTIVE:
        return PPR_LIFECYCLE_ACTIVE
    raise PprLifecycleTransitionError(
        f"ActivatePPR not allowed from lifecycle_state={current_state!r}"
    )


def assert_lifecycle_allows_section_mutation(lifecycle_state: str) -> None:
    if lifecycle_state not in LIFECYCLE_MUTATION_ALLOWED:
        raise PprLifecycleTransitionError(
            f"Section mutation not allowed in lifecycle_state={lifecycle_state!r}"
        )


def is_terminal_lifecycle(lifecycle_state: str) -> bool:
    return lifecycle_state in {PPR_LIFECYCLE_ARCHIVED, PPR_LIFECYCLE_MERGED}
