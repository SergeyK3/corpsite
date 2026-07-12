"""Lifecycle evaluation service (UDE-011)."""
from __future__ import annotations

from app.document_engine.contracts.validation import ValidationIssue, ValidationResult, ValidationSeverity
from app.document_engine.editorial.editorial_models import EditorialDocument, OfficialDraftSnapshot
from app.document_engine.lifecycle.lifecycle_models import (
    LifecycleDecision,
    LifecycleEvaluation,
    LifecycleGate,
    LifecycleViolation,
    PromotionReadiness,
    RegistrationReadiness,
    SignedSnapshotDescriptor,
)
from app.document_engine.lifecycle.lifecycle_rules import LifecycleRules
from app.document_engine.lifecycle.promotion_policy import PromotionPolicy
from app.document_engine.lifecycle.readiness_policy import ReadinessPolicy
from app.document_engine.lifecycle.registration_policy import RegistrationPolicy
from app.document_engine.read_models.lifecycle import LifecycleReadModel
from app.document_engine.value_objects.lifecycle import ArchiveState, DocumentLifecycleState


class LifecycleEvaluationService:
    """Evaluates lifecycle from editorial + lifecycle read models — no state changes."""

    @staticmethod
    def _gate_readiness(
        gate: LifecycleGate,
        *,
        editorial: EditorialDocument,
        lifecycle: LifecycleReadModel,
        draft: OfficialDraftSnapshot | None,
    ) -> tuple[bool, str | None]:
        if gate == LifecycleGate.MARK_READY:
            violations, _ = ReadinessPolicy.evaluate_mark_ready(editorial)
            if violations:
                return False, violations[0].message
            return True, None

        if gate == LifecycleGate.SIGN:
            if lifecycle.lifecycle_state != DocumentLifecycleState.READY_FOR_SIGNATURE:
                return False, "Sign requires READY_FOR_SIGNATURE"
            violations, _ = ReadinessPolicy.evaluate_mark_ready(editorial)
            if violations:
                return False, violations[0].message
            return True, None

        if gate == LifecycleGate.REGISTER:
            readiness = RegistrationPolicy.evaluate(lifecycle)
            if not readiness.is_ready:
                return False, readiness.blockers[0].message if readiness.blockers else "Not ready"
            return True, None

        if gate in (LifecycleGate.CANCEL, LifecycleGate.ANNUL):
            if lifecycle.lifecycle_state == DocumentLifecycleState.VOIDED:
                return False, "Already voided"
            if gate == LifecycleGate.CANCEL and lifecycle.lifecycle_state not in (
                DocumentLifecycleState.DRAFT,
                DocumentLifecycleState.READY_FOR_SIGNATURE,
            ):
                return False, "Cancel only from DRAFT or READY_FOR_SIGNATURE"
            if gate == LifecycleGate.ANNUL and lifecycle.lifecycle_state not in (
                DocumentLifecycleState.SIGNED,
                DocumentLifecycleState.REGISTERED,
            ):
                return False, "Annul only from SIGNED or REGISTERED"
            return True, None

        if gate == LifecycleGate.ARCHIVE:
            if lifecycle.archive_state == ArchiveState.ARCHIVED:
                return False, "Already archived"
            return True, None

        if gate == LifecycleGate.RETURN_TO_DRAFT:
            if lifecycle.lifecycle_state != DocumentLifecycleState.READY_FOR_SIGNATURE:
                return False, "Return to draft only from READY_FOR_SIGNATURE"
            return True, None

        if gate == LifecycleGate.PROMOTION and draft is not None:
            readiness = PromotionPolicy.evaluate(draft)
            if not readiness.is_ready:
                return False, readiness.blockers[0].message if readiness.blockers else "Not ready"
            return True, None

        return True, None

    @staticmethod
    def evaluate_decision(
        editorial: EditorialDocument,
        lifecycle: LifecycleReadModel,
        *,
        draft: OfficialDraftSnapshot | None = None,
    ) -> LifecycleDecision:
        current = lifecycle.lifecycle_state
        transitions = []
        blockers: list[LifecycleViolation] = []

        for target, gate in LifecycleRules.possible_transitions(current):
            gate_ready, reason = LifecycleEvaluationService._gate_readiness(
                gate,
                editorial=editorial,
                lifecycle=lifecycle,
                draft=draft,
            )
            transition = LifecycleRules.evaluate_transition(
                current,
                target,
                gate_ready=gate_ready,
                reason=reason,
            )
            transitions.append(transition)
            if not gate_ready and reason:
                blockers.append(
                    LifecycleViolation(
                        code=f"L_GATE_{gate.value}",
                        message=reason,
                        gate=gate,
                    )
                )

        issues = tuple(
            ValidationIssue(
                code=b.code,
                severity=ValidationSeverity.ERROR,
                message=b.message,
                field_path=b.field_path,
            )
            for b in blockers
        )

        return LifecycleDecision(
            current_state=current,
            archive_state=lifecycle.archive_state,
            void_kind=lifecycle.void_kind,
            allowed_transitions=tuple(transitions),
            blockers=tuple(blockers),
            validation=ValidationResult.from_issues(issues),
        )

    @staticmethod
    def signed_snapshot_descriptor(lifecycle: LifecycleReadModel) -> SignedSnapshotDescriptor:
        blockers: list[LifecycleViolation] = []
        if lifecycle.lifecycle_state not in (
            DocumentLifecycleState.SIGNED,
            DocumentLifecycleState.REGISTERED,
        ):
            blockers.append(
                LifecycleViolation(
                    code="L_SIGNED_SNAPSHOT_STATE",
                    message="Signed snapshot exists only in SIGNED or REGISTERED",
                    gate=LifecycleGate.SIGN,
                )
            )
        return SignedSnapshotDescriptor(
            is_eligible=len(blockers) == 0,
            lifecycle_state=lifecycle.lifecycle_state,
            blockers=tuple(blockers),
        )

    @staticmethod
    def evaluate(
        editorial: EditorialDocument,
        lifecycle: LifecycleReadModel,
        *,
        draft: OfficialDraftSnapshot | None = None,
    ) -> LifecycleEvaluation:
        decision = LifecycleEvaluationService.evaluate_decision(
            editorial,
            lifecycle,
            draft=draft,
        )
        signed = LifecycleEvaluationService.signed_snapshot_descriptor(lifecycle)
        promotion = PromotionPolicy.evaluate(draft) if draft is not None else None
        registration = RegistrationPolicy.evaluate(lifecycle)

        all_issues = list(decision.validation.issues)
        if promotion is not None:
            all_issues.extend(promotion.validation.issues)
        all_issues.extend(registration.validation.issues)

        return LifecycleEvaluation(
            lifecycle=lifecycle,
            decision=decision,
            signed_snapshot=signed,
            promotion_readiness=promotion,
            registration_readiness=registration,
            validation=ValidationResult.from_issues(all_issues),
        )
