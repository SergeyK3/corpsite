"""Editorial document service (UDE-010)."""
from __future__ import annotations

from typing import Tuple

from app.document_engine.editorial.editorial_models import EditorialDocument, EditorialSection
from app.document_engine.editorial.localization_service import LocalizationService
from app.document_engine.read_services.facade import DocumentEngineReadSnapshot


class EditorialService:
    """Builds EditorialDocument from shared read snapshot — no writes."""

    @staticmethod
    def _section_key(scope: str, order_item_id: int | None) -> str:
        if order_item_id is not None:
            return f"item:{order_item_id}"
        return f"scope:{scope}"

    @staticmethod
    def _sections_from_locales(
        locales: Tuple,
    ) -> Tuple[EditorialSection, ...]:
        section_map: dict[str, list] = {}
        for editorial_locale in locales:
            for block in editorial_locale.blocks:
                key = EditorialService._section_key(block.scope, block.order_item_id)
                section_map.setdefault(key, []).append(block)

        sections: list[EditorialSection] = []
        for key in sorted(section_map):
            blocks = tuple(section_map[key])
            first = blocks[0]
            sections.append(
                EditorialSection(
                    section_key=key,
                    scope=first.scope,
                    order_item_id=first.order_item_id,
                    blocks=blocks,
                )
            )
        return tuple(sections)

    @staticmethod
    def from_snapshot(snapshot: DocumentEngineReadSnapshot) -> EditorialDocument:
        locales = LocalizationService.editorial_locales_from_model(snapshot.locale)
        return EditorialDocument(
            document_kind=snapshot.document.document_kind,
            specialization=snapshot.document.specialization,
            lifecycle_state=snapshot.document.lifecycle_state,
            legacy_status=snapshot.document.legacy_status,
            sections=EditorialService._sections_from_locales(locales),
            locales=locales,
        )
