"""MRD domain invariant guards (ADR-058 / MRD-Business-Invariants)."""
from __future__ import annotations

from app.mrd.domain.errors import (
    DifferenceLifecycleError,
    DifferenceOriginError,
    MrdMutationForbiddenError,
)
from app.mrd.domain.types import (
    DIFFERENCE_LIFECYCLE_CONFIRMED,
    DIFFERENCE_LIFECYCLE_DETECTED,
    DIFFERENCE_LIFECYCLE_REJECTED,
    DIFFERENCE_LIFECYCLE_SUPERSEDED,
    MRD_STATUS_ACTIVE,
    MRD_STATUS_CLOSED,
    TERMINAL_DIFFERENCE_LIFECYCLE_STATUSES,
)

_ALLOWED_LIFECYCLE_TRANSITIONS: dict[str, frozenset[str]] = {
    DIFFERENCE_LIFECYCLE_DETECTED: frozenset(
        {
            DIFFERENCE_LIFECYCLE_DETECTED,
            DIFFERENCE_LIFECYCLE_CONFIRMED,
            DIFFERENCE_LIFECYCLE_REJECTED,
            DIFFERENCE_LIFECYCLE_SUPERSEDED,
        }
    ),
    DIFFERENCE_LIFECYCLE_CONFIRMED: frozenset({DIFFERENCE_LIFECYCLE_CONFIRMED}),
    DIFFERENCE_LIFECYCLE_REJECTED: frozenset({DIFFERENCE_LIFECYCLE_REJECTED}),
    DIFFERENCE_LIFECYCLE_SUPERSEDED: frozenset({DIFFERENCE_LIFECYCLE_SUPERSEDED}),
}


def is_terminal_lifecycle(status: str) -> bool:
    return status in TERMINAL_DIFFERENCE_LIFECYCLE_STATUSES


def validate_lifecycle_transition(current_status: str, next_status: str) -> None:
    allowed = _ALLOWED_LIFECYCLE_TRANSITIONS.get(current_status)
    if allowed is None or next_status not in allowed:
        raise DifferenceLifecycleError(
            f"Detected Difference lifecycle transition {current_status!r} -> {next_status!r} is forbidden"
        )


def validate_mrd_status_for_entry_mutation(mrd_status: str) -> None:
    if mrd_status != MRD_STATUS_ACTIVE:
        raise MrdMutationForbiddenError(
            f"MRD entry mutation requires ACTIVE parent; got {mrd_status!r}"
        )


def validate_mrd_status_for_confirm(mrd_status: str) -> None:
    if mrd_status != MRD_STATUS_ACTIVE:
        raise MrdMutationForbiddenError(
            f"Confirm requires ACTIVE MRD; got {mrd_status!r}"
        )


def validate_closed_mrd_immutable(mrd_status: str) -> None:
    if mrd_status == MRD_STATUS_CLOSED:
        raise MrdMutationForbiddenError("CLOSED MRD versions are immutable")


def validate_difference_origin_required(origin_code: str | None) -> None:
    if not origin_code or not origin_code.strip():
        raise DifferenceOriginError("difference_origin_code is required")


def validate_origin_context(origin_context: object | None) -> None:
    if origin_context is None:
        raise DifferenceOriginError("origin_context is required")
    if not isinstance(origin_context, dict):
        raise DifferenceOriginError("origin_context must be a JSON object")


def validate_active_origin(origin_code: str, *, is_active: bool) -> None:
    if not is_active:
        raise DifferenceOriginError(f"difference_origin_code {origin_code!r} is inactive")
