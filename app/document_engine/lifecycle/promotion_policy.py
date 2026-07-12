"""Promotion policy — OfficialDraftSnapshot promotion eligibility (UDE-011)."""
from __future__ import annotations

from app.document_engine.contracts.validation import ValidationIssue, ValidationResult, ValidationSeverity
from app.document_engine.editorial.editorial_models import OfficialDraftSnapshot
from app.document_engine.lifecycle.lifecycle_models import LifecycleGate, LifecycleViolation, PromotionReadiness
from app.document_engine.lifecycle.readiness_policy import ReadinessPolicy
from app.document_engine.value_objects.lifecycle import DocumentLifecycleState


class PromotionPolicy:
    """Determines whether OfficialDraftSnapshot may be promoted — no Document created."""

    @staticmethod
    def evaluate(draft: OfficialDraftSnapshot) -> PromotionReadiness:
        violations, validation = ReadinessPolicy.evaluate_official_draft(draft)

        if draft.lifecycle_state != DocumentLifecycleState.DRAFT:
            violations = list(violations) + [
                LifecycleViolation(
                    code="L_PROMOTION_STATE",
                    message=(
                        f"Promotion requires DRAFT context; "
                        f"current state is {draft.lifecycle_state.value}"
                    ),
                    gate=LifecycleGate.PROMOTION,
                    field_path="lifecycle_state",
                )
            ]
            issues = tuple(
                ValidationIssue(
                    code=v.code,
                    severity=ValidationSeverity.ERROR,
                    message=v.message,
                    field_path=v.field_path,
                )
                for v in violations
            )
            validation = ValidationResult.from_issues(issues)

        is_ready = len(violations) == 0
        return PromotionReadiness(
            is_ready=is_ready,
            blockers=tuple(violations),
            validation=validation,
        )
