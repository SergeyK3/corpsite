"""Pydantic transport schemas for Operational Orders document aggregate API."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.operational_orders.schemas.draft_workspace import ValidationResultOut


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
