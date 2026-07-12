"""Pydantic transport schemas for Operational Orders intake API."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class PartyReferenceIn(BaseModel):
    reference_type: Literal["PERSON", "POSITION_ROLE", "ORG_UNIT"]
    reference: str = Field(..., min_length=1)
    display_name: str | None = None


class DraftBlockIn(BaseModel):
    locale: Literal["ru", "kk"]
    block_type: Literal[
        "TITLE",
        "PREAMBLE",
        "BODY",
        "ORDER_ITEM",
        "CONTROL",
        "ATTACHMENT_REFERENCE",
        "SIGNATURE_NOTE",
        "OTHER",
    ]
    submitted_text: str = Field(..., min_length=1)
    source_type: Literal["SUBMITTED", "OVERRIDE", "IMPORTED", "GENERATED"] = "SUBMITTED"
    sequence: int = Field(default=1, ge=1)


class DraftWorkspaceCreateIn(BaseModel):
    initiator: PartyReferenceIn
    content_author: PartyReferenceIn
    submitting_org_unit_id: int
    organization_id: int | None = None
    blocks: list[DraftBlockIn] = Field(..., min_length=1)
    proposed_title: str | None = None
    proposed_signer: PartyReferenceIn | None = None
    source_language: Literal["ru", "kk"] | None = None
    required_locales: list[Literal["ru", "kk"]] | None = None


class DraftBlockAddIn(DraftBlockIn):
    pass


class DraftBlockEffectivePatchIn(BaseModel):
    workspace_effective_text: str
    expected_version: int | None = None


class VersionedActionIn(BaseModel):
    expected_version: int | None = None


class ClarificationResolveIn(BaseModel):
    resolution_note: str | None = None
    expected_version: int | None = None


class ValidationIssueOut(BaseModel):
    code: str
    severity: str
    message: str
    field_path: str | None = None
    metadata: dict[str, Any] | None = None


class ValidationResultOut(BaseModel):
    is_valid: bool
    has_errors: bool
    has_warnings: bool
    issues: list[ValidationIssueOut]


class DraftBlockOut(BaseModel):
    block_id: int
    workspace_id: int
    locale: str
    block_type: str
    submitted_text: str
    workspace_effective_text: str | None
    sequence: int
    source_type: str
    review_state: str
    version: int
    created_at: datetime
    updated_at: datetime


class ClarificationOut(BaseModel):
    clarification_id: int
    workspace_id: int
    code: str
    severity: str
    category: str
    message: str
    field_path: str | None
    status: str
    requested_by: int | None
    resolved_by: int | None
    resolution_note: str | None
    created_at: datetime
    resolved_at: datetime | None


class ProvenanceSummaryOut(BaseModel):
    provenance_id: int
    draft_block_id: int
    locale: str
    source_type: str
    action: str
    content_fingerprint: str | None
    created_at: datetime


class AuditSummaryOut(BaseModel):
    audit_id: int
    action: str
    actor_user_id: int | None
    created_at: datetime


class DraftWorkspaceSummaryOut(BaseModel):
    workspace_id: int
    organization_id: int
    drafting_path: str
    stage: str
    submitting_org_unit_id: int
    record_creator_user_id: int
    content_author_reference: str
    content_author_type: str
    proposed_title: str | None
    submitted_at: datetime
    accepted_at: datetime | None
    created_at: datetime
    updated_at: datetime
    version: int
    ru_present: bool | None = None
    kk_present: bool | None = None
    document_id: int | None = None
    open_clarification_count: int | None = None
    has_active_translation: bool | None = None


class LocaleCompletenessOut(BaseModel):
    ru_present: bool
    kk_present: bool
    locales_present: list[str]


class DraftWorkspaceDetailOut(BaseModel):
    workspace: DraftWorkspaceSummaryOut
    blocks: list[DraftBlockOut]
    provenance: list[ProvenanceSummaryOut]
    clarifications: list[ClarificationOut]
    audit: list[AuditSummaryOut]
    validation: ValidationResultOut
    locale_completeness: LocaleCompletenessOut
    readiness_for_editorial: bool
    readiness_for_editorial_package: bool = False
    translation_assignments: list[dict] = Field(default_factory=list)
    content_confirmations: list[dict] = Field(default_factory=list)
    bilingual_reconciliations: list[dict] = Field(default_factory=list)


class DraftWorkspaceListOut(BaseModel):
    items: list[DraftWorkspaceSummaryOut]
    total: int
    limit: int
    offset: int
