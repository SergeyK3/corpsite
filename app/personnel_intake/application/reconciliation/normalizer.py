"""Common DecisionNormalizer (WP-002 §5.2 / WP-004 §4.3)."""
from __future__ import annotations

from dataclasses import dataclass

from app.personnel_intake.application.reconciliation.dto import MatchOutcome
from app.personnel_intake.domain.reconciliation.actions import (
    MATCH_CONFIDENCE_HIGH,
    MATCH_KIND_AMBIGUOUS,
    MATCH_KIND_EXACT_ONE,
    MATCH_KIND_NONE,
    MATCH_KIND_STALE_TARGET,
    REASON_MATCH_AMBIGUOUS,
    REASON_MATCH_CONFIDENCE_LOW,
    REASON_MATCH_EXACT_KEEP,
    REASON_MATCH_NONE_CONFIDENT,
    REASON_MATCH_STALE_TARGET,
    RECONCILE_ACTION_ADD,
    RECONCILE_ACTION_KEEP_EXISTING,
    RECONCILE_ACTION_MANUAL_REVIEW,
)
from app.personnel_intake.domain.reconciliation.errors import ReconciliationValidationError


@dataclass(frozen=True, slots=True)
class NormalizeMatchResult:
    """Normalizer result; exact non-equal path needs plugin.choose_exact_action."""

    action: str | None
    reason_code: str | None
    needs_choose_exact_action: bool = False


def normalize_match_outcome(
    match: MatchOutcome,
    *,
    section_code: str,
) -> NormalizeMatchResult:
    """Map MatchOutcome → action + reason (never ApplyStatus / blocked)."""
    del section_code  # reserved for future section policy hooks
    confidence = match.match_confidence
    kind = match.match_kind

    if confidence != MATCH_CONFIDENCE_HIGH:
        return NormalizeMatchResult(
            action=RECONCILE_ACTION_MANUAL_REVIEW,
            reason_code=REASON_MATCH_CONFIDENCE_LOW,
        )
    if kind == MATCH_KIND_AMBIGUOUS:
        return NormalizeMatchResult(
            action=RECONCILE_ACTION_MANUAL_REVIEW,
            reason_code=REASON_MATCH_AMBIGUOUS,
        )
    if kind == MATCH_KIND_STALE_TARGET:
        return NormalizeMatchResult(
            action=RECONCILE_ACTION_MANUAL_REVIEW,
            reason_code=REASON_MATCH_STALE_TARGET,
        )
    if kind == MATCH_KIND_NONE:
        return NormalizeMatchResult(
            action=RECONCILE_ACTION_ADD,
            reason_code=REASON_MATCH_NONE_CONFIDENT,
        )
    if kind == MATCH_KIND_EXACT_ONE:
        if not isinstance(match.semantically_equal, bool):
            raise ReconciliationValidationError(
                "exact_one + high requires semantically_equal to be a strict bool.",
                code="INVALID_MATCH_OUTCOME",
            )
        if match.semantically_equal is True:
            return NormalizeMatchResult(
                action=RECONCILE_ACTION_KEEP_EXISTING,
                reason_code=REASON_MATCH_EXACT_KEEP,
            )
        return NormalizeMatchResult(
            action=None,
            reason_code=None,
            needs_choose_exact_action=True,
        )

    raise ReconciliationValidationError(
        f"Unsupported match_kind {kind!r} for normalization.",
        code="INVALID_MATCH_OUTCOME",
    )


__all__ = ["NormalizeMatchResult", "normalize_match_outcome"]
