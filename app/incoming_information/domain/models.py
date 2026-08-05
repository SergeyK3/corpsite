"""Incoming Information domain dataclasses."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class IncomingDocumentSnapshot:
    incoming_document_id: int
    registration_number: str
    registration_year: int
    registration_seq: int
    received_at: date
    registered_at: datetime
    document_type_id: int
    document_type_code: str
    document_type_label: str
    receipt_channel_id: int
    receipt_channel_code: str
    receipt_channel_label: str
    status_id: int
    status_code: str
    status_label: str
    status_is_terminal: bool
    planned_result_id: int | None
    planned_result_code: str | None
    planned_result_label: str | None
    summary: str
    access_level: str
    sender_kind: str
    sender_person_id: int | None
    sender_employee_id: int | None
    sender_org_unit_id: int | None
    sender_text: str | None
    addressee_kind: str
    addressee_user_id: int | None
    addressee_employee_id: int | None
    addressee_org_unit_id: int | None
    addressee_position_id: int | None
    addressee_text: str | None
    registration_org_unit_id: int
    responsible_org_unit_id: int
    resolution_text: str | None
    due_date: date | None
    planned_result_note: str | None
    executed_at: date | None
    execution_result: str | None
    closed_at: datetime | None
    note: str | None
    priority_level: str | None
    is_control_document: bool
    received_after_registration_exception: bool
    exception_comment: str | None
    transfer_comment: str | None
    cancellation_reason: str | None
    control_decision: str | None
    control_comment: str | None
    controller_user_id: int | None
    row_version: int
    closed_by_user_id: int | None
    cancelled_at: datetime | None
    cancelled_by_user_id: int | None
    transferred_at: datetime | None
    transferred_by_user_id: int | None
    resolve_recorded_at: datetime | None
    reopened_at: datetime | None
    reopen_reason: str | None
    reopen_count: int
    external_recipient_kind: str | None
    external_recipient_user_id: int | None
    external_recipient_org_unit_id: int | None
    external_recipient_text: str | None
    created_by_user_id: int
    updated_by_user_id: int | None
    created_at: datetime
    updated_at: datetime
    is_overdue: bool


@dataclass(frozen=True, slots=True)
class IncomingDocumentListItem:
    incoming_document_id: int
    registration_number: str
    registered_at: datetime
    document_type_label: str
    summary: str
    sender_display: str
    addressee_display: str
    primary_executor_display: str | None
    due_date: date | None
    status_code: str
    status_label: str
    access_level: str
    responsible_org_unit_id: int
    is_overdue: bool


@dataclass(frozen=True, slots=True)
class IncomingDocumentCreatePayload:
    received_at: date
    document_type_id: int
    receipt_channel_id: int
    summary: str
    access_level: str
    sender_kind: str
    sender_person_id: int | None
    sender_employee_id: int | None
    sender_org_unit_id: int | None
    sender_text: str | None
    addressee_kind: str
    addressee_user_id: int | None
    addressee_employee_id: int | None
    addressee_org_unit_id: int | None
    addressee_position_id: int | None
    addressee_text: str | None
    registration_org_unit_id: int
    responsible_org_unit_id: int
    received_after_registration_exception: bool
    exception_comment: str | None
    note: str | None
    is_control_document: bool
    priority_level: str | None
    created_by_user_id: int


@dataclass(frozen=True, slots=True)
class IncomingAttachmentSnapshot:
    attachment_id: int
    incoming_document_id: int
    file_id: str
    original_filename: str
    content_type: str
    size_bytes: int
    uploaded_by_user_id: int
    created_at: datetime


@dataclass(frozen=True, slots=True)
class OperationalOrderLinkSnapshot:
    link_id: int
    incoming_document_id: int
    operational_order_document_id: int
    link_type_code: str
    comment: str | None
    created_by_user_id: int
    created_at: datetime
    operational_order_registration_number: str | None
    operational_order_status: str | None
    operational_order_title: str | None


@dataclass(frozen=True, slots=True)
class PersonnelOrderLinkSnapshot:
    link_id: int
    incoming_document_id: int
    personnel_order_id: int
    link_type_code: str
    comment: str | None
    created_by_user_id: int
    created_at: datetime
    personnel_order_number: str | None
    personnel_order_status: str | None
