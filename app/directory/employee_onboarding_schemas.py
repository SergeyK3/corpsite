"""Pydantic schemas for Employee Onboarding directory API (WP-ONBOARDING-001)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.employee_onboarding.domain.models import (
    OnboardingDetailSnapshot,
    OnboardingListItemSnapshot,
    OnboardingTaskAuditSnapshot,
    OnboardingTaskListItemSnapshot,
)
from app.employee_onboarding.infrastructure.repository import is_task_overdue


class OnboardingChecklistAttachmentOut(BaseModel):
    attachment_id: int
    item_id: int
    file_url: str
    file_comment: str | None = None
    created_by: int
    created_at: datetime


class OnboardingChecklistItemOut(BaseModel):
    item_id: int
    onboarding_id: int
    item_code: str | None = None
    title: str
    sort_order: int
    is_custom: bool
    status: str
    completed_at: datetime | None = None
    completed_by_user_id: int | None = None
    comment: str | None = None
    due_date: datetime | None = None
    assignee_kind: str | None = None
    assignee_user_id: int | None = None
    assignee_employee_id: int | None = None
    priority: str = "normal"
    is_overdue: bool = False
    attachments: list[OnboardingChecklistAttachmentOut] = Field(default_factory=list)


class EmployeeOnboardingOut(BaseModel):
    onboarding_id: int
    employee_id: int
    application_id: int | None = None
    status: str
    started_at: datetime
    planned_end_at: datetime | None = None
    completed_at: datetime | None = None
    responsible_hr_id: int
    mentor_employee_id: int | None = None
    notes: str | None = None
    progress_percent: int = 0
    is_read_only: bool = False


class EmployeeOnboardingDetailOut(EmployeeOnboardingOut):
    checklist_items: list[OnboardingChecklistItemOut]
    overdue_count: int = 0


class OnboardingTaskListItemOut(BaseModel):
    item_id: int
    onboarding_id: int
    title: str
    status: str
    due_date: datetime | None = None
    priority: str
    assignee_kind: str | None = None
    assignee_user_id: int | None = None
    assignee_employee_id: int | None = None
    assignee_name: str | None = None
    employee_id: int
    employee_full_name: str | None = None
    org_unit_name: str | None = None
    onboarding_status: str
    is_overdue: bool


class OnboardingTaskListOut(BaseModel):
    items: list[OnboardingTaskListItemOut]
    total: int
    limit: int
    offset: int


class OnboardingDashboardOut(BaseModel):
    active_programs_count: int
    overdue_tasks_count: int
    due_soon_tasks_count: int
    completion_percent: int
    overdue_tasks: list[OnboardingTaskListItemOut]
    due_soon_tasks: list[OnboardingTaskListItemOut]


class OnboardingTaskAuditOut(BaseModel):
    audit_id: int
    item_id: int
    onboarding_id: int
    action: str
    actor_user_id: int | None = None
    actor_name: str | None = None
    payload: dict = Field(default_factory=dict)
    created_at: datetime


class OnboardingTaskAuditListOut(BaseModel):
    items: list[OnboardingTaskAuditOut]


class ChecklistTaskUpdateIn(BaseModel):
    due_date: datetime | None = None
    assignee_kind: str | None = None
    assignee_user_id: int | None = None
    assignee_employee_id: int | None = None
    priority: str | None = None
    comment: str | None = None


class ChecklistAttachmentIn(BaseModel):
    file_url: str = Field(..., min_length=1)
    file_comment: str | None = None


class BulkTaskIdsIn(BaseModel):
    item_ids: list[int] = Field(..., min_length=1)


class BulkAssignTasksIn(BulkTaskIdsIn):
    assignee_kind: str = Field(..., min_length=1)
    assignee_user_id: int | None = None
    assignee_employee_id: int | None = None


class BulkDueDateIn(BulkTaskIdsIn):
    due_date: datetime | None = None


class BulkCompleteTasksIn(BulkTaskIdsIn):
    comment: str | None = None


class BulkOperationOut(BaseModel):
    processed: int
    succeeded: int
    failed: int
    items: list[dict] = Field(default_factory=list)
    errors: list[dict] = Field(default_factory=list)


class EmployeeOnboardingListItemOut(BaseModel):
    onboarding_id: int
    employee_id: int
    application_id: int | None = None
    status: str
    started_at: datetime
    planned_end_at: datetime | None = None
    completed_at: datetime | None = None
    responsible_hr_id: int
    mentor_employee_id: int | None = None
    progress_percent: int
    employee_full_name: str | None = None
    org_unit_name: str | None = None
    responsible_hr_name: str | None = None
    is_read_only: bool = False


class EmployeeOnboardingListOut(BaseModel):
    items: list[EmployeeOnboardingListItemOut]
    total: int
    limit: int
    offset: int


class ChecklistItemActionIn(BaseModel):
    comment: str | None = None


class CustomChecklistItemIn(BaseModel):
    title: str = Field(..., min_length=1)


class OnboardingCancelIn(BaseModel):
    reason: str = Field(..., min_length=1)


class OnboardingCompleteIn(BaseModel):
    notes: str | None = None


def attachment_to_out(attachment) -> OnboardingChecklistAttachmentOut:
    return OnboardingChecklistAttachmentOut(
        attachment_id=attachment.attachment_id,
        item_id=attachment.item_id,
        file_url=attachment.file_url,
        file_comment=attachment.file_comment,
        created_by=attachment.created_by,
        created_at=attachment.created_at,
    )


def checklist_item_to_out(item, attachments=None) -> OnboardingChecklistItemOut:
    attachment_items = attachments or []
    return OnboardingChecklistItemOut(
        item_id=item.item_id,
        onboarding_id=item.onboarding_id,
        item_code=item.item_code,
        title=item.title,
        sort_order=item.sort_order,
        is_custom=item.is_custom,
        status=item.status,
        completed_at=item.completed_at,
        completed_by_user_id=item.completed_by_user_id,
        comment=item.comment,
        due_date=item.due_date,
        assignee_kind=item.assignee_kind,
        assignee_user_id=item.assignee_user_id,
        assignee_employee_id=item.assignee_employee_id,
        priority=item.priority,
        is_overdue=is_task_overdue(item),
        attachments=[attachment_to_out(a) for a in attachment_items],
    )


def detail_to_out(detail: OnboardingDetailSnapshot) -> EmployeeOnboardingDetailOut:
    onboarding = detail.onboarding
    attachments_by_item = detail.attachments_by_item or {}
    return EmployeeOnboardingDetailOut(
        onboarding_id=onboarding.onboarding_id,
        employee_id=onboarding.employee_id,
        application_id=onboarding.application_id,
        status=onboarding.status,
        started_at=onboarding.started_at,
        planned_end_at=onboarding.planned_end_at,
        completed_at=onboarding.completed_at,
        responsible_hr_id=onboarding.responsible_hr_id,
        mentor_employee_id=onboarding.mentor_employee_id,
        notes=onboarding.notes,
        progress_percent=detail.progress_percent,
        is_read_only=detail.is_read_only,
        overdue_count=detail.overdue_count,
        checklist_items=[
            checklist_item_to_out(item, attachments_by_item.get(item.item_id, ()))
            for item in detail.checklist_items
        ],
    )


def task_item_to_out(item: OnboardingTaskListItemSnapshot) -> OnboardingTaskListItemOut:
    return OnboardingTaskListItemOut(
        item_id=item.item_id,
        onboarding_id=item.onboarding_id,
        title=item.title,
        status=item.status,
        due_date=item.due_date,
        priority=item.priority,
        assignee_kind=item.assignee_kind,
        assignee_user_id=item.assignee_user_id,
        assignee_employee_id=item.assignee_employee_id,
        assignee_name=item.assignee_name,
        employee_id=item.employee_id,
        employee_full_name=item.employee_full_name,
        org_unit_name=item.org_unit_name,
        onboarding_status=item.onboarding_status,
        is_overdue=item.is_overdue,
    )


def audit_to_out(entry: OnboardingTaskAuditSnapshot) -> OnboardingTaskAuditOut:
    return OnboardingTaskAuditOut(
        audit_id=entry.audit_id,
        item_id=entry.item_id,
        onboarding_id=entry.onboarding_id,
        action=entry.action,
        actor_user_id=entry.actor_user_id,
        actor_name=entry.actor_name,
        payload=entry.payload,
        created_at=entry.created_at,
    )


def list_item_to_out(item: OnboardingListItemSnapshot) -> EmployeeOnboardingListItemOut:
    from app.employee_onboarding.domain.status import is_terminal_onboarding_status

    return EmployeeOnboardingListItemOut(
        onboarding_id=item.onboarding_id,
        employee_id=item.employee_id,
        application_id=item.application_id,
        status=item.status,
        started_at=item.started_at,
        planned_end_at=item.planned_end_at,
        completed_at=item.completed_at,
        responsible_hr_id=item.responsible_hr_id,
        mentor_employee_id=item.mentor_employee_id,
        progress_percent=item.progress_percent,
        employee_full_name=item.employee_full_name,
        org_unit_name=item.org_unit_name,
        responsible_hr_name=item.responsible_hr_name,
        is_read_only=is_terminal_onboarding_status(item.status),
    )
