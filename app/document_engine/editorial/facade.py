"""Document engine editorial facade — single public entry point (UDE-010)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Tuple

from app.document_engine.editorial.editorial_models import EditorialDocument, OfficialDraftSnapshot
from app.document_engine.editorial.editorial_service import EditorialService
from app.document_engine.editorial.localization_service import LocalizationService, LocalizationView
from app.document_engine.editorial.official_draft_builder import OfficialDraftBuilder
from app.document_engine.read_services.facade import (
    DocumentEngineReadFacade,
    DocumentEngineReadSnapshot,
)


@dataclass(frozen=True, slots=True)
class DocumentEngineEditorialSnapshot:
    editorial: EditorialDocument
    localization: Tuple[LocalizationView, ...] = field(default_factory=tuple)
    official_draft: OfficialDraftSnapshot | None = None


class DocumentEngineEditorialFacade:
    """Aggregates editorial runtime services behind a single entry point."""

    @staticmethod
    def from_read_snapshot(read_snapshot: DocumentEngineReadSnapshot) -> DocumentEngineEditorialSnapshot:
        editorial = EditorialService.from_snapshot(read_snapshot)
        localization = LocalizationService.from_locale_model(read_snapshot.locale)
        official_draft = OfficialDraftBuilder.from_snapshot(read_snapshot)
        return DocumentEngineEditorialSnapshot(
            editorial=editorial,
            localization=localization,
            official_draft=official_draft,
        )

    @staticmethod
    def from_detail(
        detail: Mapping[str, Any],
        *,
        supplement: Mapping[str, Any] | None = None,
        editorial: Mapping[str, Any] | None = None,
        audit_items: list[Mapping[str, Any]] | None = None,
    ) -> DocumentEngineEditorialSnapshot:
        read_snapshot = DocumentEngineReadFacade.from_detail(
            detail,
            supplement=supplement,
            editorial=editorial,
            audit_items=audit_items,
        )
        return DocumentEngineEditorialFacade.from_read_snapshot(read_snapshot)
