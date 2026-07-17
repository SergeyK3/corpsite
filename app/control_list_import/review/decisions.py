"""Review decision helpers — decision updates without apply execution (WP-CL-011)."""
from __future__ import annotations

from dataclasses import replace

from app.control_list_import.domain.review_models import (
    ControlListReviewItem,
    ReviewDecision,
)
from app.control_list_import.review.apply_planner import ApplyPlanner


class ReviewDecisionError(ValueError):
    """Invalid review decision for the current item state."""


def apply_review_decision(
    item: ControlListReviewItem,
    decision: ReviewDecision,
    *,
    planner: ApplyPlanner | None = None,
) -> ControlListReviewItem:
    """Update reviewer decision and rebuild declarative apply plan — no canonical writes."""
    if decision == ReviewDecision.APPROVED and not item.is_approval_allowed:
        raise ReviewDecisionError(
            "Cannot approve a blocked review item; resolve blocking issues first"
        )

    apply_planner = planner or ApplyPlanner()
    updated = replace(item, decision=decision)
    return replace(updated, apply_plan=apply_planner.plan_item(updated))
