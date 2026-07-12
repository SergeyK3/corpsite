"""UDE shared value objects."""
from __future__ import annotations

from app.document_engine.value_objects.identity import (
    DocumentId,
    DocumentKind,
    DocumentSpecialization,
)
from app.document_engine.value_objects.lifecycle import (
    ArchiveState,
    DocumentLifecycleState,
    VoidKind,
)
from app.document_engine.value_objects.drafting import DraftingPath
from app.document_engine.value_objects.localization import LocaleCode, StalenessState
from app.document_engine.value_objects.provenance import TextSourceType

__all__ = [
    "ArchiveState",
    "DocumentId",
    "DocumentKind",
    "DocumentLifecycleState",
    "DocumentSpecialization",
    "DraftingPath",
    "LocaleCode",
    "StalenessState",
    "TextSourceType",
    "VoidKind",
]
