"""Document identity value objects (UDE-001)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DocumentKind(str, Enum):
    """Classification selecting document specialization."""

    PERSONNEL_ORDER = "PERSONNEL_ORDER"
    OPERATIONAL_ORDER = "OPERATIONAL_ORDER"


class DocumentSpecialization(str, Enum):
    """Runtime specialization binding for a document kind."""

    PERSONNEL = "PERSONNEL"
    OPERATIONAL = "OPERATIONAL"


@dataclass(frozen=True, slots=True)
class DocumentId:
    """Opaque document identity reference."""

    value: str

    def __post_init__(self) -> None:
        normalized = str(self.value or "").strip()
        if not normalized:
            raise ValueError("DocumentId must be non-empty")
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value
