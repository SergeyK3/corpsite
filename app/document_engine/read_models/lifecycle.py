"""Lifecycle runtime read model (UDE-009)."""
from __future__ import annotations

from dataclasses import dataclass

from app.document_engine.value_objects.identity import DocumentId
from app.document_engine.value_objects.lifecycle import (
    ArchiveState,
    DocumentLifecycleState,
    VoidKind,
)


@dataclass(frozen=True, slots=True)
class LifecycleReadModel:
    document_id: DocumentId
    lifecycle_state: DocumentLifecycleState
    archive_state: ArchiveState
    void_kind: VoidKind | None
    legacy_status: str
    is_archived: bool
