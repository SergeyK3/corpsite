"""Localization read service (UDE-009)."""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from app.document_engine.adapters.personnel.locale import PersonnelLocaleAdapter
from app.document_engine.adapters.personnel.views import (
    PersonnelLocaleBlockReadView,
    PersonnelLocaleSnapshotReadView,
    PersonnelReadBundle,
)
from app.document_engine.read_models.locale import (
    LocaleBlockReadModel,
    LocaleReadModel,
    LocaleSnapshotReadModel,
)


class LocalizationReadService:
    """Maps Personnel locale adapter output → shared locale read model."""

    @staticmethod
    def from_block_view(view: PersonnelLocaleBlockReadView) -> LocaleBlockReadModel:
        return LocaleBlockReadModel(
            block_id=view.block_id,
            scope=view.scope,
            order_item_id=view.order_item_id,
            locale=view.locale,
            block_type=view.block_type,
            generated_text=view.generated_text,
            override_text=view.override_text,
            effective_text=view.effective_text,
            text_source_type=view.text_source_type,
            staleness_state=view.staleness_state,
            source_fingerprint=view.source_fingerprint,
            generator_key=view.generator_key,
            generator_version=view.generator_version,
            review_status=view.review_status,
        )

    @staticmethod
    def from_snapshot_view(view: PersonnelLocaleSnapshotReadView) -> LocaleSnapshotReadModel:
        return LocaleSnapshotReadModel(
            localized_text_id=view.localized_text_id,
            locale=view.locale,
            title=view.title,
            preamble=view.preamble,
            body_text=view.body_text,
            text_source_type=view.text_source_type,
            is_authoritative=view.is_authoritative,
            render_version=view.render_version,
        )

    @staticmethod
    def from_editorial_state(editorial: Mapping[str, Any]) -> LocaleReadModel:
        blocks = PersonnelLocaleAdapter.from_editorial_state(editorial)
        return LocaleReadModel(
            blocks=tuple(LocalizationReadService.from_block_view(block) for block in blocks),
            snapshots=(),
        )

    @staticmethod
    def from_localized_texts(rows: Iterable[Mapping[str, Any]]) -> LocaleReadModel:
        snapshots = PersonnelLocaleAdapter.from_localized_texts(rows)
        return LocaleReadModel(
            blocks=(),
            snapshots=tuple(
                LocalizationReadService.from_snapshot_view(snapshot) for snapshot in snapshots
            ),
        )

    @staticmethod
    def from_bundle(bundle: PersonnelReadBundle) -> LocaleReadModel:
        return LocaleReadModel(
            blocks=tuple(
                LocalizationReadService.from_block_view(block)
                for block in bundle.locale_blocks
            ),
            snapshots=tuple(
                LocalizationReadService.from_snapshot_view(snapshot)
                for snapshot in bundle.locale_snapshots
            ),
        )
