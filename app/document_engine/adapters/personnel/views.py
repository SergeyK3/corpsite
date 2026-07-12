"""Read-only adapter view shapes (UDE-008).

Temporary adapter DTOs — not full Document aggregate runtime.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Tuple

from app.document_engine.contracts.party import PartyReference
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
from app.document_engine.value_objects.localization import LocaleCode, StalenessState
from app.document_engine.value_objects.provenance import TextSourceType


@dataclass(frozen=True, slots=True)
class PersonnelDocumentMetadataView:
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
class PersonnelDocumentReadView:
    document_id: DocumentId
    document_kind: DocumentKind
    specialization: DocumentSpecialization
    lifecycle_state: DocumentLifecycleState
    archive_state: ArchiveState
    void_kind: VoidKind | None
    metadata: PersonnelDocumentMetadataView
    legacy_status: str
    is_archived: bool


@dataclass(frozen=True, slots=True)
class PersonnelLocaleBlockReadView:
    block_id: int
    scope: str
    order_item_id: int | None
    locale: LocaleCode
    block_type: str
    generated_text: str | None
    override_text: str | None
    effective_text: str
    text_source_type: TextSourceType
    staleness_state: StalenessState
    source_fingerprint: str | None
    generator_key: str | None
    generator_version: str | None
    review_status: str


@dataclass(frozen=True, slots=True)
class PersonnelLocaleSnapshotReadView:
    localized_text_id: int
    locale: LocaleCode
    title: str | None
    preamble: str | None
    body_text: str | None
    text_source_type: TextSourceType
    is_authoritative: bool
    render_version: int


@dataclass(frozen=True, slots=True)
class PersonnelItemReadView:
    item_id: int
    order_id: int
    item_number: int
    backend_item_type_code: str
    display_item_type_code: str
    item_status: str
    event_subject: PartyReference | None
    effective_date: str | None
    payload: Mapping[str, Any]
    org_unit_id: int | None
    org_unit_name: str | None


@dataclass(frozen=True, slots=True)
class PersonnelAuditEventReadView:
    event_id: int
    order_id: int
    action: str
    previous_status: str | None
    new_status: str | None
    previous_void_kind: VoidKind | None
    new_void_kind: VoidKind | None
    actor_user_id: int
    reason_code: str | None
    reason_text: str | None
    created_at: str
    metadata_json: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PersonnelPrintRecordReadView:
    print_id: int
    order_id: int
    locale: LocaleCode
    format: str
    file_path: str | None
    file_url: str | None
    is_signed_copy: bool
    render_version: int
    generated_at: str | None


@dataclass(frozen=True, slots=True)
class PersonnelPrintReadView:
    order_id: int
    lifecycle_state: DocumentLifecycleState
    archive_state: ArchiveState
    status_mark: str
    printable: bool
    records: Tuple[PersonnelPrintRecordReadView, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class PersonnelReadBundle:
    document: PersonnelDocumentReadView
    items: Tuple[PersonnelItemReadView, ...] = field(default_factory=tuple)
    locale_blocks: Tuple[PersonnelLocaleBlockReadView, ...] = field(default_factory=tuple)
    locale_snapshots: Tuple[PersonnelLocaleSnapshotReadView, ...] = field(default_factory=tuple)
    audit_events: Tuple[PersonnelAuditEventReadView, ...] = field(default_factory=tuple)
    print_view: PersonnelPrintReadView | None = None
    event_subjects: Tuple[PartyReference, ...] = field(default_factory=tuple)
