"""Unified Document Engine — shared runtime contracts (UDE-007).

Pure domain types only. No persistence, API, or specialization imports.
"""
from __future__ import annotations

from app.document_engine.contracts.party import PartyReference, PartyReferenceType
from app.document_engine.contracts.validation import (
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)
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
    "PartyReference",
    "PartyReferenceType",
    "StalenessState",
    "TextSourceType",
    "ValidationIssue",
    "ValidationResult",
    "ValidationSeverity",
    "VoidKind",
]
