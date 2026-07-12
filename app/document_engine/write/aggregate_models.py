"""Runtime document aggregate models (UDE-012).

Not persistence, not ORM — in-memory aggregate only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Tuple

from app.document_engine.contracts.validation import ValidationResult
from app.document_engine.editorial.editorial_models import OfficialDraftLocaleBlock, OfficialDraftSnapshot
from app.document_engine.value_objects.identity import DocumentId, DocumentKind, DocumentSpecialization
from app.document_engine.value_objects.lifecycle import ArchiveState, DocumentLifecycleState, VoidKind


@dataclass(frozen=True, slots=True)
class AggregateMetadata:
    """Runtime aggregate metadata — not persistence row."""

    order_type_code: str
    order_number: str | None = None
    order_date: str | None = None
    source_mode: str | None = None
    legal_basis_article: str | None = None
    basis_summary: str | None = None
    workspace_reference: str | None = None
    extra: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DocumentAggregate:
    """Runtime document aggregate — no ORM, no DB."""

    document_id: DocumentId
    document_kind: DocumentKind
    specialization: DocumentSpecialization
    lifecycle_state: DocumentLifecycleState
    archive_state: ArchiveState
    void_kind: VoidKind | None
    metadata: AggregateMetadata
    locale_blocks: Tuple[OfficialDraftLocaleBlock, ...] = field(default_factory=tuple)
    official_draft: OfficialDraftSnapshot | None = None
    item_count: int = 0
    validation_state: ValidationResult = field(default_factory=ValidationResult)

    @property
    def is_archived(self) -> bool:
        return self.archive_state == ArchiveState.ARCHIVED
