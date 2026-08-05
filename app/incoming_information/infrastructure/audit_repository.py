"""Incoming document audit persistence."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.incoming_information.domain.status import AUDIT_ACTION_CREATED


class SqlAlchemyIncomingDocumentAuditRepository:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def append(
        self,
        *,
        incoming_document_id: int,
        action: str,
        actor_user_id: int | None,
        field_name: str | None = None,
        old_value: str | None = None,
        new_value: str | None = None,
        comment: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        row = self._conn.execute(
            text(
                """
                INSERT INTO public.incoming_document_audit (
                    incoming_document_id,
                    action,
                    field_name,
                    old_value,
                    new_value,
                    actor_user_id,
                    comment,
                    metadata
                )
                VALUES (
                    :incoming_document_id,
                    :action,
                    :field_name,
                    :old_value,
                    :new_value,
                    :actor_user_id,
                    :comment,
                    CAST(:metadata AS jsonb)
                )
                RETURNING audit_id
                """
            ),
            {
                "incoming_document_id": int(incoming_document_id),
                "action": action,
                "field_name": field_name,
                "old_value": old_value,
                "new_value": new_value,
                "actor_user_id": int(actor_user_id) if actor_user_id is not None else None,
                "comment": comment,
                "metadata": json.dumps(metadata) if metadata is not None else None,
            },
        ).one()
        return int(row[0])

    def append_created(
        self,
        *,
        incoming_document_id: int,
        actor_user_id: int,
        registration_number: str,
    ) -> int:
        return self.append(
            incoming_document_id=incoming_document_id,
            action=AUDIT_ACTION_CREATED,
            actor_user_id=actor_user_id,
            new_value=registration_number,
            metadata={"registration_number": registration_number},
        )

    def append_operation(
        self,
        *,
        incoming_document_id: int,
        action: str,
        actor_user_id: int,
        old_status_code: str,
        new_status_code: str,
        version_before: int,
        version_after: int,
        comment: str | None = None,
        field_changes: dict[str, Any] | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> int:
        metadata: dict[str, Any] = {
            "operation": action,
            "old_status_code": old_status_code,
            "new_status_code": new_status_code,
            "version_before": version_before,
            "version_after": version_after,
        }
        if field_changes:
            metadata["field_changes"] = field_changes
        if extra_metadata:
            metadata.update(extra_metadata)
        return self.append(
            incoming_document_id=incoming_document_id,
            action=action,
            actor_user_id=actor_user_id,
            field_name="status_code",
            old_value=old_status_code,
            new_value=new_status_code,
            comment=comment,
            metadata=metadata,
        )

    def list_for_document(self, incoming_document_id: int) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            text(
                """
                SELECT
                    audit_id,
                    incoming_document_id,
                    action,
                    field_name,
                    old_value,
                    new_value,
                    actor_user_id,
                    comment,
                    metadata,
                    created_at
                FROM public.incoming_document_audit
                WHERE incoming_document_id = :incoming_document_id
                ORDER BY created_at ASC, audit_id ASC
                """
            ),
            {"incoming_document_id": int(incoming_document_id)},
        ).mappings().all()
        return [dict(row) for row in rows]
