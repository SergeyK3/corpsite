"""Personnel Application domain snapshot types."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PersonnelApplicationSnapshot:
    application_id: int
    person_id: int
    status: str
    application_received_at: date
    application_source: str
    vacancy_check_status: str
    vacancy_checked_at: datetime | None
    vacancy_checked_by_user_id: int | None
    intended_org_group_id: int | None
    intended_org_unit_id: int | None
    intended_position_id: int | None
    intended_employment_rate: Decimal | None
    intended_vacancy_text: str | None
    contact_mobile_phone: str | None
    contact_email: str | None
    director_resolution_status: str | None
    director_resolution_at: datetime | None
    director_resolution_by_user_id: int | None
    director_resolution_note: str | None
    personnel_order_id: int | None
    registered_at: datetime
    registered_by_user_id: int
    hr_note: str | None
    idempotency_key: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class PersonnelApplicationCreatePayload:
    person_id: int
    application_received_at: date
    application_source: str
    vacancy_check_status: str
    vacancy_checked_at: datetime | None
    vacancy_checked_by_user_id: int | None
    intended_org_group_id: int | None
    intended_org_unit_id: int | None
    intended_position_id: int | None
    intended_employment_rate: Decimal | None
    intended_vacancy_text: str | None
    contact_mobile_phone: str | None
    contact_email: str | None
    registered_by_user_id: int
    hr_note: str | None
    idempotency_key: str | None
    status: str


@dataclass(frozen=True, slots=True)
class ResolutionAuditSnapshot:
    audit_id: int
    application_id: int
    action: str
    previous_application_status: str | None
    new_application_status: str
    previous_resolution_status: str | None
    new_resolution_status: str | None
    comment: str | None
    actor_user_id: int
    created_at: datetime


@dataclass(frozen=True, slots=True)
class HireOrderDraftResult:
    application_id: int
    personnel_order_id: int
    idempotent_replay: bool
    application_status: str


@dataclass(frozen=True, slots=True)
class ApplicationApplyResult:
    application_id: int
    personnel_order_id: int
    employee_id: int
    idempotent_replay: bool
    application_status: str


@dataclass(frozen=True, slots=True)
class LifecycleAuditSnapshot:
    audit_id: int
    application_id: int
    action: str
    previous_status: str | None
    new_status: str | None
    comment: str | None
    actor_user_id: int | None
    metadata: dict | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class TimelineEvent:
    code: str
    label: str
    occurred_at: datetime
    actor_user_id: int | None = None
    detail: str | None = None
    metadata: dict | None = None
