"""Pydantic schemas for Personnel Application directory API."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.personnel_applications.domain.models import PersonnelApplicationSnapshot
from app.personnel_applications.domain.status import (
    VACANCY_CHECK_CONFIRMED_VISUALLY,
    is_terminal_application_status,
)


class PersonnelApplicationPreviewIn(BaseModel):
    iin: str = Field(..., min_length=1)


class PersonnelApplicationPreviewOut(BaseModel):
    iin: str
    person_exists: bool
    person_id: int | None = None
    full_name: str | None = None
    hr_relationship_context: str | None = None
    has_active_employee: bool
    has_active_application: bool
    active_application_id: int | None = None
    can_register: bool
    block_reason: str | None = None


class PersonnelApplicationRegisterIn(BaseModel):
    iin: str = Field(..., min_length=1)
    full_name: str | None = None
    birth_date: date | None = None
    application_received_at: date
    vacancy_check_status: str = VACANCY_CHECK_CONFIRMED_VISUALLY
    vacancy_checked_at: datetime | None = None
    vacancy_checked_by_user_id: int | None = None
    intended_org_group_id: int | None = None
    intended_org_unit_id: int | None = None
    intended_position_id: int | None = None
    intended_employment_rate: Decimal | None = None
    intended_vacancy_text: str | None = None
    contact_mobile_phone: str | None = None
    contact_email: str | None = None
    hr_note: str | None = None
    idempotency_key: str | None = None


class PersonnelApplicationRegisterOut(BaseModel):
    person_id: int
    application_id: int
    action: Literal["created", "opened_existing"]
    card_href: str


class PersonnelApplicationDetailOut(BaseModel):
    application_id: int
    person_id: int
    full_name: str | None = None
    iin: str | None = None
    status: str
    application_received_at: date
    application_source: str
    vacancy_check_status: str
    vacancy_checked_at: datetime | None = None
    vacancy_checked_by_user_id: int | None = None
    intended_org_group_id: int | None = None
    intended_org_unit_id: int | None = None
    intended_position_id: int | None = None
    intended_org_group_name: str | None = None
    intended_org_unit_name: str | None = None
    intended_position_name: str | None = None
    intended_employment_rate: Decimal | None = None
    intended_vacancy_text: str | None = None
    contact_mobile_phone: str | None = None
    contact_email: str | None = None
    director_resolution_status: str | None = None
    director_resolution_at: datetime | None = None
    director_resolution_by_user_id: int | None = None
    director_resolution_note: str | None = None
    personnel_order_id: int | None = None
    registered_at: datetime
    registered_by_user_id: int
    registered_by_name: str | None = None
    hr_note: str | None = None
    idempotency_key: str | None = None
    created_at: datetime
    updated_at: datetime
    intake_link_status: str | None = None
    intake_draft_status: str | None = None
    intake_opened_at: datetime | None = None
    intake_submitted_at: datetime | None = None
    employee_id: int | None = None
    employee_full_name: str | None = None
    employee_created_at: datetime | None = None
    personnel_order_number: str | None = None
    personnel_order_date: date | None = None
    hire_applied_at: datetime | None = None
    completed_at: datetime | None = None
    closed_at: datetime | None = None
    cancel_reason: str | None = None
    cancelled_by_user_id: int | None = None
    closed_by_user_id: int | None = None
    is_read_only: bool = False


class PersonnelApplicationHistoryOut(BaseModel):
    person_id: int
    items: list[PersonnelApplicationDetailOut]


class PersonnelApplicationListItemOut(BaseModel):
    application_id: int
    person_id: int
    full_name: str | None = None
    iin: str | None = None
    status: str
    application_received_at: date
    intended_org_group_id: int | None = None
    intended_org_unit_id: int | None = None
    intended_position_id: int | None = None
    intended_org_group_name: str | None = None
    intended_org_unit_name: str | None = None
    intended_position_name: str | None = None
    registered_at: datetime
    registered_by_user_id: int
    registered_by_name: str | None = None
    director_resolution_status: str | None = None
    personnel_order_id: int | None = None
    is_active: bool
    intake_link_status: str | None = None
    intake_draft_status: str | None = None
    intake_opened_at: datetime | None = None
    intake_submitted_at: datetime | None = None
    intake_link_display_state: str | None = None
    intake_url_path: str | None = None
    employee_id: int | None = None
    employee_full_name: str | None = None
    completed_at: datetime | None = None
    closed_at: datetime | None = None
    is_read_only: bool = False


class PersonnelApplicationListOut(BaseModel):
    items: list[PersonnelApplicationListItemOut]
    total: int
    limit: int
    offset: int


def list_item_to_out(item) -> PersonnelApplicationListItemOut:
    return PersonnelApplicationListItemOut(
        application_id=item.application_id,
        person_id=item.person_id,
        full_name=item.full_name,
        iin=item.iin,
        status=item.status,
        application_received_at=item.application_received_at,
        intended_org_group_id=item.intended_org_group_id,
        intended_org_unit_id=item.intended_org_unit_id,
        intended_position_id=item.intended_position_id,
        intended_org_group_name=item.intended_org_group_name,
        intended_org_unit_name=item.intended_org_unit_name,
        intended_position_name=item.intended_position_name,
        registered_at=item.registered_at,
        registered_by_user_id=item.registered_by_user_id,
        registered_by_name=item.registered_by_name,
        director_resolution_status=item.director_resolution_status,
        personnel_order_id=item.personnel_order_id,
        is_active=item.is_active,
        intake_link_status=getattr(item, "intake_link_status", None),
        intake_draft_status=getattr(item, "intake_draft_status", None),
        intake_opened_at=getattr(item, "intake_opened_at", None),
        intake_submitted_at=getattr(item, "intake_submitted_at", None),
        intake_link_display_state=getattr(item, "intake_link_display_state", None),
        intake_url_path=getattr(item, "intake_url_path", None),
        employee_id=getattr(item, "employee_id", None),
        employee_full_name=getattr(item, "employee_full_name", None),
        completed_at=getattr(item, "completed_at", None),
        closed_at=getattr(item, "closed_at", None),
        is_read_only=not item.is_active,
    )


def snapshot_to_detail(
    snapshot: PersonnelApplicationSnapshot,
    *,
    full_name: str | None = None,
    iin: str | None = None,
    intended_org_group_name: str | None = None,
    intended_org_unit_name: str | None = None,
    intended_position_name: str | None = None,
    registered_by_name: str | None = None,
    intake_link_status: str | None = None,
    intake_draft_status: str | None = None,
    intake_opened_at: datetime | None = None,
    intake_submitted_at: datetime | None = None,
    employee_id: int | None = None,
    employee_full_name: str | None = None,
    employee_created_at: datetime | None = None,
    personnel_order_number: str | None = None,
    personnel_order_date: date | None = None,
    hire_applied_at: datetime | None = None,
    completed_at: datetime | None = None,
    closed_at: datetime | None = None,
    cancel_reason: str | None = None,
    cancelled_by_user_id: int | None = None,
    closed_by_user_id: int | None = None,
) -> PersonnelApplicationDetailOut:
    return PersonnelApplicationDetailOut(
        application_id=snapshot.application_id,
        person_id=snapshot.person_id,
        full_name=full_name,
        iin=iin,
        status=snapshot.status,
        application_received_at=snapshot.application_received_at,
        application_source=snapshot.application_source,
        vacancy_check_status=snapshot.vacancy_check_status,
        vacancy_checked_at=snapshot.vacancy_checked_at,
        vacancy_checked_by_user_id=snapshot.vacancy_checked_by_user_id,
        intended_org_group_id=snapshot.intended_org_group_id,
        intended_org_unit_id=snapshot.intended_org_unit_id,
        intended_position_id=snapshot.intended_position_id,
        intended_org_group_name=intended_org_group_name,
        intended_org_unit_name=intended_org_unit_name,
        intended_position_name=intended_position_name,
        intended_employment_rate=snapshot.intended_employment_rate,
        intended_vacancy_text=snapshot.intended_vacancy_text,
        contact_mobile_phone=snapshot.contact_mobile_phone,
        contact_email=snapshot.contact_email,
        director_resolution_status=snapshot.director_resolution_status,
        director_resolution_at=snapshot.director_resolution_at,
        director_resolution_by_user_id=snapshot.director_resolution_by_user_id,
        director_resolution_note=snapshot.director_resolution_note,
        personnel_order_id=snapshot.personnel_order_id,
        registered_at=snapshot.registered_at,
        registered_by_user_id=snapshot.registered_by_user_id,
        registered_by_name=registered_by_name,
        hr_note=snapshot.hr_note,
        idempotency_key=snapshot.idempotency_key,
        created_at=snapshot.created_at,
        updated_at=snapshot.updated_at,
        intake_link_status=intake_link_status,
        intake_draft_status=intake_draft_status,
        intake_opened_at=intake_opened_at,
        intake_submitted_at=intake_submitted_at,
        employee_id=employee_id,
        employee_full_name=employee_full_name,
        employee_created_at=employee_created_at,
        personnel_order_number=personnel_order_number,
        personnel_order_date=personnel_order_date,
        hire_applied_at=hire_applied_at,
        completed_at=completed_at,
        closed_at=closed_at,
        cancel_reason=cancel_reason,
        cancelled_by_user_id=cancelled_by_user_id,
        closed_by_user_id=closed_by_user_id,
        is_read_only=is_terminal_application_status(snapshot.status),
    )


class PersonnelApplicationCancelIn(BaseModel):
    reason: str = Field(..., min_length=1)


class LifecycleAuditOut(BaseModel):
    audit_id: int
    application_id: int
    action: str
    previous_status: str | None = None
    new_status: str | None = None
    comment: str | None = None
    actor_user_id: int | None = None
    metadata: dict | None = None
    created_at: datetime


class LifecycleAuditListOut(BaseModel):
    items: list[LifecycleAuditOut]


class CombinedAuditOut(BaseModel):
    source: str
    audit_id: int
    action: str
    previous_status: str | None = None
    new_status: str | None = None
    comment: str | None = None
    actor_user_id: int | None = None
    metadata: dict | None = None
    created_at: datetime


class CombinedAuditListOut(BaseModel):
    items: list[CombinedAuditOut]


class TimelineEventOut(BaseModel):
    code: str
    label: str
    occurred_at: datetime
    actor_user_id: int | None = None
    detail: str | None = None
    metadata: dict | None = None


class ApplicationTimelineOut(BaseModel):
    application_id: int
    items: list[TimelineEventOut]


class PersonnelApplicationCancelOut(BaseModel):
    application_id: int
    status: str
    closed_at: datetime
    audit: LifecycleAuditOut


def lifecycle_audit_to_out(audit) -> LifecycleAuditOut:
    return LifecycleAuditOut(
        audit_id=audit.audit_id,
        application_id=audit.application_id,
        action=audit.action,
        previous_status=audit.previous_status,
        new_status=audit.new_status,
        comment=audit.comment,
        actor_user_id=audit.actor_user_id,
        metadata=audit.metadata,
        created_at=audit.created_at,
    )


def timeline_event_to_out(event) -> TimelineEventOut:
    return TimelineEventOut(
        code=event.code,
        label=event.label,
        occurred_at=event.occurred_at,
        actor_user_id=event.actor_user_id,
        detail=event.detail,
        metadata=event.metadata,
    )


class DirectorResolutionRecordIn(BaseModel):
    outcome: str = Field(..., min_length=1)
    comment: str | None = None


class DirectorResolutionChangeIn(BaseModel):
    outcome: str = Field(..., min_length=1)
    comment: str | None = None


class ResolutionAuditOut(BaseModel):
    audit_id: int
    application_id: int
    action: str
    previous_application_status: str | None = None
    new_application_status: str
    previous_resolution_status: str | None = None
    new_resolution_status: str | None = None
    comment: str | None = None
    actor_user_id: int
    created_at: datetime


class ResolutionAuditListOut(BaseModel):
    items: list[ResolutionAuditOut]


class DirectorResolutionActionOut(BaseModel):
    application_id: int
    status: str
    director_resolution_status: str | None = None
    director_resolution_at: datetime | None = None
    director_resolution_by_user_id: int | None = None
    director_resolution_note: str | None = None
    audit: ResolutionAuditOut


class HireOrderDraftOut(BaseModel):
    application_id: int
    personnel_order_id: int
    idempotent_replay: bool
    application_status: str


class ApplicationApplyOut(BaseModel):
    application_id: int
    personnel_order_id: int
    employee_id: int
    idempotent_replay: bool
    application_status: str


def audit_to_out(audit) -> ResolutionAuditOut:
    return ResolutionAuditOut(
        audit_id=audit.audit_id,
        application_id=audit.application_id,
        action=audit.action,
        previous_application_status=audit.previous_application_status,
        new_application_status=audit.new_application_status,
        previous_resolution_status=audit.previous_resolution_status,
        new_resolution_status=audit.new_resolution_status,
        comment=audit.comment,
        actor_user_id=audit.actor_user_id,
        created_at=audit.created_at,
    )


def application_resolution_to_out(result) -> DirectorResolutionActionOut:
    app = result.application
    return DirectorResolutionActionOut(
        application_id=app.application_id,
        status=app.status,
        director_resolution_status=app.director_resolution_status,
        director_resolution_at=app.director_resolution_at,
        director_resolution_by_user_id=app.director_resolution_by_user_id,
        director_resolution_note=app.director_resolution_note,
        audit=audit_to_out(result.audit),
    )
