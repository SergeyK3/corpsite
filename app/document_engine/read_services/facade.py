"""Document engine read facade — single public entry point (UDE-009)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Tuple

from app.document_engine.adapters.personnel.read_adapter import PersonnelReadAdapter
from app.document_engine.adapters.personnel.views import PersonnelReadBundle
from app.document_engine.contracts.party import PartyReference
from app.document_engine.read_models.audit import AuditReadModel
from app.document_engine.read_models.document import DocumentReadModel
from app.document_engine.read_models.item import ItemReadModel
from app.document_engine.read_models.lifecycle import LifecycleReadModel
from app.document_engine.read_models.locale import LocaleReadModel
from app.document_engine.read_models.print import PrintReadModel
from app.document_engine.read_services.audit import AuditReadService
from app.document_engine.read_services.document import DocumentReadService
from app.document_engine.read_services.item import ItemReadService
from app.document_engine.read_services.lifecycle import LifecycleReadService
from app.document_engine.read_services.localization import LocalizationReadService
from app.document_engine.read_services.print import PrintReadService


@dataclass(frozen=True, slots=True)
class DocumentEngineReadSnapshot:
    document: DocumentReadModel
    lifecycle: LifecycleReadModel
    locale: LocaleReadModel
    items: Tuple[ItemReadModel, ...] = field(default_factory=tuple)
    audit: AuditReadModel | None = None
    print_view: PrintReadModel | None = None
    event_subjects: Tuple[PartyReference, ...] = field(default_factory=tuple)


class DocumentEngineReadFacade:
    """Aggregates all shared read services behind a single runtime entry point."""

    @staticmethod
    def from_bundle(bundle: PersonnelReadBundle) -> DocumentEngineReadSnapshot:
        return DocumentEngineReadSnapshot(
            document=DocumentReadService.from_bundle(bundle),
            lifecycle=LifecycleReadService.from_bundle(bundle),
            locale=LocalizationReadService.from_bundle(bundle),
            items=ItemReadService.from_bundle(bundle),
            audit=AuditReadService.from_bundle(bundle) if bundle.audit_events else None,
            print_view=PrintReadService.from_bundle(bundle),
            event_subjects=bundle.event_subjects,
        )

    @staticmethod
    def from_detail(
        detail: Mapping[str, Any],
        *,
        supplement: Mapping[str, Any] | None = None,
        editorial: Mapping[str, Any] | None = None,
        audit_items: list[Mapping[str, Any]] | None = None,
    ) -> DocumentEngineReadSnapshot:
        bundle = PersonnelReadAdapter.from_detail(
            detail,
            supplement=supplement,
            editorial=editorial,
            audit_items=audit_items,
        )
        return DocumentEngineReadFacade.from_bundle(bundle)
