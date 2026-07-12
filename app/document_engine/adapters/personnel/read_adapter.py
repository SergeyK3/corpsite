"""Personnel read adapter facade — single public entry point (UDE-008)."""
from __future__ import annotations

from typing import Any, Mapping

from app.document_engine.adapters.personnel.audit import PersonnelAuditAdapter
from app.document_engine.adapters.personnel.document import PersonnelDocumentAdapter
from app.document_engine.adapters.personnel.item import PersonnelItemAdapter
from app.document_engine.adapters.personnel.locale import PersonnelLocaleAdapter
from app.document_engine.adapters.personnel.party import PersonnelPartyAdapter
from app.document_engine.adapters.personnel.print import PersonnelPrintAdapter
from app.document_engine.adapters.personnel.views import PersonnelReadBundle
from app.document_engine.adapters.personnel._supplement import fetch_order_supplement


class PersonnelReadAdapter:
    """Aggregates all Personnel Orders read-only adapters."""

    @staticmethod
    def from_detail(
        detail: Mapping[str, Any],
        *,
        supplement: Mapping[str, Any] | None = None,
        editorial: Mapping[str, Any] | None = None,
        audit_items: list[Mapping[str, Any]] | None = None,
    ) -> PersonnelReadBundle:
        order = detail.get("order") or {}
        items = list(detail.get("items") or [])
        localized_texts = list(detail.get("localized_texts") or [])
        prints = list(detail.get("prints") or [])

        document = PersonnelDocumentAdapter.from_header(order, supplement=supplement)
        item_views = PersonnelItemAdapter.from_items(items)
        locale_blocks = (
            PersonnelLocaleAdapter.from_editorial_state(editorial)
            if editorial is not None
            else ()
        )
        locale_snapshots = PersonnelLocaleAdapter.from_localized_texts(localized_texts)
        audit_events = (
            PersonnelAuditAdapter.from_audit_rows(audit_items)
            if audit_items is not None
            else ()
        )
        print_view = PersonnelPrintAdapter.from_header_and_prints(order, prints)
        event_subjects = PersonnelPartyAdapter.collect_event_subjects(items)

        return PersonnelReadBundle(
            document=document,
            items=item_views,
            locale_blocks=locale_blocks,
            locale_snapshots=locale_snapshots,
            audit_events=audit_events,
            print_view=print_view,
            event_subjects=event_subjects,
        )

    @staticmethod
    def from_order_id(
        order_id: int,
        *,
        include_editorial: bool = True,
        include_audit: bool = True,
        audit_limit: int = 100,
    ) -> PersonnelReadBundle:
        from app.services.personnel_order_lifecycle_audit_service import (
            list_personnel_order_lifecycle_audit,
        )
        from app.services.personnel_orders_editorial.service import get_editorial_state
        from app.services.personnel_orders_query_service import get_personnel_order

        detail = get_personnel_order(int(order_id))
        supplement = fetch_order_supplement(int(order_id))
        editorial = get_editorial_state(int(order_id)) if include_editorial else None
        audit_items = None
        if include_audit:
            audit_items = list_personnel_order_lifecycle_audit(
                int(order_id),
                limit=audit_limit,
                offset=0,
            )["items"]
        return PersonnelReadAdapter.from_detail(
            detail,
            supplement=supplement,
            editorial=editorial,
            audit_items=audit_items,
        )
