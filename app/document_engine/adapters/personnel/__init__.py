"""Personnel Orders read-only adapters (UDE-008)."""
from __future__ import annotations

from app.document_engine.adapters.personnel.read_adapter import PersonnelReadAdapter
from app.document_engine.adapters.personnel.views import PersonnelReadBundle

__all__ = [
    "PersonnelReadAdapter",
    "PersonnelReadBundle",
]
