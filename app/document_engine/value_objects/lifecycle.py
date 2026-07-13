"""Document lifecycle value objects (UDE-005)."""
from __future__ import annotations

from enum import Enum


class DocumentLifecycleState(str, Enum):
    """Ratified document lifecycle model (UDE-005, extended with PUBLISHED)."""

    DRAFT = "DRAFT"
    READY_FOR_SIGNATURE = "READY_FOR_SIGNATURE"
    SIGNED = "SIGNED"
    REGISTERED = "REGISTERED"
    PUBLISHED = "PUBLISHED"
    VOIDED = "VOIDED"


class ArchiveState(str, Enum):
    """Orthogonal archive flag — not a lifecycle enum member."""

    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class VoidKind(str, Enum):
    """Canonical void discriminator for terminal VOIDED state."""

    CANCEL = "CANCEL"
    ANNUL = "ANNUL"
