"""Write command models (UDE-012).

Immutable command intents — no side effects, no persistence.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class CreateDocumentCommand:
    """Intent to activate document from official draft — no persistence."""

    workspace_reference: str
    actor_user_id: int | None = None
    metadata: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class PromoteDraftCommand:
    """Intent to promote official draft to runtime aggregate."""

    workspace_reference: str
    actor_user_id: int | None = None


@dataclass(frozen=True, slots=True)
class MarkReadyCommand:
    """Intent to transition DRAFT → READY_FOR_SIGNATURE."""

    actor_user_id: int | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class ReturnToDraftCommand:
    """Intent to transition READY_FOR_SIGNATURE → DRAFT."""

    actor_user_id: int | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class SignDocumentCommand:
    """Intent to transition READY_FOR_SIGNATURE → SIGNED."""

    actor_user_id: int | None = None
    signed_at: str | None = None


@dataclass(frozen=True, slots=True)
class RegisterDocumentCommand:
    """Intent to transition SIGNED → REGISTERED — no number assigned here."""

    actor_user_id: int | None = None
    registration_number: str | None = None


@dataclass(frozen=True, slots=True)
class CancelDocumentCommand:
    """Intent to cancel from DRAFT or READY_FOR_SIGNATURE."""

    actor_user_id: int | None = None
    reason_code: str | None = None
    reason_text: str | None = None


@dataclass(frozen=True, slots=True)
class AnnulDocumentCommand:
    """Intent to annul from SIGNED or REGISTERED."""

    actor_user_id: int | None = None
    reason_code: str | None = None
    reason_text: str | None = None


@dataclass(frozen=True, slots=True)
class ArchiveDocumentCommand:
    """Intent to set archive_state ARCHIVED."""

    actor_user_id: int | None = None
    reason_code: str | None = None
    reason_text: str | None = None


@dataclass(frozen=True, slots=True)
class RestoreDocumentCommand:
    """Intent to restore archive_state ACTIVE."""

    actor_user_id: int | None = None
    reason: str | None = None
