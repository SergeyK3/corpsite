"""Invariant guards for personnel verification foundation (ADR-060 / WP-VER-002)."""
from __future__ import annotations

from datetime import date

from app.personnel_verification.domain.control_catalog import (
    get_control_point_definition,
    is_allowed_control_point,
    supports_task_creation,
)
from app.personnel_verification.domain.errors import (
    AttestationValidationError,
    CanonicalRecordUnavailableError,
    ControlPointNotAllowedError,
    PolicyValidationError,
    TaskValidationError,
)
from app.personnel_verification.domain.models import (
    DerivedVerificationState,
    VerificationAttestationSnapshot,
    VerificationPolicySnapshot,
    VerificationTaskSnapshot,
)
from app.personnel_verification.domain.types import (
    ATTESTATION_DECISION_REJECTED,
    ATTESTATION_DECISION_VERIFIED,
    ATTESTATION_DECISIONS,
    POLICY_STATUS_ACTIVE,
    POLICY_STATUS_DRAFT,
    POLICY_STATUS_INACTIVE,
    POLICY_STATUSES,
    TASK_STATUS_CANCELLED,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_PENDING,
    TASK_STATUS_REJECTED,
    TASK_STATUSES,
    TERMINAL_TASK_STATUSES,
    VERIFICATION_STATE_NOT_REQUIRED,
    VERIFICATION_STATE_PENDING,
    VERIFICATION_STATE_REJECTED,
    VERIFICATION_STATE_VERIFIED,
)


def require_allowed_control_point(control_point: str) -> None:
    if not is_allowed_control_point(control_point):
        raise ControlPointNotAllowedError(
            f"Control point {control_point!r} is not in the allowed catalog"
        )


def require_task_creation_supported(control_point: str) -> None:
    require_allowed_control_point(control_point)
    if not supports_task_creation(control_point):
        definition = get_control_point_definition(control_point)
        raise CanonicalRecordUnavailableError(
            f"Control point {control_point!r} has no typed canonical record yet "
            f"({definition.description}); task creation is forbidden until WP-VER-004"
        )


def validate_policy_dates(effective_from: date, effective_to: date | None) -> None:
    if effective_to is not None and effective_to < effective_from:
        raise PolicyValidationError(
            "effective_to must be greater than or equal to effective_from"
        )


def validate_decision_basis(decision_basis: str) -> None:
    if not decision_basis or not decision_basis.strip():
        raise PolicyValidationError("decision_basis is required")


def validate_policy_status(status: str) -> None:
    if status not in POLICY_STATUSES:
        raise PolicyValidationError(f"Unsupported policy status: {status!r}")


def validate_publish_fields(
    *,
    status: str,
    published_by_user_id: int | None,
    published_at_present: bool,
) -> None:
    validate_policy_status(status)
    if status == POLICY_STATUS_DRAFT:
        if published_by_user_id is not None or published_at_present:
            raise PolicyValidationError("draft policy must not have publish fields set")
        return
    if status in {POLICY_STATUS_ACTIVE, POLICY_STATUS_INACTIVE}:
        if published_by_user_id is None or not published_at_present:
            raise PolicyValidationError(
                f"{status} policy requires published_by_user_id and published_at"
            )


def validate_employment_episode_object_identity(
    *,
    object_id: int,
    object_version_id: int,
    supersedes_employment_id: int | None = None,
) -> None:
    """Employment task identity for root rows and WP-VER-003 revisions.

    - Root (no supersedes): object_id = object_version_id = employment_id
    - Revision: object_version_id = new employment_id,
      object_id = supersedes_employment_id
    """
    if supersedes_employment_id is None:
        if object_id != object_version_id:
            raise TaskValidationError(
                "employment_episode root requires object_id = object_version_id "
                f"(got object_id={object_id}, object_version_id={object_version_id})"
            )
        return
    if object_id != supersedes_employment_id:
        raise TaskValidationError(
            "employment_episode revision requires object_id = supersedes_employment_id "
            f"(got object_id={object_id}, supersedes_employment_id={supersedes_employment_id})"
        )
    if object_version_id == object_id:
        raise TaskValidationError(
            "employment_episode revision requires object_version_id distinct from object_id"
        )


def validate_task_status(status: str) -> None:
    if status not in TASK_STATUSES:
        raise TaskValidationError(f"Unsupported task status: {status!r}")


def validate_task_not_terminal(status: str) -> None:
    validate_task_status(status)
    if status in TERMINAL_TASK_STATUSES:
        raise TaskValidationError(
            f"Terminal task status {status!r} cannot accept a new decision"
        )


