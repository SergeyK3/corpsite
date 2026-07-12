"""Drafting path value objects (UDE-007 extension for OO-IMP-001)."""
from __future__ import annotations

from enum import Enum


class DraftingPath(str, Enum):
    """How a document draft enters the editorial pipeline."""

    SUBMITTED_TEXT = "SUBMITTED_TEXT"
    OPERATOR_COMPOSED = "OPERATOR_COMPOSED"
    IMPORTED = "IMPORTED"
