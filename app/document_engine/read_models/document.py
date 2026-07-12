"""Document runtime read model (UDE-009)."""
from __future__ import annotations

from dataclasses import dataclass

from app.document_engine.value_objects.identity import (
    DocumentId,
    DocumentKind,
    DocumentSpecialization,
)
from app.document_engine.value_objects.lifecycle import (
    ArchiveState,
    DocumentLifecycleState,
    VoidKind,
)


@dataclass(frozen=True, slots=True)
class DocumentMetadataReadModel:
    order_number: str | None
    order_date: str | None
    order_type_code: str
    source_mode: str
    legal_basis_article: str | None
    basis_summary: str | None
    comment: str | None
    created_by: int | None
    created_at: str | None
    updated_at: str | None
    archived_at: str | None = None
    archive_reason_code: str | None = None
    archive_reason_text: str | None = None


@dataclass(frozen=True, slots=True)
class DocumentReadModel:
    document_id: DocumentId
    document_kind: DocumentKind
    specialization: DocumentSpecialization
    lifecycle_state: DocumentLifecycleState
    archive_state: ArchiveState
    void_kind: VoidKind | None
    metadata: DocumentMetadataReadModel
    legacy_status: str
    is_archived: bool
