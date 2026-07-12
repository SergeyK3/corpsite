"""Personnel lifecycle audit read adapter (UDE-008)."""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from app.document_engine.adapters.personnel._mapping import optional_str, parse_void_kind
from app.document_engine.adapters.personnel.views import PersonnelAuditEventReadView


class PersonnelAuditAdapter:
    """Read-only mapping for append-only lifecycle audit rows."""

    @staticmethod
    def from_audit_row(row: Mapping[str, Any]) -> PersonnelAuditEventReadView:
        metadata = row.get("metadata_json")
        if not isinstance(metadata, dict):
            metadata = {}
        return PersonnelAuditEventReadView(
            event_id=int(row["id"]),
            order_id=int(row["order_id"]),
            action=str(row.get("action") or ""),
            previous_status=optional_str(row.get("previous_status")),
            new_status=optional_str(row.get("new_status")),
            previous_void_kind=parse_void_kind(row.get("previous_void_kind")),
            new_void_kind=parse_void_kind(row.get("new_void_kind")),
            actor_user_id=int(row["actor_user_id"]),
            reason_code=optional_str(row.get("reason_code")),
            reason_text=optional_str(row.get("reason_text")),
            created_at=str(row.get("created_at") or ""),
            metadata_json=dict(metadata),
        )

    @staticmethod
    def from_audit_rows(
        rows: Iterable[Mapping[str, Any]],
    ) -> tuple[PersonnelAuditEventReadView, ...]:
        return tuple(PersonnelAuditAdapter.from_audit_row(row) for row in rows)
