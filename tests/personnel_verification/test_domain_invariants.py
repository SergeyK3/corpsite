"""Unit tests for WP-VER-002 domain invariants (no DB)."""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.personnel_verification.domain.control_catalog import supports_task_creation
from app.personnel_verification.domain.errors import (
    AttestationImmutableError,
    AttestationValidationError,
    CanonicalRecordUnavailableError,
    ControlPointNotAllowedError,
    PolicyValidationError,
    TaskValidationError,
)
from app.personnel_verification.domain.invariants import (
    require_allowed_control_point,
    require_task_creation_supported,
    resolve_derived_verification_state,
    validate_attestation_matches_task,
    validate_decision_basis,
    validate_employment_episode_object_identity,
    validate_policy_dates,
    validate_publish_fields,
    validate_task_not_terminal,
)
from app.personnel_verification.domain.models import (
    VerificationAttestationSnapshot,
    VerificationPolicySnapshot,
    VerificationTaskSnapshot,
)
from app.personnel_verification.domain.types import (
    ATTESTATION_DECISION_REJECTED,
    ATTESTATION_DECISION_VERIFIED,
    CONTROL_POINT_EMPLOYMENT_EPISODE,
    CONTROL_POINT_MEDICAL_CATEGORY,
    OBJECT_TYPE_PERSON_EXTERNAL_EMPLOYMENT,
    POLICY_STATUS_ACTIVE,
    POLICY_STATUS_DRAFT,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_PENDING,
    VERIFICATION_STATE_NOT_REQUIRED,
    VERIFICATION_STATE_PENDING,
    VERIFICATION_STATE_VERIFIED,
)
from app.personnel_verification.infrastructure.repository import PersonnelVerificationRepository


def _policy(*, status: str = POLICY_STATUS_ACTIVE) -> VerificationPolicySnapshot:
    now = datetime.now(timezone.utc)
    return VerificationPolicySnapshot(
        policy_id=1,
        control_point=CONTROL_POINT_EMPLOYMENT_EPISODE,
        policy_version=1,
        status=status,
        effective_from=date(2026, 1, 1),
        effective_to=None,
        decision_basis="HR order 1",
        created_by_user_id=10,
        published_by_user_id=10 if status != POLICY_STATUS_DRAFT else None,
        created_at=now,
        published_at=now if status != POLICY_STATUS_DRAFT else None,
        updated_at=now,
    )


def _task(*, status: str = TASK_STATUS_PENDING) -> VerificationTaskSnapshot:
    now = datetime.now(timezone.utc)
    return VerificationTaskSnapshot(
        task_id=5,
        person_id=100,
        control_point=CONTROL_POINT_EMPLOYMENT_EPISODE,
        object_type=OBJECT_TYPE_PERSON_EXTERNAL_EMPLOYMENT,
        object_id=200,
        object_version_id=201,
        policy_id=1,
        policy_version=1,
        status=status,
        created_at=now,
        updated_at=now,
        closed_at=None if status == TASK_STATUS_PENDING else now,
    )


def test_catalog_allows_both_control_points_but_blocks_medical_tasks() -> None:
    require_allowed_control_point(CONTROL_POINT_EMPLOYMENT_EPISODE)
    require_allowed_control_point(CONTROL_POINT_MEDICAL_CATEGORY)
    assert supports_task_creation(CONTROL_POINT_EMPLOYMENT_EPISODE) is True
    assert supports_task_creation(CONTROL_POINT_MEDICAL_CATEGORY) is False

    with pytest.raises(ControlPointNotAllowedError):
        require_allowed_control_point("external_employment")
    with pytest.raises(CanonicalRecordUnavailableError):
        require_task_creation_supported(CONTROL_POINT_MEDICAL_CATEGORY)


def test_employment_episode_requires_object_id_equals_object_version_id() -> None:
    validate_employment_episode_object_identity(object_id=10, object_version_id=10)
    with pytest.raises(TaskValidationError, match="object_id = object_version_id"):
        validate_employment_episode_object_identity(object_id=10, object_version_id=11)


