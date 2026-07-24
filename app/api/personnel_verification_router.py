"""Personnel verification REST API — employment revisions (WP-VER-005A)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from app.api.personnel_verification_employment_api import (
    confirm_employment_revision,
    get_employment_revision_state,
    get_employment_task_review,
    list_pending_employment_tasks,
    reject_employment_revision,
)
from app.api.personnel_verification_errors import map_personnel_verification_error
from app.api.personnel_verification_schemas import (
    DerivedVerificationStateResponse,
    EmploymentPendingTaskListResponse,
    EmploymentRevisionDecisionResponse,
    EmploymentTaskReviewResponse,
    EmploymentVerificationDecisionRequest,
)
from app.auth import get_current_user
from app.directory.common import as_http500
from app.directory.rbac import require_hr_import_admin_or_403
from app.personnel_verification.application.employment_verification_commands import (
    EmploymentVerificationCommandService,
)
from app.services.ppr_query_access_service import assert_ppr_read_allowed_for_person

router = APIRouter(prefix="/api/personnel-verification", tags=["personnel-verification"])


def _run(handler):
    try:
        return handler()
    except HTTPException:
        raise
    except Exception as exc:
        mapped = map_personnel_verification_error(exc)
        if mapped is not None:
            raise mapped
        raise as_http500(exc)


def _assert_task_person_visible(user: dict[str, Any], task_id: int) -> None:
    task = EmploymentVerificationCommandService().get_task(task_id=task_id)
    assert_ppr_read_allowed_for_person(user, task.person_id)


def _assert_revision_person_visible(user: dict[str, Any], revision_employment_id: int) -> None:
    person_id = EmploymentVerificationCommandService().get_revision_person_id(
        revision_employment_id=revision_employment_id
    )
    assert_ppr_read_allowed_for_person(user, person_id)


@router.get(
    "/employment/pending-tasks",
    response_model=EmploymentPendingTaskListResponse,
)
def list_employment_pending_tasks(
    person_id: int | None = Query(None, ge=1),
    limit: int = Query(100, ge=1, le=500),
    user: dict[str, Any] = Depends(get_current_user),
) -> EmploymentPendingTaskListResponse:
    """List pending employment_episode verification tasks."""
    require_hr_import_admin_or_403(user)
    if person_id is not None:
        assert_ppr_read_allowed_for_person(user, person_id)
    return _run(
        lambda: list_pending_employment_tasks(person_id=person_id, limit=limit)
    )


@router.get(
    "/employment/tasks/{task_id}/review",
    response_model=EmploymentTaskReviewResponse,
)
def get_employment_pending_task_review(
    task_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> EmploymentTaskReviewResponse:
    """HR-facing prior/revision comparison payload for a verification task."""
    require_hr_import_admin_or_403(user)

    def _handler():
        _assert_task_person_visible(user, task_id)
        return get_employment_task_review(task_id=task_id)

    return _run(_handler)


@router.get(
    "/employment/revisions/{revision_id}/state",
    response_model=DerivedVerificationStateResponse,
)
def get_employment_revision_verification_state(
    revision_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> DerivedVerificationStateResponse:
    """Derived verification state for an employment revision version."""
    require_hr_import_admin_or_403(user)

    def _handler():
        _assert_revision_person_visible(user, revision_id)
        return get_employment_revision_state(revision_employment_id=revision_id)

    return _run(_handler)


@router.post(
    "/employment/tasks/{task_id}/confirm",
    response_model=EmploymentRevisionDecisionResponse,
)
def confirm_employment_pending_task(
    body: EmploymentVerificationDecisionRequest,
    task_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> EmploymentRevisionDecisionResponse:
    """Confirm a pending employment revision (supersede prior atomically)."""
    require_hr_import_admin_or_403(user)

    def _handler():
        _assert_task_person_visible(user, task_id)
        return confirm_employment_revision(user, task_id=task_id, body=body)

    return _run(_handler)


@router.post(
    "/employment/tasks/{task_id}/reject",
    response_model=EmploymentRevisionDecisionResponse,
)
def reject_employment_pending_task(
    body: EmploymentVerificationDecisionRequest,
    task_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> EmploymentRevisionDecisionResponse:
    """Reject a pending employment revision (void revision, keep prior)."""
    require_hr_import_admin_or_403(user)

    def _handler():
        _assert_task_person_visible(user, task_id)
        return reject_employment_revision(user, task_id=task_id, body=body)

    return _run(_handler)
