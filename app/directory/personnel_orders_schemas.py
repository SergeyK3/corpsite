"""Pydantic schemas for personnel orders read API (WP-PO-004A)."""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class PersonnelOrderHeaderOut(BaseModel):
    order_id: int
    order_number: Optional[str] = None
    order_date: Optional[str] = None
    order_type_code: str
    order_class: str
    status: str
    source_mode: str
    legal_basis_article: Optional[str] = None
    signed_by_employee_id: Optional[int] = None
    signed_by_name: Optional[str] = None
    signed_by_position: Optional[str] = None
    executor_name: Optional[str] = None
    basis_summary: Optional[str] = None
    comment: Optional[str] = None
    void_reason: Optional[str] = None
    voided_at: Optional[str] = None
    voided_by: Optional[int] = None
    created_by: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    is_archived: bool = False
    archive_summary_at: Optional[str] = None
    archive_summary_by_name: Optional[str] = None
    archive_summary_reason: Optional[str] = None


class PersonnelOrderListItemOut(PersonnelOrderHeaderOut):
    item_count: int = 0
    employee_ids: List[int] = Field(default_factory=list)
    employee_names: List[str] = Field(default_factory=list)


class PersonnelOrderListResponse(BaseModel):
    items: List[PersonnelOrderListItemOut]
    total: int
    limit: int
    offset: int


class PersonnelOrderItemOut(BaseModel):
    item_id: int
    order_id: int
    item_number: int
    item_type_code: str
    item_status: str
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    org_unit_id: Optional[int] = None
    org_unit_name: Optional[str] = None
    effective_date: Optional[str] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    void_reason: Optional[str] = None
    voided_at: Optional[str] = None
    voided_by: Optional[int] = None
    created_at: Optional[str] = None


class PersonnelOrderLocalizedTextOut(BaseModel):
    localized_text_id: int
    order_id: int
    locale: str
    title: Optional[str] = None
    preamble: Optional[str] = None
    body_text: Optional[str] = None
    render_version: int
    is_authoritative: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PersonnelOrderAttachmentOut(BaseModel):
    attachment_id: int
    order_id: int
    attachment_kind: str
    storage_type: str
    file_path: Optional[str] = None
    file_url: Optional[str] = None
    file_comment: Optional[str] = None
    locale: Optional[str] = None
    created_by: int
    created_at: Optional[str] = None


class PersonnelOrderPrintOut(BaseModel):
    print_id: int
    order_id: int
    locale: str
    format: str
    file_path: Optional[str] = None
    file_url: Optional[str] = None
    is_signed_copy: bool
    render_version: int
    generated_at: Optional[str] = None
    generated_by: Optional[int] = None


class PersonnelOrderLinkedEventOut(BaseModel):
    event_id: int
    order_id: Optional[int] = None
    order_item_id: Optional[int] = None
    employee_id: int
    employee_name: Optional[str] = None
    event_type: str
    event_class: str
    event_label: str
    lifecycle_status: str
    metadata: Optional[Dict[str, Any]] = None
    effective_date: Optional[str] = None
    from_org_unit_id: Optional[int] = None
    from_org_unit_name: Optional[str] = None
    to_org_unit_id: Optional[int] = None
    to_org_unit_name: Optional[str] = None
    from_position_id: Optional[int] = None
    from_position_name: Optional[str] = None
    to_position_id: Optional[int] = None
    to_position_name: Optional[str] = None
    from_rate: Optional[float] = None
    to_rate: Optional[float] = None
    order_ref: Optional[str] = None
    comment: Optional[str] = None
    created_at: Optional[str] = None


class PersonnelOrderDetailResponse(BaseModel):
    order: PersonnelOrderHeaderOut
    items: List[PersonnelOrderItemOut]
    localized_texts: List[PersonnelOrderLocalizedTextOut]
    attachments: List[PersonnelOrderAttachmentOut]
    prints: List[PersonnelOrderPrintOut]
    events: List[PersonnelOrderLinkedEventOut]


class PersonnelOrderSignatoryDefaultOut(BaseModel):
    signed_by_employee_id: Optional[int] = None
    signed_by_name: Optional[str] = None
    signed_by_position: Optional[str] = None
    warning: Optional[str] = None
    source: Optional[str] = None


class PersonnelOrderCreateIn(BaseModel):
    order_number: Optional[str] = Field(default=None, min_length=1, max_length=200)
    order_date: Optional[date] = None
    order_type_code: str = Field(..., min_length=1, max_length=80)
    source_mode: str = Field(default="DIGITAL", max_length=20)
    legal_basis_article: Optional[str] = Field(default=None, max_length=500)
    signed_by_employee_id: Optional[int] = Field(default=None, ge=1)
    signed_by_name: Optional[str] = Field(default=None, max_length=200)
    signed_by_position: Optional[str] = Field(default=None, max_length=200)
    executor_name: Optional[str] = Field(default=None, max_length=200)
    basis_summary: Optional[str] = Field(default=None, max_length=2000)
    comment: Optional[str] = Field(default=None, max_length=2000)