def test_policy_date_and_publish_guards() -> None:
    validate_policy_dates(date(2026, 1, 1), date(2026, 12, 31))
    with pytest.raises(PolicyValidationError):
        validate_policy_dates(date(2026, 5, 1), date(2026, 1, 1))
    with pytest.raises(PolicyValidationError):
        validate_decision_basis("   ")

    validate_publish_fields(
        status=POLICY_STATUS_DRAFT,
        published_by_user_id=None,
        published_at_present=False,
    )
    with pytest.raises(PolicyValidationError):
        validate_publish_fields(
            status=POLICY_STATUS_ACTIVE,
            published_by_user_id=None,
            published_at_present=True,
        )


def test_attestation_must_match_pending_task_and_policy() -> None:
    task = _task()
    policy = _policy()
    validate_attestation_matches_task(
        task=task,
        policy=policy,
        person_id=task.person_id,
        control_point=task.control_point,
        object_type=task.object_type,
        object_id=task.object_id,
        object_version_id=task.object_version_id,
        policy_id=task.policy_id,
        policy_version=task.policy_version,
    )
    with pytest.raises(AttestationValidationError):
        validate_attestation_matches_task(
            task=task,
            policy=policy,
            person_id=task.person_id,
            control_point=task.control_point,
            object_type=task.object_type,
            object_id=task.object_id,
            object_version_id=999,
            policy_id=task.policy_id,
            policy_version=task.policy_version,
        )
    with pytest.raises(TaskValidationError):
        validate_task_not_terminal(TASK_STATUS_COMPLETED)


def test_derived_state_is_not_verification_status_column() -> None:
    assert (
        resolve_derived_verification_state(
            control_point=CONTROL_POINT_EMPLOYMENT_EPISODE,
            active_policy=None,
            pending_task=None,
            latest_attestation=None,
        ).state
        == VERIFICATION_STATE_NOT_REQUIRED
    )
    assert (
        resolve_derived_verification_state(
            control_point=CONTROL_POINT_EMPLOYMENT_EPISODE,
            active_policy=_policy(),
            pending_task=_task(),
            latest_attestation=None,
        ).state
        == VERIFICATION_STATE_PENDING
    )
    now = datetime.now(timezone.utc)
    attestation = VerificationAttestationSnapshot(
        attestation_id=7,
        task_id=5,
        person_id=100,
        control_point=CONTROL_POINT_EMPLOYMENT_EPISODE,
        object_type=OBJECT_TYPE_PERSON_EXTERNAL_EMPLOYMENT,
        object_id=200,
        object_version_id=201,
        policy_id=1,
        policy_version=1,
        decision=ATTESTATION_DECISION_VERIFIED,
        verifier_user_id=10,
        verifier_employee_id=None,
        decided_at=now,
        comment=None,
        evidence_ref=None,
        created_at=now,
    )
    assert (
        resolve_derived_verification_state(
            control_point=CONTROL_POINT_EMPLOYMENT_EPISODE,
            active_policy=_policy(),
            pending_task=None,
            latest_attestation=attestation,
        ).state
        == VERIFICATION_STATE_VERIFIED
    )
    rejected = VerificationAttestationSnapshot(
        attestation_id=8,
        task_id=5,
        person_id=100,
        control_point=CONTROL_POINT_EMPLOYMENT_EPISODE,
        object_type=OBJECT_TYPE_PERSON_EXTERNAL_EMPLOYMENT,
        object_id=200,
        object_version_id=201,
        policy_id=1,
        policy_version=1,
        decision=ATTESTATION_DECISION_REJECTED,
        verifier_user_id=10,
        verifier_employee_id=None,
        decided_at=now,
        comment=None,
        evidence_ref=None,
        created_at=now,
    )
    assert (
        resolve_derived_verification_state(
            control_point=CONTROL_POINT_EMPLOYMENT_EPISODE,
            active_policy=_policy(),
            pending_task=None,
            latest_attestation=rejected,
        ).state
        == "rejected"
    )


def test_repository_api_forbids_attestation_mutation_methods() -> None:
    repo = PersonnelVerificationRepository(conn=None)  # type: ignore[arg-type]
    with pytest.raises(AttestationImmutableError):
        repo.update_attestation(attestation_id=1)
    with pytest.raises(AttestationImmutableError):
        repo.delete_attestation(attestation_id=1)
