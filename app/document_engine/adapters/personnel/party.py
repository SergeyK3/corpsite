"""Personnel party read adapter (UDE-008)."""
from __future__ import annotations

from typing import Any, Mapping

from app.document_engine.contracts.party import PartyReference, PartyReferenceType


class PersonnelPartyAdapter:
    """Maps PO employee references → PartyReference.

    UDE-006: employee_id on an order item is an Event Subject pointer,
    not a Responsible Party for document authority.
    """

    EVENT_SUBJECT_ROLE = "event_subject"

    @staticmethod
    def from_employee_id(
        employee_id: int | str | None,
        *,
        display_name: str | None = None,
        role: str = EVENT_SUBJECT_ROLE,
    ) -> PartyReference | None:
        if employee_id is None:
            return None
        numeric = int(employee_id)
        if numeric <= 0:
            return None
        metadata = {"po_role": role}
        return PartyReference(
            reference_type=PartyReferenceType.PERSON,
            reference=str(numeric),
            display_name=display_name,
            metadata=metadata,
        )

    @staticmethod
    def from_item(item: Mapping[str, Any]) -> PartyReference | None:
        return PersonnelPartyAdapter.from_employee_id(
            item.get("employee_id"),
            display_name=item.get("employee_name"),
            role=PersonnelPartyAdapter.EVENT_SUBJECT_ROLE,
        )

    @staticmethod
    def collect_event_subjects(items: list[Mapping[str, Any]]) -> tuple[PartyReference, ...]:
        seen: set[str] = set()
        result: list[PartyReference] = []
        for item in items:
            party = PersonnelPartyAdapter.from_item(item)
            if party is None or party.reference in seen:
                continue
            seen.add(party.reference)
            result.append(party)
        return tuple(result)
