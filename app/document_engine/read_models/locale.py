"""Localization runtime read models (UDE-009)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from app.document_engine.value_objects.localization import LocaleCode, StalenessState
from app.document_engine.value_objects.provenance import TextSourceType


@dataclass(frozen=True, slots=True)
class LocaleBlockReadModel:
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
class LocaleSnapshotReadModel:
    localized_text_id: int
    locale: LocaleCode
    title: str | None
    preamble: str | None
    body_text: str | None
    text_source_type: TextSourceType
    is_authoritative: bool
    render_version: int


@dataclass(frozen=True, slots=True)
class LocaleReadModel:
    blocks: Tuple[LocaleBlockReadModel, ...]
    snapshots: Tuple[LocaleSnapshotReadModel, ...]
