"""Party reference contracts (UDE-001)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


class PartyReferenceType(str, Enum):
    """Generic party discriminator for adapter mapping."""

    PERSON = "PERSON"
    POSITION_ROLE = "POSITION_ROLE"
    ORG_UNIT = "ORG_UNIT"
    COMMISSION = "COMMISSION"
    WORKING_GROUP = "WORKING_GROUP"
    EXTERNAL_PARTY = "EXTERNAL_PARTY"


@dataclass(frozen=True, slots=True)
class PartyReference:
    """Minimal generic party pointer — not a persistence entity."""

    reference_type: PartyReferenceType
    reference: str
    display_name: str | None = None
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        normalized_type = self.reference_type
        if not isinstance(normalized_type, PartyReferenceType):
            normalized_type = PartyReferenceType(str(normalized_type).strip().upper())
            object.__setattr__(self, "reference_type", normalized_type)

        normalized_ref = str(self.reference or "").strip()
        if not normalized_ref:
            raise ValueError("PartyReference.reference must be non-empty")
        object.__setattr__(self, "reference", normalized_ref)

        if self.metadata is not None:
            object.__setattr__(self, "metadata", dict(self.metadata))
