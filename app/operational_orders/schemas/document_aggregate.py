"""Pydantic transport schemas for Operational Orders document aggregate API."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.operational_orders.schemas.draft_workspace import PartyReferenceIn, ValidationResultOut


class PromotionIn(BaseModel):
    expected_workspace_version: int | None = Field(default=None, alias="expected_version")

    model_config = {"populate_by_name": True}


class DocumentSummaryOut(BaseModel):
    document_id: int
    workspace_id: int
    document_kind: str
    status: str
    created_from_workspace_version: int
    created_from_workspace_fingerprint: str
    promotion_id: int
    created_at: datetime
    created_by_user_id: int
    version: int
    submitting_org_unit_id: int | None = None
    ready_for_signature_at: datetime | None = None
    ready_for_signature_by_user_id: int | None = None


class DocumentVersionOut(BaseModel):
    id: int
    document_id: int
    version_number: int
    workspace_version: int
    promotion_snapshot_version: int
    snapshot_fingerprint: str
    is_current: bool
    created_at: datetime
    created_by_user_id: int


class SigningAuthorityOut(BaseModel):
    id: int
    document_id: int
    document_version_id: int
    authority_party_type: str
    authority_party_reference: str
    authority_display_name: str | None = None
    authority_position_id: int | None = None
    authority_org_unit_id: int | None = None
    authority_basis: str | None = None
    assigned_by_user_id: int
    status: str
    assigned_at: datetime
    superseded_at: datetime | None = None
    version: int


class LifecycleAuditOut(BaseModel):
    id: int
    document_id: int
    document_version_id: int | None = None
    transition_from: str | None = None
    transition_to: str | None = None
    action: str
    actor_user_id: int | None = None
    reason: str | None = None
    created_at: datetime
    document_version_before: int | None = None
    document_version_after: int | None = None


class OrgScopeSourceOut(BaseModel):
    submitting_org_unit_id: int | None = None
    workspace_id: int


class DocumentLocalizationOut(BaseModel):
    id: int
    document_version_id: int
    locale: str
    block_type: str
    sequence: int
    official_text: str
    content_fingerprint: str
    source_workspace_block_version: int
    source_confirmation_ids: list[int]
    source_reconciliation_id: int | None
    created_at: datetime


class PromotionSummaryOut(BaseModel):
    id: int
    workspace_id: int
    document_id: int | None
    status: str
    workspace_version: int
    workspace_fingerprint: str
    snapshot_fingerprint: str | None
    snapshot_version: int
    promoted_by_user_id: int
    promoted_at: datetime | None
    created_at: datetime


class PromotionAuditOut(BaseModel):
    id: int
    promotion_id: int
    action: str
    actor_user_id: int | None
    metadata_json: dict[str, Any] | None
    created_at: datetime


class DocumentDetailOut(BaseModel):
    document: DocumentSummaryOut
    current_version: DocumentVersionOut | None = None
    promotion: PromotionSummaryOut | None = None
    signing_authority: SigningAuthorityOut | None = None
    readiness_validation: ValidationResultOut | None = None
    latest_lifecycle_transition: LifecycleAuditOut | None = None
    org_scope_source: OrgScopeSourceOut | None = None
    workspace_drift_detected: bool = False
    revision_recommended: bool = False


class DocumentVersionDetailOut(BaseModel):
    document: DocumentSummaryOut
    version: DocumentVersionOut
    localizations: list[DocumentLocalizationOut]


class DocumentLocalizationListOut(BaseModel):
    document_id: int
    version_number: int
    items: list[DocumentLocalizationOut]


class PromotionResultOut(BaseModel):
    workspace_id: int
    document: DocumentDetailOut
    validation: ValidationResultOut
    idempotent_replay: bool = False
    workspace_frozen: bool = False
    workspace_drift_detected: bool = False
    revision_recommended: bool = False
    document_id: int | None = None
    promotion_id: int | None = None


class VersionedDocumentActionIn(BaseModel):
    expected_document_version: int | None = Field(default=None, alias="expected_version")

    model_config = {"populate_by_name": True}


class SigningAuthorityAssignIn(VersionedDocumentActionIn):
    authority: PartyReferenceIn
    authority_position_id: int | None = None
    authority_org_unit_id: int | None = None
    authority_basis: str | None = None


class ReturnToCreatedIn(VersionedDocumentActionIn):
    reason: str = Field(..., min_length=1)


class SignatureReadinessOut(BaseModel):
    document_id: int
    status: str
    aggregate_version: int
    signing_authority: SigningAuthorityOut | None = None
    readiness_validation: ValidationResultOut
    workspace_drift_detected: bool = False
    revision_recommended: bool = False


class SigningAuthorityResultOut(BaseModel):
    document_id: int
    signing_authority: SigningAuthorityOut | None = None
    document: DocumentSummaryOut | None = None
    idempotent_replay: bool = False


class ReadyForSignatureResultOut(BaseModel):
    document: DocumentDetailOut
    validation: ValidationResultOut
    idempotent_replay: bool = False


class ReturnToCreatedResultOut(BaseModel):
    document: DocumentDetailOut
    idempotent_replay: bool = False
