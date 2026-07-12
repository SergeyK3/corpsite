"""Runtime domain events (UDE-012).

In-memory events only — not written to audit persistence.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from app.document_engine.value_objects.identity import DocumentId
from app.document_engine.value_objects.lifecycle import ArchiveState, DocumentLifecycleState, VoidKind


@dataclass(frozen=True, slots=True)
class DocumentActivated:
    document_id: DocumentId
    workspace_reference: str
    lifecycle_state: DocumentLifecycleState = DocumentLifecycleState.DRAFT


@dataclass(frozen=True, slots=True)
class DocumentPromoted:
    document_id: DocumentId
    workspace_reference: str


@dataclass(frozen=True, slots=True)
class DocumentMarkedReady:
    document_id: DocumentId
    from_state: DocumentLifecycleState
    to_state: DocumentLifecycleState


@dataclass(frozen=True, slots=True)
class DocumentReturnedToDraft:
    document_id: DocumentId
    from_state: DocumentLifecycleState
    to_state: DocumentLifecycleState


@dataclass(frozen=True, slots=True)
class DocumentSigned:
    document_id: DocumentId
    from_state: DocumentLifecycleState
    to_state: DocumentLifecycleState


@dataclass(frozen=True, slots=True)
class DocumentRegistered:
    document_id: DocumentId
    from_state: DocumentLifecycleState
    to_state: DocumentLifecycleState
    registration_number: str | None = None


@dataclass(frozen=True, slots=True)
class DocumentCancelled:
    document_id: DocumentId
    void_kind: VoidKind
    reason_code: str | None = None
    reason_text: str | None = None


@dataclass(frozen=True, slots=True)
class DocumentAnnulled:
    document_id: DocumentId
    void_kind: VoidKind
    reason_code: str | None = None
    reason_text: str | None = None


@dataclass(frozen=True, slots=True)
class DocumentArchived:
    document_id: DocumentId
    from_archive_state: ArchiveState
    to_archive_state: ArchiveState


@dataclass(frozen=True, slots=True)
class DocumentRestored:
    document_id: DocumentId
    from_archive_state: ArchiveState
    to_archive_state: ArchiveState


DomainEvent = Union[
    DocumentActivated,
    DocumentPromoted,
    DocumentMarkedReady,
    DocumentReturnedToDraft,
    DocumentSigned,
    DocumentRegistered,
    DocumentCancelled,
    DocumentAnnulled,
    DocumentArchived,
    DocumentRestored,
]
