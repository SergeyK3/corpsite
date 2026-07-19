"""MRD REST API schemas (WP-MRD-004)."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class MonthlyReferenceSummary(BaseModel):
    mrd_id: int
    report_period: date
    version: int
    status: str
    row_version: int
    entry_count: int
    forked_from_reference_id: int | None = None
    is_active_for_period: bool = False


class ActiveMrdResponse(BaseModel):
    report_period: date
    active: MonthlyReferenceSummary | None


class MonthlyReferenceListResponse(BaseModel):
    report_period: date | None = None
    active: MonthlyReferenceSummary | None = None
    items: list[MonthlyReferenceSummary]


class ForkSourcesResponse(BaseModel):
    items: list[MonthlyReferenceSummary]
    active_by_period: dict[str, int]


class ForkVersionRequest(BaseModel):
    command_id: str = Field(min_length=1)
    source_mrd_id: int = Field(ge=1)
    expected_active_row_version: int | None = Field(default=None, ge=1)
    notes: str | None = None


class ForkPeriodRequest(BaseModel):
    command_id: str = Field(min_length=1)
    source_mrd_id: int = Field(ge=1)
    target_report_period: date
    notes: str | None = None


class ForkMutationResult(BaseModel):
    command_id: str
    source_mrd_id: int
    target_mrd_id: int
    target_report_period: date
    target_version: int
    closed_mrd_id: int | None = None
    copied_entry_count: int
    version_event_ids: list[int]


class ForkMutationResponse(BaseModel):
    status: str
    result: ForkMutationResult


class CreationWindowResponse(BaseModel):
    reference_date: date
    allowed_periods: list[date]


class MrdEntrySummary(BaseModel):
    entry_id: int
    match_key: str
    entity_scope: str
    record_kind: str
    effective_payload: dict
    row_version: int


class MrdConfirmedChangeSummary(BaseModel):
    confirmed_change_id: int
    entity_scope: str
    attribute: str
    old_value: object | None = None
    new_value: object
    confirmed_at: str
    difference_origin_code: str
    source_batch_id: int | None = None
    basis: str | None = None


class MrdWorkspaceMetrics(BaseModel):
    detected_differences_count: int
    pending_differences_count: int
    confirmed_changes_count: int


class MrdWorkspaceEntriesPage(BaseModel):
    total: int
    items: list[MrdEntrySummary]


class MrdWorkspaceConfirmedChangesPage(BaseModel):
    total: int
    items: list[MrdConfirmedChangeSummary]


class MrdWorkspaceResponse(BaseModel):
    summary: MonthlyReferenceSummary
    metrics: MrdWorkspaceMetrics
    entries: MrdWorkspaceEntriesPage
    confirmed_changes: MrdWorkspaceConfirmedChangesPage


class HrReviewDifference(BaseModel):
    difference_id: int
    attribute: str
    field_label: str
    old_value: object | None = None
    new_value: object | None = None
    detected_value: object | None = None
    source_label: str | None = None
    lifecycle_status: str
    decision_status: str
    technical_diff_class: str | None = None
    record_kind: str | None = None
    row_version: int
    actions_available: bool = False


class HrReviewEmployee(BaseModel):
    match_key: str
    employee_id: int | None = None
    full_name: str
    position_raw: str
    rate: str | None = None
    category: str | None = None
    difference_count: int
    review_status: str
    differences: list[HrReviewDifference]


class HrReviewDepartmentSummary(BaseModel):
    total_employees: int
    without_changes: int
    with_changes: int
    awaiting_decision: int
    confirmed: int
    rejected: int


class HrReviewEmployeesPage(BaseModel):
    total: int
    items: list[HrReviewEmployee]


class HrReviewResponse(BaseModel):
    summary: MonthlyReferenceSummary
    org_groups: list[dict]
    departments: list[dict]
    department_summary: HrReviewDepartmentSummary | None = None
    employees: HrReviewEmployeesPage