class PersonnelOrderUpdateIn(BaseModel):
    model_config = {"extra": "forbid"}

    order_number: Optional[str] = Field(default=None, min_length=1, max_length=200)
    order_date: Optional[date] = None
    order_type_code: Optional[str] = Field(default=None, min_length=1, max_length=80)
    source_mode: Optional[str] = Field(default=None, max_length=20)
    legal_basis_article: Optional[str] = Field(default=None, max_length=500)
    signed_by_employee_id: Optional[int] = Field(default=None, ge=1)
    signed_by_name: Optional[str] = Field(default=None, max_length=200)
    signed_by_position: Optional[str] = Field(default=None, max_length=200)
    executor_name: Optional[str] = Field(default=None, max_length=200)
    basis_summary: Optional[str] = Field(default=None, max_length=2000)
    comment: Optional[str] = Field(default=None, max_length=2000)


class PersonnelOrderItemCreateIn(BaseModel):
    item_type_code: str = Field(..., min_length=1, max_length=80)
    employee_id: Optional[int] = Field(default=None, ge=1)
    effective_date: Optional[date] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    item_number: Optional[int] = Field(default=None, ge=1)


class PersonnelOrderItemUpdateIn(BaseModel):
    model_config = {"extra": "forbid"}

    item_type_code: Optional[str] = Field(default=None, min_length=1, max_length=80)
    employee_id: Optional[int] = Field(default=None, ge=1)
    effective_date: Optional[date] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    payload: Optional[Dict[str, Any]] = None
    item_number: Optional[int] = Field(default=None, ge=1)


class PersonnelOrderLocalizedTextUpsertIn(BaseModel):
    title: Optional[str] = Field(default=None, max_length=500)
    preamble: Optional[str] = Field(default=None, max_length=4000)
    body_text: Optional[str] = None
    is_authoritative: Optional[bool] = None


class PersonnelOrderRegisterIn(BaseModel):
    target_status: str = Field(..., min_length=1, max_length=40)


class PersonnelOrderVoidIn(BaseModel):
    void_reason: str = Field(..., min_length=1, max_length=2000)


PersonnelOrderCancelReasonCode = Literal[
    "duplicate",
    "created_by_mistake",
    "no_longer_required",
    "replaced_before_registration",
    "test_record",
    "other",
]


class PersonnelOrderCancelIn(BaseModel):
    reason_code: PersonnelOrderCancelReasonCode
    reason_text: Optional[str] = Field(default=None, max_length=2000)


PersonnelOrderArchiveReasonCode = Literal[
    "completed",
    "voided_record",
    "migrated_legacy",
    "duplicate_reference",
    "other",
]


class PersonnelOrderArchiveIn(BaseModel):
    reason_code: str = Field(..., min_length=1, max_length=80)
    reason_text: Optional[str] = Field(default=None, max_length=2000)


class PersonnelOrderRestoreIn(BaseModel):
    model_config = {"extra": "forbid"}


class EditorialBlockOut(BaseModel):
    block_id: int
    scope: str
    order_item_id: Optional[int] = None
    locale: str
    block_type: str
    generated_text: Optional[str] = None
    override_text: Optional[str] = None
    effective_text: str = ""
    generator_key: Optional[str] = None
    generator_version: Optional[str] = None
    source_fingerprint: Optional[str] = None
    review_status: str
    basis_required: Optional[bool] = None
    editable: bool = False
    revision: int = 1
    generated_at: Optional[str] = None
    edited_at: Optional[str] = None
    edited_by_user_id: Optional[int] = None


class EditorialItemGroupOut(BaseModel):
    order_item_id: int
    item_number: int
    item_type_code: str
    basis_required: bool = False
    blocks: List[EditorialBlockOut] = Field(default_factory=list)


class EditorialStateResponse(BaseModel):
    order_id: int
    order_status: str
    editable: bool
    order_blocks: List[EditorialBlockOut] = Field(default_factory=list)
    items: List[EditorialItemGroupOut] = Field(default_factory=list)


class EditorialGenerateIn(BaseModel):
    model_config = {"extra": "forbid"}

    locale: Optional[str] = Field(default=None, max_length=8)
    item_id: Optional[int] = Field(default=None, ge=1)
    block_id: Optional[int] = Field(default=None, ge=1)
    block_type: Optional[str] = Field(default=None, max_length=40)


class EditorialBlockPatchIn(BaseModel):
    model_config = {"extra": "forbid"}

    override_text: Optional[str] = None
    clear_override: bool = False
    expected_revision: Optional[int] = Field(default=None, ge=1)


PersonnelOrderVoidKind = Literal["CANCEL", "ANNUL"]
PersonnelOrderLifecycleAuditAction = Literal[
    "CANCEL",
    "ANNUL",
    "ARCHIVE",
    "RESTORE",
    "VOID_APPLIED",
    "HARD_DELETE",
    "COMPENSATE_LINK",
]


class PersonnelOrderLifecycleAuditOut(BaseModel):
    id: int
    order_id: int
    action: PersonnelOrderLifecycleAuditAction
    previous_status: Optional[str] = None
    new_status: Optional[str] = None
    previous_void_kind: Optional[PersonnelOrderVoidKind] = None
    new_void_kind: Optional[PersonnelOrderVoidKind] = None
    actor_user_id: int
    reason_code: Optional[str] = None
    reason_text: Optional[str] = None
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None


class PersonnelOrderLifecycleAuditListResponse(BaseModel):
    items: List[PersonnelOrderLifecycleAuditOut]
    total: int
    limit: int
    offset: int
