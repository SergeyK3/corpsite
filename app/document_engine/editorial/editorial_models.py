"""Shared editorial runtime models (UDE-010).

Immutable runtime models — not ORM, not API DTOs, not persistence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Tuple

from app.document_engine.value_objects.identity import DocumentKind, DocumentSpecialization
from app.document_engine.value_objects.lifecycle import DocumentLifecycleState
from app.document_engine.value_objects.localization import LocaleCode, StalenessState
from app.document_engine.value_objects.provenance import TextSourceType


class ReviewState(str, Enum):
    """Editorial review state derived from adapter or fingerprint policy."""

    CURRENT = "CURRENT"
    STALE = "STALE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class EditorialFingerprint:
    """Deterministic runtime fingerprint for generated text change detection."""

    value: str
    generator_key: str | None = None
    generator_version: str | None = None
    source_fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class EditorialOverride:
    """Manual override layer — nullable per UDE-003."""

    override_text: str | None
    is_active: bool


@dataclass(frozen=True, slots=True)
class EditorialBlock:
    """Per locale × section/item editorial block."""

    block_id: int
    scope: str
    order_item_id: int | None
    locale: LocaleCode
    block_type: str
    generated_text: str | None
    override: EditorialOverride
    effective_text: str
    fingerprint: EditorialFingerprint
    review_state: ReviewState
    staleness_state: StalenessState
    text_source_type: TextSourceType


@dataclass(frozen=True, slots=True)
class EditorialLocale:
    """Locale-scoped editorial blocks and legacy snapshots."""

    locale: LocaleCode
    blocks: Tuple[EditorialBlock, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class EditorialSection:
    """Editorial section grouping blocks by scope and optional item."""

    section_key: str
    scope: str
    order_item_id: int | None
    blocks: Tuple[EditorialBlock, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class EditorialDocument:
    """Shared editorial document view — not a Document Aggregate."""

    document_kind: DocumentKind
    specialization: DocumentSpecialization
    lifecycle_state: DocumentLifecycleState
    legacy_status: str
    sections: Tuple[EditorialSection, ...] = field(default_factory=tuple)
    locales: Tuple[EditorialLocale, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class OfficialDraftLocaleBlock:
    """Frozen locale block in official draft snapshot."""

    locale: LocaleCode
    block_type: str
    scope: str
    order_item_id: int | None
    generated_text: str | None
    override_text: str | None
    effective_text: str
    review_state: ReviewState
    staleness_state: StalenessState
    fingerprint: EditorialFingerprint
    text_source_type: TextSourceType


@dataclass(frozen=True, slots=True)
class OfficialDraftSnapshot:
    """Promotion handoff snapshot — no DocumentId (UDE-003)."""

    document_kind: DocumentKind
    specialization: DocumentSpecialization
    workspace_reference: str
    order_type_code: str
    lifecycle_state: DocumentLifecycleState
    locale_blocks: Tuple[OfficialDraftLocaleBlock, ...] = field(default_factory=tuple)
    item_count: int = 0
    draft_metadata: Mapping[str, Any] = field(default_factory=dict)
