"""Pydantic schemas for OO-IMP-002 editorial workflow API."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.operational_orders.schemas.draft_workspace import PartyReferenceIn, ValidationResultOut


class VersionedEntityActionIn(BaseModel):
    expected_version: int | None = None


class TranslationAssignmentCreateIn(BaseModel):
    target_locale: Literal["ru", "kk"]
    assigned_to: PartyReferenceIn
    due_at: datetime | None = None
    notes: str | None = None
    expected_version: int | None = None


class TranslationAssignmentActionIn(BaseModel):
    expected_version: int | None = None
    assignment_expected_version: int | None = None


class TranslationAssignmentCompleteIn(BaseModel):
    target_block_id: int
    expected_version: int | None = None
    assignment_expected_version: int | None = None
    block_expected_version: int | None = None


class TranslationAssignmentOut(BaseModel):
    id: int
    workspace_id: int
    source_locale: str
    target_locale: str
    assigned_to_type: str
    assigned_to_reference: str
    assigned_to_display_name: str | None
    assigned_by_user_id: int
    status: str
    requested_at: datetime
    accepted_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    due_at: datetime | None
    source_block_version: int
    target_block_version: int | None
    source_content_fingerprint: str
    produced_content_fingerprint: str | None
    notes: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class TranslationAssignmentListOut(BaseModel):
    items: list[TranslationAssignmentOut]


class ContentConfirmationCreateIn(BaseModel):
    block_id: int
    confirmation_role: Literal["CONTENT_AUTHOR", "TRANSLATOR", "DOCUMENT_OPERATOR"]
    confirmer: PartyReferenceIn
    block_expected_version: int | None = None
    expected_version: int | None = None
    operator_recorded: bool = False


class ContentConfirmationRevokeIn(BaseModel):
    revocation_reason: str | None = None
    expected_version: int | None = None
    confirmation_expected_version: int | None = None


class ContentConfirmationOut(BaseModel):
    id: int
    workspace_id: int
    locale: str
    block_id: int
    block_version: int
    content_fingerprint: str
    confirmer_party_type: str
    confirmer_party_reference: str
    confirmer_display_name: str | None
    confirmer_user_id: int | None
    confirmation_role: str
    status: str
    confirmed_at: datetime | None
    revoked_at: datetime | None
    revocation_reason: str | None
    version: int
    created_at: datetime


class ContentConfirmationListOut(BaseModel):
    items: list[ContentConfirmationOut]


class BilingualReconciliationCreateIn(BaseModel):
    ru_block_id: int
    kk_block_id: int
    notes: str | None = None
    ru_block_expected_version: int | None = None
    kk_block_expected_version: int | None = None
    expected_version: int | None = None


class BilingualReconciliationInvalidateIn(BaseModel):
    invalidation_reason: str | None = None
    expected_version: int | None = None
    reconciliation_expected_version: int | None = None


class BilingualReconciliationOut(BaseModel):
    id: int
    workspace_id: int
    ru_block_id: int
    ru_block_version: int
    ru_content_fingerprint: str
    kk_block_id: int
    kk_block_version: int
    kk_content_fingerprint: str
    status: str
    reconciled_by_user_id: int
    reconciled_at: datetime | None
    notes: str | None
    invalidated_at: datetime | None
    invalidation_reason: str | None
    version: int
    created_at: datetime


class BilingualReconciliationListOut(BaseModel):
    items: list[BilingualReconciliationOut]


class EditorialPackageValidationOut(BaseModel):
    workspace_id: int
    validation: ValidationResultOut
