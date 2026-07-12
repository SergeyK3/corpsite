"""Activation service — activation decision from OfficialDraftSnapshot (UDE-011)."""
from __future__ import annotations

from app.document_engine.contracts.validation import ValidationIssue, ValidationResult, ValidationSeverity
from app.document_engine.editorial.editorial_models import OfficialDraftSnapshot
from app.document_engine.lifecycle.lifecycle_models import ActivationDecision, LifecycleGate, LifecycleViolation
from app.document_engine.lifecycle.promotion_policy import PromotionPolicy
from app.document_engine.lifecycle.readiness_policy import ReadinessPolicy


class ActivationService:
    """Builds ActivationDecision — no DocumentId, no persistence, no writes."""

    @staticmethod
    def evaluate(draft: OfficialDraftSnapshot) -> ActivationDecision:
        violations, validation = ReadinessPolicy.evaluate_official_draft(draft)
        promotion = PromotionPolicy.evaluate(draft)

        all_violations = list(violations)
        if not promotion.is_ready:
            for blocker in promotion.blockers:
                if blocker not in all_violations:
                    all_violations.append(blocker)

        activation_blockers = [
            v for v in all_violations if v.gate in (LifecycleGate.ACTIVATION, LifecycleGate.PROMOTION, None)
        ]
        issues = tuple(
            ValidationIssue(
                code=v.code,
                severity=ValidationSeverity.ERROR,
                message=v.message,
                field_path=v.field_path,
            )
            for v in activation_blockers
        )
        result = ValidationResult.from_issues(issues)
        is_allowed = len(activation_blockers) == 0

        return ActivationDecision(
            is_allowed=is_allowed,
            blockers=tuple(activation_blockers),
            validation=result,
        )
