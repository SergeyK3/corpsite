"""Personnel item read adapter (UDE-008)."""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from app.document_engine.adapters.personnel._mapping import infer_display_item_type, payload_dict
from app.document_engine.adapters.personnel.party import PersonnelPartyAdapter
from app.document_engine.adapters.personnel.views import PersonnelItemReadView

SUPPORTED_BACKEND_ITEM_TYPES = frozenset(
    {
        "HIRE",
        "TRANSFER",
        "TERMINATION",
        "CONCURRENT_DUTY_START",
        "CONCURRENT_DUTY_END",
    }
)

SUPPORTED_DISPLAY_ITEM_TYPES = SUPPORTED_BACKEND_ITEM_TYPES | frozenset({"RATE_CHANGE"})


class PersonnelItemAdapter:
    """Maps PersonnelOrderItem dicts → shared item read views."""

    @staticmethod
    def from_item(item: Mapping[str, Any]) -> PersonnelItemReadView:
        payload = payload_dict(item.get("payload"))
        backend_type = str(item.get("item_type_code") or "").strip().upper()
        display_type = infer_display_item_type(backend_type, payload)
        return PersonnelItemReadView(
            item_id=int(item["item_id"]),
            order_id=int(item["order_id"]),
            item_number=int(item["item_number"]),
            backend_item_type_code=backend_type,
            display_item_type_code=display_type,
            item_status=str(item.get("item_status") or ""),
            event_subject=PersonnelPartyAdapter.from_item(item),
            effective_date=item.get("effective_date"),
            payload=payload,
            org_unit_id=(
                int(item["org_unit_id"]) if item.get("org_unit_id") is not None else None
            ),
            org_unit_name=item.get("org_unit_name"),
        )

    @staticmethod
    def from_items(items: Iterable[Mapping[str, Any]]) -> tuple[PersonnelItemReadView, ...]:
        return tuple(PersonnelItemAdapter.from_item(item) for item in items)
