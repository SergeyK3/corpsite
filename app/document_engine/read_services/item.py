"""Item read service (UDE-009)."""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Tuple

from app.document_engine.adapters.personnel.item import PersonnelItemAdapter
from app.document_engine.adapters.personnel.views import PersonnelItemReadView, PersonnelReadBundle
from app.document_engine.read_models.item import ItemReadModel


class ItemReadService:
    """Maps Personnel item adapter output → shared item read models."""

    @staticmethod
    def from_item_view(view: PersonnelItemReadView) -> ItemReadModel:
        return ItemReadModel(
            item_id=view.item_id,
            order_id=view.order_id,
            item_number=view.item_number,
            backend_item_type_code=view.backend_item_type_code,
            display_item_type_code=view.display_item_type_code,
            item_status=view.item_status,
            event_subject=view.event_subject,
            effective_date=view.effective_date,
            payload=view.payload,
            org_unit_id=view.org_unit_id,
            org_unit_name=view.org_unit_name,
        )

    @staticmethod
    def from_items(items: Iterable[Mapping[str, Any]]) -> Tuple[ItemReadModel, ...]:
        views = PersonnelItemAdapter.from_items(items)
        return tuple(ItemReadService.from_item_view(view) for view in views)

    @staticmethod
    def from_bundle(bundle: PersonnelReadBundle) -> Tuple[ItemReadModel, ...]:
        return tuple(ItemReadService.from_item_view(item) for item in bundle.items)
