"""Lifecycle audit persistence (WP-PPR-APPLICANT-004)."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.personnel_applications.domain.models import LifecycleAuditSnapshot


class SqlAlchemyPersonnelApplicationLifecycleRepository:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def append_audit(
        self,
        *,
        application_id: int,
        action: str,
        previous_status: str | None,
        new_status: str | None,
        comment: str | None = None,
        actor_user_id: int | None = None,
        metadata: dict[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> LifecycleAuditSnapshot:
        params: dict[str, Any] = {
            "application_id": int(application_id),
            "action": action,
            "previous_status": previous_status,
            "new_status": new_status,
            "comment": comment,
            "actor_user_id": int(actor_user_id) if actor_user_id is not None else None,
            "metadata": json.dumps(metadata) if metadata is not None else None,
        }
        created_clause = ""
        values_clause = ""
        if created_at is not None:
            params["created_at"] = created_at
            created_clause = ", created_at"
            values_clause = ", :created_at"

        row = self._conn.execute(
            text(
                f"""
                INSERT INTO public.personnel_application_lifecycle_audit (
                    application_id,
                    action,
                    previous_status,
                    new_status,
                    comment,
                    actor_user_id,
                    metadata
                    {created_clause}
                )
                VALUES (
                    :application_id,
                    :action,
                    :previous_status,
                    :new_status,
                    :comment,
                    :actor_user_id,
                    CAST(:metadata AS jsonb)
                    {values_clause}
                )
                RETURNING
                    audit_id,
                    application_id,
                    action,
                    previous_status,
                    new_status,
                    comment,
                    actor_user_id,
                    metadata,
                    created_at
                """
            ),
            params,
        ).mappings().one()
        return _row_to_snapshot(row)

    def list_audit(self, application_id: int, *, limit: int = 200) -> list[LifecycleAuditSnapshot]:
        rows = self._conn.execute(
            text(
                """
                SELECT
                    audit_id,
                    application_id,
                    action,
                    previous_status,
                    new_status,
                    comment,
                    actor_user_id,
                    metadata,
                    created_at
                FROM public.personnel_application_lifecycle_audit
                WHERE application_id = :application_id
                ORDER BY created_at DESC, audit_id DESC
                LIMIT :limit
                """
            ),
            {"application_id": int(application_id), "limit": int(limit)},
        ).mappings().all()
        return [_row_to_snapshot(row) for row in rows]


def _row_to_snapshot(row) -> LifecycleAuditSnapshot:
    metadata = row.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        metadata = dict(metadata)
    return LifecycleAuditSnapshot(
        audit_id=int(row["audit_id"]),
        application_id=int(row["application_id"]),
        action=str(row["action"]),
        previous_status=row.get("previous_status"),
        new_status=row.get("new_status"),
        comment=row.get("comment"),
        actor_user_id=(
            int(row["actor_user_id"]) if row.get("actor_user_id") is not None else None
        ),
        metadata=metadata,
        created_at=row["created_at"],
    )
