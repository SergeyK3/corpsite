"""Employee Onboarding directory API (WP-ONBOARDING-001, WP-ONBOARDING-002)."""
from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from app.auth import get_current_user
from app.db.engine import engine
from app.directory.common import as_http500
from app.directory.employee_onboarding_schemas import (
    BulkAssignTasksIn,
    BulkCompleteTasksIn,
    BulkDueDateIn,
    BulkOperationOut,
    ChecklistAttachmentIn,
    ChecklistItemActionIn,
    ChecklistTaskUpdateIn,
    CustomChecklistItemIn,
    EmployeeOnboardingDetailOut,
    EmployeeOnboardingListOut,
    OnboardingCancelIn,
    OnboardingCompleteIn,
    OnboardingDashboardOut,
    OnboardingTaskAuditListOut,
    OnboardingTaskListOut,
    audit_to_out,
    detail_to_out,
    list_item_to_out,
    task_item_to_out,
)
from app.directory.rbac import require_personnel_admin_or_403
from app.employee_onboarding.application.bootstrap_service import (
    load_onboarding_detail,
    load_onboarding_detail_for_employee,
)
from app.employee_onboarding.application.bulk_service import (
    bulk_assign_tasks,
    bulk_complete_tasks,
    bulk_update_due_dates,
)
from app.employee_onboarding.application.checklist_service import (
    add_custom_checklist_item,
    cancel_onboarding,
    complete_checklist_item,
    complete_onboarding,
    skip_checklist_item,
)
from app.employee_onboarding.application.dashboard_service import load_onboarding_dashboard
from app.employee_onboarding.application.query_service import list_employee_onboardings
from app.employee_onboarding.application.task_query_service import list_onboarding_tasks
from app.employee_onboarding.application.task_service import add_checklist_attachment, update_checklist_task
from app.employee_onboarding.domain.errors import (
    EmployeeOnboardingChecklistError,
    EmployeeOnboardingNotFoundError,
)
from app.employee_onboarding.infrastructure.repository import SqlAlchemyEmployeeOnboardingRepository

router = APIRouter(prefix="/employee-onboarding", tags=["employee-onboarding"])


def _require_user_id(user: dict[str, Any]) -> int:
    uid = user.get("user_id") or user.get("id")
    if uid is None:
        raise HTTPException(status_code=401, detail="Unauthorized.")
    return int(uid)


def _onboarding_http422(exc: EmployeeOnboardingChecklistError) -> HTTPException:
    return HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)})


