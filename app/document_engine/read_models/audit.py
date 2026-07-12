"""Audit runtime read models (UDE-009)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Tuple

from app.document_engine.value_objects.lifecycle import VoidKind


@dataclass(frozen=True, slots=True)
class AuditEventReadModel:
    event_id: int
    order_id: int
    action: str
    previous_status: str | None
    new_status: str | None
    previous_void_kind: VoidKind | None
    new_void_kind: VoidKind | None
    actor_user_id: int
    reason_code: str | None
    reason_text: str | None
    created_at: str
    metadata_json: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AuditReadModel:
    document_order_id: int
    events: Tuple[AuditEventReadModel, ...] = field(default_factory=tuple)
