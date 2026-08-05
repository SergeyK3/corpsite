"""Pydantic schemas for Incoming Information API."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class IncomingDocumentRegisterIn(BaseModel):
    received_at: date
    document_type_id: int = Field(..., ge=1)
    receipt_channel_id: int = Field(..., ge=1)
    summary: str = Field(..., min_length=1, max_length=8000)
    access_level: str = "NORMAL"
    sender_kind: str
    sender_person_id: int | None = Field(default=None, ge=1)
    sender_employee_id: int | None = Field(default=None, ge=1)
    sender_org_unit_id: int | None = Field(default=None, ge=1)
    sender_text: str | None = Field(default=None, max_length=2000)
    addressee_kind: str
    addressee_user_id: int | None = Field(default=None, ge=1)
    addressee_employee_id: int | None = Field(default=None, ge=1)
    addressee_org_unit_id: int | None = Field(default=None, ge=1)
    addressee_position_id: int | None = Field(default=None, ge=1)
    addressee_text: str | None = Field(default=None, max_length=2000)
    registration_org_unit_id: int = Field(..., ge=1)
    responsible_org_unit_id: int | None = Field(default=None, ge=1)
    received_after_registration_exception: bool = False
    exception_comment: str | None = Field(default=None, max_length=2000)
    note: str | None = Field(default=None, max_length=4000)
    is_control_document: bool = False
    priority_level: str | None = Field(default=None, max_length=50)


class IncomingDocumentOut(BaseModel):
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


class IncomingDocumentListItemOut(BaseModel):
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


class IncomingDocumentListOut(BaseModel):
    items: list[IncomingDocumentListItemOut]
    total: int
    limit: int
    offset: int


class IncomingAuditEntryOut(BaseModel):
    audit_id: int
    incoming_document_id: int
    action: str
    field_name: str | None
    old_value: str | None
    new_value: str | None
    actor_user_id: int | None
    comment: str | None
    metadata: dict | None
    created_at: datetime


class IncomingAttachmentOut(BaseModel):
    attachment_id: int
    incoming_document_id: int
    file_id: str
    original_filename: str
    content_type: str
    size_bytes: int
    uploaded_by_user_id: int
    created_at: datetime


class OrderLinkIn(BaseModel):
    link_type_code: str
    comment: str | None = None


class OperationalOrderLinkOut(BaseModel):
    link_id: int
    incoming_document_id: int
    operational_order_document_id: int
    link_type_code: str
    comment: str | None
    created_by_user_id: int
    created_at: datetime
    operational_order_registration_number: str | None = None
    operational_order_status: str | None = None
    operational_order_title: str | None = None


class PersonnelOrderLinkOut(BaseModel):
    link_id: int
    incoming_document_id: int
    personnel_order_id: int
    link_type_code: str
    comment: str | None
    created_by_user_id: int
    created_at: datetime
    personnel_order_number: str | None = None
    personnel_order_status: str | None = None


class WorkflowExpectedVersionIn(BaseModel):
    expected_version: int = Field(..., ge=1)


class IncomingAssignIn(WorkflowExpectedVersionIn):
    primary_user_id: int = Field(..., ge=1)
    coexecutor_user_ids: list[int] = Field(default_factory=list)
    org_unit_id: int | None = Field(default=None, ge=1)
    due_date: date | None = None
    controller_user_id: int | None = Field(default=None, ge=1)


class IncomingReassignIn(WorkflowExpectedVersionIn):
    primary_user_id: int = Field(..., ge=1)
    reason: str | None = Field(default=None, max_length=2000)
    org_unit_id: int | None = Field(default=None, ge=1)


class IncomingTransferIn(WorkflowExpectedVersionIn):
    transfer_scope: str
    comment: str = Field(..., min_length=1, max_length=4000)
    target_org_unit_id: int | None = Field(default=None, ge=1)
    recipient_kind: str | None = None
    recipient_user_id: int | None = Field(default=None, ge=1)
    recipient_org_unit_id: int | None = Field(default=None, ge=1)
    recipient_text: str | None = Field(default=None, max_length=2000)


class IncomingChangeDeadlineIn(WorkflowExpectedVersionIn):
    new_due_date: date
    reason: str = Field(..., min_length=1, max_length=2000)


class IncomingResolveIn(WorkflowExpectedVersionIn):
    execution_result: str = Field(..., min_length=1, max_length=8000)
    executed_at: date | None = None


class IncomingCloseIn(WorkflowExpectedVersionIn):
    control_decision: str = Field(..., min_length=1, max_length=2000)
    comment: str | None = Field(default=None, max_length=4000)


class IncomingReopenIn(WorkflowExpectedVersionIn):
    reason: str = Field(..., min_length=1, max_length=2000)


class IncomingCancelIn(WorkflowExpectedVersionIn):
    reason: str = Field(..., min_length=1, max_length=2000)


class IncomingWorkflowCommentIn(WorkflowExpectedVersionIn):
    reason: str | None = Field(default=None, max_length=2000)
    comment: str | None = Field(default=None, max_length=2000)