@router.get("", response_model=EmployeeOnboardingListOut)
def list_onboardings_route(
    q: str | None = Query(None),
    status: str | None = Query(None),
    org_unit_id: int | None = Query(None, ge=1),
    responsible_hr_id: int | None = Query(None, ge=1),
    sort: str = Query("started_at_desc"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict[str, Any] = Depends(get_current_user),
) -> EmployeeOnboardingListOut:
    require_personnel_admin_or_403(user)
    try:
        with engine.connect() as conn:
            items, total = list_employee_onboardings(
                conn,
                q=q,
                status=status,
                org_unit_id=org_unit_id,
                responsible_hr_id=responsible_hr_id,
                sort=sort,
                limit=limit,
                offset=offset,
            )
        return EmployeeOnboardingListOut(
            items=[list_item_to_out(item) for item in items],
            total=total,
            limit=limit,
            offset=offset,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.get("/dashboard", response_model=OnboardingDashboardOut)
def get_onboarding_dashboard(
    user: dict[str, Any] = Depends(get_current_user),
) -> OnboardingDashboardOut:
    require_personnel_admin_or_403(user)
    try:
        with engine.connect() as conn:
            dashboard = load_onboarding_dashboard(conn)
        return OnboardingDashboardOut(
            active_programs_count=dashboard.active_programs_count,
            overdue_tasks_count=dashboard.overdue_tasks_count,
            due_soon_tasks_count=dashboard.due_soon_tasks_count,
            completion_percent=dashboard.completion_percent,
            overdue_tasks=[task_item_to_out(item) for item in dashboard.overdue_tasks],
            due_soon_tasks=[task_item_to_out(item) for item in dashboard.due_soon_tasks],
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.get("/tasks", response_model=OnboardingTaskListOut)
def list_onboarding_tasks_route(
    q: str | None = Query(None),
    status: str | None = Query(None),
    org_unit_id: int | None = Query(None, ge=1),
    assignee_user_id: int | None = Query(None, ge=1),
    due_before: date | None = Query(None),
    due_after: date | None = Query(None),
    overdue_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict[str, Any] = Depends(get_current_user),
) -> OnboardingTaskListOut:
    require_personnel_admin_or_403(user)
    try:
        with engine.connect() as conn:
            items, total = list_onboarding_tasks(
                conn,
                q=q,
                status=status,
                org_unit_id=org_unit_id,
                assignee_user_id=assignee_user_id,
                due_before=due_before,
                due_after=due_after,
                overdue_only=overdue_only,
                limit=limit,
                offset=offset,
            )
        return OnboardingTaskListOut(
            items=[task_item_to_out(item) for item in items],
            total=total,
            limit=limit,
            offset=offset,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post("/tasks/bulk/assign", response_model=BulkOperationOut)
def post_bulk_assign_tasks(
    body: BulkAssignTasksIn,
    user: dict[str, Any] = Depends(get_current_user),
) -> BulkOperationOut:
    require_personnel_admin_or_403(user)
    user_id = _require_user_id(user)
    try:
        with engine.begin() as conn:
            result = bulk_assign_tasks(
                conn,
                item_ids=body.item_ids,
                actor_user_id=user_id,
                assignee_kind=body.assignee_kind,
                assignee_user_id=body.assignee_user_id,
                assignee_employee_id=body.assignee_employee_id,
            )
        return BulkOperationOut(**result)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post("/tasks/bulk/due-date", response_model=BulkOperationOut)
def post_bulk_due_date(
    body: BulkDueDateIn,
    user: dict[str, Any] = Depends(get_current_user),
) -> BulkOperationOut:
    require_personnel_admin_or_403(user)
    user_id = _require_user_id(user)
    try:
        with engine.begin() as conn:
            result = bulk_update_due_dates(
                conn,
                item_ids=body.item_ids,
                actor_user_id=user_id,
                due_date=body.due_date,
            )
        return BulkOperationOut(**result)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post("/tasks/bulk/complete", response_model=BulkOperationOut)
def post_bulk_complete_tasks(
    body: BulkCompleteTasksIn,
    user: dict[str, Any] = Depends(get_current_user),
) -> BulkOperationOut:
    require_personnel_admin_or_403(user)
    user_id = _require_user_id(user)
    try:
        with engine.begin() as conn:
            result = bulk_complete_tasks(
                conn,
                item_ids=body.item_ids,
                actor_user_id=user_id,
                comment=body.comment,
            )
        return BulkOperationOut(**result)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.get("/by-employee/{employee_id}", response_model=EmployeeOnboardingDetailOut)
def get_onboarding_by_employee(
    employee_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> EmployeeOnboardingDetailOut:
    require_personnel_admin_or_403(user)
    try:
        with engine.connect() as conn:
            detail = load_onboarding_detail_for_employee(conn, employee_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="Onboarding not found for employee.")
        return detail_to_out(detail)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.get("/{onboarding_id}", response_model=EmployeeOnboardingDetailOut)
def get_onboarding(
    onboarding_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> EmployeeOnboardingDetailOut:
    require_personnel_admin_or_403(user)
    try:
        with engine.connect() as conn:
            detail = load_onboarding_detail(conn, onboarding_id)
        return detail_to_out(detail)
    except EmployeeOnboardingNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.patch("/{onboarding_id}/checklist/{item_id}", response_model=EmployeeOnboardingDetailOut)
def patch_checklist_task(
    body: ChecklistTaskUpdateIn,
    onboarding_id: int = Path(..., ge=1),
    item_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> EmployeeOnboardingDetailOut:
    require_personnel_admin_or_403(user)
    user_id = _require_user_id(user)
    try:
        fields_set = body.model_fields_set
        with engine.begin() as conn:
            result = update_checklist_task(
                conn,
                onboarding_id=onboarding_id,
                item_id=item_id,
                actor_user_id=user_id,
                due_date=body.due_date if "due_date" in fields_set else ...,
                assignee_kind=body.assignee_kind if "assignee_kind" in fields_set else ...,
                assignee_user_id=body.assignee_user_id if "assignee_user_id" in fields_set else ...,
                assignee_employee_id=body.assignee_employee_id if "assignee_employee_id" in fields_set else ...,
                priority=body.priority if "priority" in fields_set else ...,
                comment=body.comment if "comment" in fields_set else ...,
            )
        return detail_to_out(result.detail)
    except EmployeeOnboardingNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except EmployeeOnboardingChecklistError as exc:
        raise _onboarding_http422(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post("/{onboarding_id}/checklist/{item_id}/attachments", response_model=EmployeeOnboardingDetailOut)
def post_checklist_attachment(
    body: ChecklistAttachmentIn,
    onboarding_id: int = Path(..., ge=1),
    item_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> EmployeeOnboardingDetailOut:
    require_personnel_admin_or_403(user)
    user_id = _require_user_id(user)
    try:
        with engine.begin() as conn:
            result = add_checklist_attachment(
                conn,
                onboarding_id=onboarding_id,
                item_id=item_id,
                actor_user_id=user_id,
                file_url=body.file_url,
                file_comment=body.file_comment,
            )
        return detail_to_out(result.detail)
    except EmployeeOnboardingNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except EmployeeOnboardingChecklistError as exc:
        raise _onboarding_http422(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.get("/{onboarding_id}/checklist/{item_id}/audit", response_model=OnboardingTaskAuditListOut)
def get_checklist_task_audit(
    onboarding_id: int = Path(..., ge=1),
    item_id: int = Path(..., ge=1),
    limit: int = Query(50, ge=1, le=200),
    user: dict[str, Any] = Depends(get_current_user),
) -> OnboardingTaskAuditListOut:
    require_personnel_admin_or_403(user)
    try:
        with engine.connect() as conn:
            repo = SqlAlchemyEmployeeOnboardingRepository(conn)
            item = repo.require_checklist_item(item_id)
            if item.onboarding_id != onboarding_id:
                raise HTTPException(status_code=404, detail="Checklist item not found.")
            entries = repo.list_task_audit(item_id, limit=limit)
        return OnboardingTaskAuditListOut(items=[audit_to_out(entry) for entry in entries])
    except EmployeeOnboardingChecklistError as exc:
        if exc.code == "CHECKLIST_ITEM_NOT_FOUND":
            raise HTTPException(status_code=404, detail=str(exc))
        raise _onboarding_http422(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post("/{onboarding_id}/checklist/{item_id}/complete", response_model=EmployeeOnboardingDetailOut)
def post_checklist_complete(
    body: ChecklistItemActionIn,
    onboarding_id: int = Path(..., ge=1),
    item_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> EmployeeOnboardingDetailOut:
    require_personnel_admin_or_403(user)
    user_id = _require_user_id(user)
    try:
        with engine.begin() as conn:
            result = complete_checklist_item(
                conn,
                onboarding_id=onboarding_id,
                item_id=item_id,
                actor_user_id=user_id,
                comment=body.comment,
            )
        return detail_to_out(result.detail)
    except EmployeeOnboardingNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except EmployeeOnboardingChecklistError as exc:
        raise _onboarding_http422(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post("/{onboarding_id}/checklist/{item_id}/skip", response_model=EmployeeOnboardingDetailOut)
def post_checklist_skip(
    body: ChecklistItemActionIn,
    onboarding_id: int = Path(..., ge=1),
    item_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> EmployeeOnboardingDetailOut:
    require_personnel_admin_or_403(user)
    user_id = _require_user_id(user)
    try:
        with engine.begin() as conn:
            result = skip_checklist_item(
                conn,
                onboarding_id=onboarding_id,
                item_id=item_id,
                actor_user_id=user_id,
                comment=body.comment,
            )
        return detail_to_out(result.detail)
    except EmployeeOnboardingNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except EmployeeOnboardingChecklistError as exc:
        raise _onboarding_http422(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post("/{onboarding_id}/checklist/custom", response_model=EmployeeOnboardingDetailOut)
def post_custom_checklist_item(
    body: CustomChecklistItemIn,
    onboarding_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> EmployeeOnboardingDetailOut:
    require_personnel_admin_or_403(user)
    user_id = _require_user_id(user)
    try:
        with engine.begin() as conn:
            result = add_custom_checklist_item(
                conn,
                onboarding_id=onboarding_id,
                title=body.title,
                actor_user_id=user_id,
            )
        return detail_to_out(result.detail)
    except EmployeeOnboardingNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except EmployeeOnboardingChecklistError as exc:
        raise _onboarding_http422(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post("/{onboarding_id}/complete", response_model=EmployeeOnboardingDetailOut)
def post_onboarding_complete(
    body: OnboardingCompleteIn,
    onboarding_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> EmployeeOnboardingDetailOut:
    require_personnel_admin_or_403(user)
    user_id = _require_user_id(user)
    try:
        with engine.begin() as conn:
            result = complete_onboarding(
                conn,
                onboarding_id=onboarding_id,
                actor_user_id=user_id,
                notes=body.notes,
            )
        return detail_to_out(result.detail)
    except EmployeeOnboardingNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except EmployeeOnboardingChecklistError as exc:
        raise _onboarding_http422(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post("/{onboarding_id}/cancel", response_model=EmployeeOnboardingDetailOut)
def post_onboarding_cancel(
    body: OnboardingCancelIn,
    onboarding_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> EmployeeOnboardingDetailOut:
    require_personnel_admin_or_403(user)
    user_id = _require_user_id(user)
    try:
        with engine.begin() as conn:
            result = cancel_onboarding(
                conn,
                onboarding_id=onboarding_id,
                actor_user_id=user_id,
                reason=body.reason,
            )
        return detail_to_out(result.detail)
    except EmployeeOnboardingNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except EmployeeOnboardingChecklistError as exc:
        raise _onboarding_http422(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)
