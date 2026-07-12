"""Localization editorial service (UDE-010)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple

from app.document_engine.editorial.editorial_models import (
    EditorialBlock,
    EditorialLocale,
    EditorialOverride,
    ReviewState,
)
from app.document_engine.editorial.fingerprint_service import FingerprintService
from app.document_engine.editorial.override_resolver import OverrideResolver
from app.document_engine.editorial.review_policy import ReviewPolicy
from app.document_engine.read_models.locale import LocaleBlockReadModel, LocaleReadModel
from app.document_engine.value_objects.localization import LocaleCode, StalenessState


@dataclass(frozen=True, slots=True)
class LocalizationView:
    """Per-locale editorial localization breakdown."""

    locale: LocaleCode
    effective_blocks: Tuple[EditorialBlock, ...] = field(default_factory=tuple)
    generated_blocks: Tuple[EditorialBlock, ...] = field(default_factory=tuple)
    override_blocks: Tuple[EditorialBlock, ...] = field(default_factory=tuple)
    review_states: Tuple[ReviewState, ...] = field(default_factory=tuple)
    staleness_states: Tuple[StalenessState, ...] = field(default_factory=tuple)


class LocalizationService:
    """Builds localization views from LocaleReadModel — no text generation."""

    @staticmethod
    def block_from_read_model(block: LocaleBlockReadModel) -> EditorialBlock:
        fingerprint = FingerprintService.from_read_block(block)
        override = EditorialOverride(
            override_text=block.override_text,
            is_active=OverrideResolver.has_override(block.override_text),
        )
        effective = OverrideResolver.resolve_effective(
            generated_text=block.generated_text,
            override_text=block.override_text,
        )
        return EditorialBlock(
            block_id=block.block_id,
            scope=block.scope,
            order_item_id=block.order_item_id,
            locale=block.locale,
            block_type=block.block_type,
            generated_text=block.generated_text,
            override=override,
            effective_text=effective,
            fingerprint=fingerprint,
            review_state=ReviewPolicy.compute_for_block(block),
            staleness_state=block.staleness_state,
            text_source_type=block.text_source_type,
        )

    @staticmethod
    def locale_from_blocks(blocks: Tuple[EditorialBlock, ...], locale: LocaleCode) -> EditorialLocale:
        locale_blocks = tuple(block for block in blocks if block.locale == locale)
        return EditorialLocale(locale=locale, blocks=locale_blocks)

    @staticmethod
    def from_locale_model(locale_model: LocaleReadModel) -> Tuple[LocalizationView, ...]:
        editorial_blocks = tuple(
            LocalizationService.block_from_read_model(block)
            for block in locale_model.blocks
        )
        locales = sorted({block.locale for block in editorial_blocks}, key=lambda code: code.value)
        views: list[LocalizationView] = []
        for locale in locales:
            locale_blocks = tuple(block for block in editorial_blocks if block.locale == locale)
            generated = tuple(
                block for block in locale_blocks if not block.override.is_active
            )
            override = tuple(block for block in locale_blocks if block.override.is_active)
            views.append(
                LocalizationView(
                    locale=locale,
                    effective_blocks=locale_blocks,
                    generated_blocks=generated,
                    override_blocks=override,
                    review_states=tuple(block.review_state for block in locale_blocks),
                    staleness_states=tuple(block.staleness_state for block in locale_blocks),
                )
            )
        return tuple(views)

    @staticmethod
    def editorial_locales_from_model(locale_model: LocaleReadModel) -> Tuple[EditorialLocale, ...]:
        blocks = tuple(
            LocalizationService.block_from_read_model(block)
            for block in locale_model.blocks
        )
        locales = sorted({block.locale for block in blocks}, key=lambda code: code.value)
        return tuple(
            LocalizationService.locale_from_blocks(blocks, locale)
            for locale in locales
        )
