"""Audit read service (UDE-009)."""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from app.document_engine.adapters.personnel.audit import PersonnelAuditAdapter
from app.document_engine.adapters.personnel.views import (
    PersonnelAuditEventReadView,
    PersonnelReadBundle,
)
from app.document_engine.read_models.audit import AuditEventReadModel, AuditReadModel


class AuditReadService:
    """Maps Personnel audit adapter output → shared audit read model (append-only)."""

    @staticmethod
    def from_event_view(view: PersonnelAuditEventReadView) -> AuditEventReadModel:
        return AuditEventReadModel(
            event_id=view.event_id,
            order_id=view.order_id,
            action=view.action,
            previous_status=view.previous_status,
            new_status=view.new_status,
            previous_void_kind=view.previous_void_kind,
            new_void_kind=view.new_void_kind,
            actor_user_id=view.actor_user_id,
            reason_code=view.reason_code,
            reason_text=view.reason_text,
            created_at=view.created_at,
            metadata_json=view.metadata_json,
        )

    @staticmethod
    def from_audit_rows(rows: Iterable[Mapping[str, Any]]) -> AuditReadModel:
        events = PersonnelAuditAdapter.from_audit_rows(rows)
        order_id = int(events[0].order_id) if events else 0
        return AuditReadModel(
            document_order_id=order_id,
            events=tuple(AuditReadService.from_event_view(event) for event in events),
        )

    @staticmethod
    def from_bundle(bundle: PersonnelReadBundle) -> AuditReadModel:
        order_id = int(bundle.document.document_id.value.split(":")[-1])
        return AuditReadModel(
            document_order_id=order_id,
            events=tuple(
                AuditReadService.from_event_view(event) for event in bundle.audit_events
            ),
        )
