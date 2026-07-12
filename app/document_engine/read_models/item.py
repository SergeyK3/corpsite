"""Item runtime read model (UDE-009)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app.document_engine.contracts.party import PartyReference


@dataclass(frozen=True, slots=True)
class ItemReadModel:
    item_id: int
    order_id: int
    item_number: int
    backend_item_type_code: str
    display_item_type_code: str
    item_status: str
    event_subject: PartyReference | None
    effective_date: str | None
    payload: Mapping[str, Any]
    org_unit_id: int | None
    org_unit_name: str | None
