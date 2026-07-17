"""Employee onboarding domain snapshots (WP-ONBOARDING-001)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class OnboardingChecklistAttachmentSnapshot:
    attachment_id: int
    item_id: int
    file_url: str
    file_comment: str | None
    created_by: int
    created_at: datetime


@dataclass(frozen=True, slots=True)
class OnboardingChecklistItemSnapshot:
    item_id: int
    onboarding_id: int
    item_code: str | None
    title: str
    sort_order: int
    is_custom: bool
    status: str
    completed_at: datetime | None
    completed_by_user_id: int | None
    comment: str | None
    due_date: datetime | None
    assignee_kind: str | None
    assignee_user_id: int | None
    assignee_employee_id: int | None
    priority: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class OnboardingTaskAuditSnapshot:
    audit_id: int
    item_id: int
    onboarding_id: int
    action: str
    actor_user_id: int | None
    payload: dict
    created_at: datetime
    actor_name: str | None = None


@dataclass(frozen=True, slots=True)
class OnboardingTaskListItemSnapshot:
    item_id: int
    onboarding_id: int
    title: str
    status: str
    due_date: datetime | None
    priority: str
    assignee_kind: str | None
    assignee_user_id: int | None
    assignee_employee_id: int | None
    assignee_name: str | None
    employee_id: int
    employee_full_name: str | None
    org_unit_name: str | None
    onboarding_status: str
    is_overdue: bool


@dataclass(frozen=True, slots=True)
class OnboardingDashboardSnapshot:
    active_programs_count: int
    overdue_tasks_count: int
    due_soon_tasks_count: int
    completion_percent: int
    overdue_tasks: tuple[OnboardingTaskListItemSnapshot, ...]
    due_soon_tasks: tuple[OnboardingTaskListItemSnapshot, ...]


@dataclass(frozen=True, slots=True)
class EmployeeOnboardingSnapshot:
    onboarding_id: int
    employee_id: int
    application_id: int | None
    status: str
    started_at: datetime
    planned_end_at: datetime | None
    completed_at: datetime | None
    responsible_hr_id: int
    mentor_employee_id: int | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class OnboardingDetailSnapshot:
    onboarding: EmployeeOnboardingSnapshot
    checklist_items: tuple[OnboardingChecklistItemSnapshot, ...]
    progress_percent: int
    is_read_only: bool
    overdue_count: int = 0
    attachments_by_item: dict[int, tuple[OnboardingChecklistAttachmentSnapshot, ...]] | None = None


@dataclass(frozen=True, slots=True)
class OnboardingListItemSnapshot:
    onboarding_id: int
    employee_id: int
    application_id: int | None
    status: str
    started_at: datetime
    planned_end_at: datetime | None
    completed_at: datetime | None
    responsible_hr_id: int
    mentor_employee_id: int | None
    progress_percent: int
    employee_full_name: str | None
    org_unit_name: str | None
    responsible_hr_name: str | None
