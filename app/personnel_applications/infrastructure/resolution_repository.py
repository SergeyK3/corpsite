"""Resolution audit persistence (WP-PPR-APPLICANT-002)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.personnel_applications.domain.models import ResolutionAuditSnapshot


class SqlAlchemyPersonnelApplicationResolutionRepository:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def append_audit(
        self,
        *,
        application_id: int,
        action: str,
        previous_application_status: str | None,
        new_application_status: str,
        previous_resolution_status: str | None,
        new_resolution_status: str | None,
        comment: str | None,
        actor_user_id: int,
        created_at: datetime,
    ) -> ResolutionAuditSnapshot:
        row = self._conn.execute(
            text(
                """
                INSERT INTO public.personnel_application_resolution_audit (
                    application_id,
                    action,
                    previous_application_status,
                    new_application_status,
                    previous_resolution_status,
                    new_resolution_status,
                    comment,
                    actor_user_id,
                    created_at
                )
                VALUES (
                    :application_id,
                    :action,
                    :previous_application_status,
                    :new_application_status,
                    :previous_resolution_status,
                    :new_resolution_status,
                    :comment,
                    :actor_user_id,
                    :created_at
                )
                RETURNING
                    audit_id,
                    application_id,
                    action,
                    previous_application_status,
                    new_application_status,
                    previous_resolution_status,
                    new_resolution_status,
                    comment,
                    actor_user_id,
                    created_at
                """
            ),
            {
                "application_id": int(application_id),
                "action": action,
                "previous_application_status": previous_application_status,
                "new_application_status": new_application_status,
                "previous_resolution_status": previous_resolution_status,
                "new_resolution_status": new_resolution_status,
                "comment": comment,
                "actor_user_id": int(actor_user_id),
                "created_at": created_at,
            },
        ).mappings().one()
        return ResolutionAuditSnapshot(
            audit_id=int(row["audit_id"]),
            application_id=int(row["application_id"]),
            action=str(row["action"]),
            previous_application_status=row.get("previous_application_status"),
            new_application_status=str(row["new_application_status"]),
            previous_resolution_status=row.get("previous_resolution_status"),
            new_resolution_status=row.get("new_resolution_status"),
            comment=row.get("comment"),
            actor_user_id=int(row["actor_user_id"]),
            created_at=row["created_at"],
        )

    def list_audit(self, application_id: int, *, limit: int = 100) -> list[ResolutionAuditSnapshot]:
        rows = self._conn.execute(
            text(
                """
                SELECT
                    audit_id,
                    application_id,
                    action,
                    previous_application_status,
                    new_application_status,
                    previous_resolution_status,
                    new_resolution_status,
                    comment,
                    actor_user_id,
                    created_at
                FROM public.personnel_application_resolution_audit
                WHERE application_id = :application_id
                ORDER BY created_at DESC, audit_id DESC
                LIMIT :limit
                """
            ),
            {"application_id": int(application_id), "limit": int(limit)},
        ).mappings().all()
        return [
            ResolutionAuditSnapshot(
                audit_id=int(row["audit_id"]),
                application_id=int(row["application_id"]),
                action=str(row["action"]),
                previous_application_status=row.get("previous_application_status"),
                new_application_status=str(row["new_application_status"]),
                previous_resolution_status=row.get("previous_resolution_status"),
                new_resolution_status=row.get("new_resolution_status"),
                comment=row.get("comment"),
                actor_user_id=int(row["actor_user_id"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]
