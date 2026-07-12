"""UDE shared domain contracts."""
from __future__ import annotations

from app.document_engine.contracts.party import PartyReference, PartyReferenceType
from app.document_engine.contracts.validation import (
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)

__all__ = [
    "PartyReference",
    "PartyReferenceType",
    "ValidationIssue",
    "ValidationResult",
    "ValidationSeverity",
]
