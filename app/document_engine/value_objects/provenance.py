"""Text provenance value objects (UDE-002)."""
from __future__ import annotations

from enum import Enum


class TextSourceType(str, Enum):
    """Provenance discriminator for effective text selection."""

    GENERATED = "GENERATED"
    OVERRIDE = "OVERRIDE"
    SUBMITTED = "SUBMITTED"
    IMPORTED = "IMPORTED"
