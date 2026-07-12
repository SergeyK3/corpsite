"""Registration policy — registration eligibility (UDE-011)."""
from __future__ import annotations

from app.document_engine.lifecycle.lifecycle_models import LifecycleGate, LifecycleViolation, RegistrationReadiness
from app.document_engine.read_models.lifecycle import LifecycleReadModel
from app.document_engine.value_objects.lifecycle import ArchiveState, DocumentLifecycleState


class RegistrationPolicy:
    """Computes registration eligibility — no registration number assigned."""

    @staticmethod
    def evaluate(lifecycle: LifecycleReadModel) -> RegistrationReadiness:
        violations: list[LifecycleViolation] = []

        if lifecycle.lifecycle_state != DocumentLifecycleState.SIGNED:
            violations.append(
                LifecycleViolation(
                    code="L_REGISTER_STATE",
                    message=(
                        f"Registration requires SIGNED state; "
                        f"current is {lifecycle.lifecycle_state.value}"
                    ),
                    gate=LifecycleGate.REGISTER,
                    field_path="lifecycle_state",
                )
            )

        if lifecycle.archive_state == ArchiveState.ARCHIVED:
            violations.append(
                LifecycleViolation(
                    code="L_REGISTER_ARCHIVED",
                    message="Archived documents cannot be registered",
                    gate=LifecycleGate.REGISTER,
                    field_path="archive_state",
                )
            )

        if lifecycle.lifecycle_state == DocumentLifecycleState.VOIDED:
            violations.append(
                LifecycleViolation(
                    code="L_REGISTER_VOIDED",
                    message="Voided documents cannot be registered",
                    gate=LifecycleGate.REGISTER,
                    field_path="lifecycle_state",
                )
            )

        from app.document_engine.contracts.validation import ValidationIssue, ValidationResult, ValidationSeverity

        issues = tuple(
            ValidationIssue(
                code=v.code,
                severity=ValidationSeverity.ERROR,
                message=v.message,
                field_path=v.field_path,
            )
            for v in violations
        )
        return RegistrationReadiness(
            is_ready=len(violations) == 0,
            blockers=tuple(violations),
            validation=ValidationResult.from_issues(issues),
        )
