"""HTTP adapter for employment revision verification (WP-VER-005A)."""
from __future__ import annotations

from typing import Any

from app.api.personnel_verification_schemas import (
    DerivedVerificationStateResponse,
    EmploymentPendingTaskListResponse,
    EmploymentRevisionDecisionResponse,
    EmploymentVerificationDecisionRequest,
    VerificationAttestationResponse,
    VerificationTaskResponse,
)
from app.personnel_verification.application.employment_revision_service import (
    RevisionDecisionResult,
)
from app.personnel_verification.application.employment_verification_commands import (
    EmploymentPendingTaskView,
    EmploymentVerificationCommandService,
)
from app.personnel_verification.domain.models import (
    DerivedVerificationState,
    VerificationAttestationSnapshot,
    VerificationTaskSnapshot,
)


def _task_response(
    task: VerificationTaskSnapshot,
    *,
    prior_updated_at=None,
) -> VerificationTaskResponse:
    return VerificationTaskResponse(
        task_id=task.task_id,
        person_id=task.person_id,
        control_point=task.control_point,
        object_type=task.object_type,
        object_id=task.object_id,
        object_version_id=task.object_version_id,
        policy_id=task.policy_id,
        policy_version=task.policy_version,
        status=task.status,
        created_at=task.created_at,
        updated_at=task.updated_at,
        closed_at=task.closed_at,
        prior_updated_at=prior_updated_at,
    )


def _attestation_response(
    attestation: VerificationAttestationSnapshot,
) -> VerificationAttestationResponse:
    return VerificationAttestationResponse(
        attestation_id=attestation.attestation_id,
        task_id=attestation.task_id,
        person_id=attestation.person_id,
        control_point=attestation.control_point,
        object_type=attestation.object_type,
        object_id=attestation.object_id,
        object_version_id=attestation.object_version_id,
        policy_id=attestation.policy_id,
        policy_version=attestation.policy_version,
        decision=attestation.decision,
        verifier_user_id=attestation.verifier_user_id,
        verifier_employee_id=attestation.verifier_employee_id,
        decided_at=attestation.decided_at,
        comment=attestation.comment,
        evidence_ref=attestation.evidence_ref,
        created_at=attestation.created_at,
    )


def _state_response(state: DerivedVerificationState) -> DerivedVerificationStateResponse:
    return DerivedVerificationStateResponse(
        state=state.state,
        control_point=state.control_point,
        object_type=state.object_type,
        object_id=state.object_id,
        object_version_id=state.object_version_id,
        policy_id=state.policy_id,
        policy_version=state.policy_version,
        attestation_id=state.attestation_id,
        decided_at=state.decided_at,
    )


def _decision_response(result: RevisionDecisionResult) -> EmploymentRevisionDecisionResponse:
    return EmploymentRevisionDecisionResponse(
        task=_task_response(result.task),
        attestation=_attestation_response(result.attestation),
        prior_employment_id=result.prior_employment_id,
        revision_employment_id=result.revision_employment_id,
        prior_lifecycle_status=result.prior_lifecycle_status,
        revision_lifecycle_status=result.revision_lifecycle_status,
    )


def _pending_item(view: EmploymentPendingTaskView) -> VerificationTaskResponse:
    return _task_response(view.task, prior_updated_at=view.prior_updated_at)


def _verifier_user_id(user_ctx: dict[str, Any]) -> int:
    uid = user_ctx.get("user_id") or user_ctx.get("id")
    if uid is None:
        raise ValueError("Authenticated user id is required.")
    return int(uid)


def list_pending_employment_tasks(
    *,
    person_id: int | None = None,
    limit: int = 100,
) -> EmploymentPendingTaskListResponse:
    service = EmploymentVerificationCommandService()
    items = service.list_pending_tasks(person_id=person_id, limit=limit)
    mapped = [_pending_item(item) for item in items]
    return EmploymentPendingTaskListResponse(items=mapped, count=len(mapped))


def get_employment_revision_state(
    *,
    revision_employment_id: int,
) -> DerivedVerificationStateResponse:
    service = EmploymentVerificationCommandService()
    state = service.get_revision_state(revision_employment_id=revision_employment_id)
    return _state_response(state)


def confirm_employment_revision(
    user_ctx: dict[str, Any],
    *,
    task_id: int,
    body: EmploymentVerificationDecisionRequest,
) -> EmploymentRevisionDecisionResponse:
    service = EmploymentVerificationCommandService()
    result = service.confirm_pending_revision(
        task_id=task_id,
        verifier_user_id=_verifier_user_id(user_ctx),
        expected_prior_updated_at=body.expected_prior_updated_at,
        comment=body.comment,
        evidence_ref=body.evidence_ref,
    )
    return _decision_response(result)


def reject_employment_revision(
    user_ctx: dict[str, Any],
    *,
    task_id: int,
    body: EmploymentVerificationDecisionRequest,
) -> EmploymentRevisionDecisionResponse:
    service = EmploymentVerificationCommandService()
    result = service.reject_pending_revision(
        task_id=task_id,
        verifier_user_id=_verifier_user_id(user_ctx),
        expected_prior_updated_at=body.expected_prior_updated_at,
        comment=body.comment,
        evidence_ref=body.evidence_ref,
    )
    return _decision_response(result)