def validate_attestation_decision(decision: str) -> None:
    if decision not in ATTESTATION_DECISIONS:
        raise AttestationValidationError(f"Unsupported attestation decision: {decision!r}")


def expected_task_status_for_decision(decision: str) -> str:
    validate_attestation_decision(decision)
    if decision == ATTESTATION_DECISION_VERIFIED:
        return TASK_STATUS_COMPLETED
    if decision == ATTESTATION_DECISION_REJECTED:
        return TASK_STATUS_REJECTED
    raise AttestationValidationError(f"Unsupported attestation decision: {decision!r}")


def validate_attestation_matches_task(
    *,
    task: VerificationTaskSnapshot,
    policy: VerificationPolicySnapshot,
    person_id: int,
    control_point: str,
    object_type: str,
    object_id: int,
    object_version_id: int,
    policy_id: int,
    policy_version: int,
) -> None:
    validate_task_not_terminal(task.status)
    if task.status != TASK_STATUS_PENDING:
        raise TaskValidationError(
            f"Attestation requires pending task; got {task.status!r}"
        )
    if task.person_id != person_id:
        raise AttestationValidationError("attestation.person_id must match task.person_id")
    if task.control_point != control_point or policy.control_point != control_point:
        raise AttestationValidationError(
            "attestation.control_point must match task and policy control_point"
        )
    if (
        task.object_type != object_type
        or task.object_id != object_id
        or task.object_version_id != object_version_id
    ):
        raise AttestationValidationError(
            "attestation object identity must match the pending task revision"
        )
    if task.policy_id != policy_id or policy.policy_id != policy_id:
        raise AttestationValidationError("attestation.policy_id must match task/policy")
    if task.policy_version != policy_version or policy.policy_version != policy_version:
        raise AttestationValidationError(
            "attestation.policy_version must match task/policy version"
        )


def validate_policy_active_for_tasks(policy: VerificationPolicySnapshot) -> None:
    if policy.status != POLICY_STATUS_ACTIVE:
        raise PolicyValidationError(
            f"Tasks require an active policy; got status {policy.status!r}"
        )


def resolve_derived_verification_state(
    *,
    control_point: str,
    active_policy: VerificationPolicySnapshot | None,
    pending_task: VerificationTaskSnapshot | None,
    latest_attestation: VerificationAttestationSnapshot | None,
) -> DerivedVerificationState:
    """Derive verification state from policy + attestation (+ pending task).

    This intentionally does not read or write PPR ``verification_status``.
    """
    require_allowed_control_point(control_point)
    if active_policy is None:
        return DerivedVerificationState(
            state=VERIFICATION_STATE_NOT_REQUIRED,
            control_point=control_point,
            object_type=None,
            object_id=None,
            object_version_id=None,
            policy_id=None,
            policy_version=None,
            attestation_id=None,
            decided_at=None,
        )

    if pending_task is not None and pending_task.status == TASK_STATUS_PENDING:
        return DerivedVerificationState(
            state=VERIFICATION_STATE_PENDING,
            control_point=control_point,
            object_type=pending_task.object_type,
            object_id=pending_task.object_id,
            object_version_id=pending_task.object_version_id,
            policy_id=pending_task.policy_id,
            policy_version=pending_task.policy_version,
            attestation_id=None,
            decided_at=None,
        )

    if latest_attestation is not None:
        if latest_attestation.decision == ATTESTATION_DECISION_VERIFIED:
            state = VERIFICATION_STATE_VERIFIED
        elif latest_attestation.decision == ATTESTATION_DECISION_REJECTED:
            state = VERIFICATION_STATE_REJECTED
        else:
            state = VERIFICATION_STATE_PENDING
        return DerivedVerificationState(
            state=state,
            control_point=control_point,
            object_type=latest_attestation.object_type,
            object_id=latest_attestation.object_id,
            object_version_id=latest_attestation.object_version_id,
            policy_id=latest_attestation.policy_id,
            policy_version=latest_attestation.policy_version,
            attestation_id=latest_attestation.attestation_id,
            decided_at=latest_attestation.decided_at,
        )

    return DerivedVerificationState(
        state=VERIFICATION_STATE_PENDING,
        control_point=control_point,
        object_type=None,
        object_id=None,
        object_version_id=None,
        policy_id=active_policy.policy_id,
        policy_version=active_policy.policy_version,
        attestation_id=None,
        decided_at=None,
    )


# Re-export cancel constant for callers that close without attestation.
CANCELLED_TASK_STATUS = TASK_STATUS_CANCELLED
