"""SQLAlchemy repository for personnel intake links and drafts."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection, RowMapping

from app.db.models.personnel_intake import PersonnelIntakeDraft, PersonnelIntakeLink
from app.personnel_intake.domain.errors import PersonnelIntakeNotFoundError
from app.personnel_intake.domain.models import (
    IntakeDraftSnapshot,
    IntakeLinkSnapshot,
    IntakeSummary,
    empty_intake_draft_payload,
)
from app.personnel_intake.domain.status import (
    INTAKE_DRAFT_STATUS_EDITABLE,
    INTAKE_LINK_ACTIVE_STATUSES,
    INTAKE_LINK_REVOCABLE_STATUSES,
    INTAKE_LINK_STATUS_EXPIRED,
    INTAKE_LINK_STATUS_ISSUED,
    INTAKE_LINK_STATUS_OPENED,
    INTAKE_LINK_STATUS_REVOKED,
    INTAKE_LINK_STATUS_SUBMITTED,
)

_LINK_COLUMNS = (
    PersonnelIntakeLink.link_id,
    PersonnelIntakeLink.application_id,
    PersonnelIntakeLink.status,
    PersonnelIntakeLink.issued_at,
    PersonnelIntakeLink.issued_by_user_id,
    PersonnelIntakeLink.expires_at,
    PersonnelIntakeLink.opened_at,
    PersonnelIntakeLink.submitted_at,
    PersonnelIntakeLink.revoked_at,
    PersonnelIntakeLink.revoked_by_user_id,
    PersonnelIntakeLink.superseded_by_link_id,
    PersonnelIntakeLink.token_ciphertext,
    PersonnelIntakeLink.created_at,
    PersonnelIntakeLink.updated_at,
)

_DRAFT_COLUMNS = (
    PersonnelIntakeDraft.draft_id,
    PersonnelIntakeDraft.application_id,
    PersonnelIntakeDraft.link_id,
    PersonnelIntakeDraft.status,
    PersonnelIntakeDraft.payload,
    PersonnelIntakeDraft.created_at,
    PersonnelIntakeDraft.updated_at,
    PersonnelIntakeDraft.submitted_at,
)


def _link_from_row(row: RowMapping | dict[str, Any]) -> IntakeLinkSnapshot:
    return IntakeLinkSnapshot(
        link_id=int(row["link_id"]),
        application_id=int(row["application_id"]),
        status=str(row["status"]),
        issued_at=row["issued_at"],
        issued_by_user_id=int(row["issued_by_user_id"]),
        expires_at=row["expires_at"],
        opened_at=row.get("opened_at"),
        submitted_at=row.get("submitted_at"),
        revoked_at=row.get("revoked_at"),
        revoked_by_user_id=(
            int(row["revoked_by_user_id"])
            if row.get("revoked_by_user_id") is not None
            else None
        ),
        superseded_by_link_id=(
            int(row["superseded_by_link_id"])
            if row.get("superseded_by_link_id") is not None
            else None
        ),
        token_ciphertext=(
            str(row["token_ciphertext"]).strip()
            if row.get("token_ciphertext") is not None
            else None
        ),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _draft_from_row(row: RowMapping | dict[str, Any]) -> IntakeDraftSnapshot:
    payload = row.get("payload") or {}
    if isinstance(payload, str):
        payload = json.loads(payload)
    return IntakeDraftSnapshot(
        draft_id=int(row["draft_id"]),
        application_id=int(row["application_id"]),
        link_id=int(row["link_id"]),
        status=str(row["status"]),
        payload=dict(payload),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        submitted_at=row.get("submitted_at"),
    )


class SqlAlchemyPersonnelIntakeRepository:
    """Persistence adapter — caller owns transaction and commit."""

    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def create_link(
        self,
        *,
        application_id: int,
        token_hash: str,
        token_ciphertext: str | None,
        issued_by_user_id: int,
        expires_at: datetime,
    ) -> IntakeLinkSnapshot:
        stmt = (
            pg_insert(PersonnelIntakeLink)
            .values(
                application_id=int(application_id),
                token_hash=token_hash,
                token_ciphertext=token_ciphertext,
                status=INTAKE_LINK_STATUS_ISSUED,
                issued_by_user_id=int(issued_by_user_id),
                expires_at=expires_at,
            )
            .returning(*_LINK_COLUMNS)
        )
        row = self._conn.execute(stmt).mappings().one()
        return _link_from_row(row)

    def get_link_by_token_hash(self, token_hash: str) -> IntakeLinkSnapshot | None:
        stmt = select(*_LINK_COLUMNS).where(PersonnelIntakeLink.token_hash == token_hash)
        row = self._conn.execute(stmt).mappings().one_or_none()
        if row is None:
            return None
        return _link_from_row(row)

    def get_link_by_id(self, link_id: int) -> IntakeLinkSnapshot | None:
        stmt = select(*_LINK_COLUMNS).where(PersonnelIntakeLink.link_id == int(link_id))
        row = self._conn.execute(stmt).mappings().one_or_none()
        if row is None:
            return None
        return _link_from_row(row)

    def get_active_link_for_application(self, application_id: int) -> IntakeLinkSnapshot | None:
        stmt = (
            select(*_LINK_COLUMNS)
            .where(
                PersonnelIntakeLink.application_id == int(application_id),
                PersonnelIntakeLink.status.in_(tuple(INTAKE_LINK_ACTIVE_STATUSES)),
            )
            .order_by(PersonnelIntakeLink.created_at.desc())
            .limit(1)
        )
        row = self._conn.execute(stmt).mappings().one_or_none()
        if row is None:
            return None
        return _link_from_row(row)

    def get_revocable_link_for_application(self, application_id: int) -> IntakeLinkSnapshot | None:
        stmt = (
            select(*_LINK_COLUMNS)
            .where(
                PersonnelIntakeLink.application_id == int(application_id),
                PersonnelIntakeLink.status.in_(tuple(INTAKE_LINK_REVOCABLE_STATUSES)),
            )
            .order_by(PersonnelIntakeLink.created_at.desc())
            .limit(1)
        )
        row = self._conn.execute(stmt).mappings().one_or_none()
        if row is None:
            return None
        return _link_from_row(row)

    def get_latest_link_for_application(self, application_id: int) -> IntakeLinkSnapshot | None:
        stmt = (
            select(*_LINK_COLUMNS)
            .where(PersonnelIntakeLink.application_id == int(application_id))
            .order_by(PersonnelIntakeLink.created_at.desc())
            .limit(1)
        )
        row = self._conn.execute(stmt).mappings().one_or_none()
        if row is None:
            return None
        return _link_from_row(row)

    def mark_link_opened(self, link_id: int, *, opened_at: datetime) -> IntakeLinkSnapshot:
        stmt = (
            update(PersonnelIntakeLink)
            .where(PersonnelIntakeLink.link_id == int(link_id))
            .values(
                status=INTAKE_LINK_STATUS_OPENED,
                opened_at=opened_at,
                updated_at=opened_at,
            )
            .returning(*_LINK_COLUMNS)
        )
        row = self._conn.execute(stmt).mappings().one()
        return _link_from_row(row)

    def mark_link_submitted(self, link_id: int, *, submitted_at: datetime) -> IntakeLinkSnapshot:
        stmt = (
            update(PersonnelIntakeLink)
            .where(PersonnelIntakeLink.link_id == int(link_id))
            .values(
                status=INTAKE_LINK_STATUS_SUBMITTED,
                submitted_at=submitted_at,
                updated_at=submitted_at,
            )
            .returning(*_LINK_COLUMNS)
        )
        row = self._conn.execute(stmt).mappings().one()
        return _link_from_row(row)

    def mark_link_revoked(
        self,
        link_id: int,
        *,
        revoked_at: datetime,
        revoked_by_user_id: int,
        superseded_by_link_id: int | None = None,
    ) -> IntakeLinkSnapshot:
        values: dict[str, Any] = {
            "status": INTAKE_LINK_STATUS_REVOKED,
            "revoked_at": revoked_at,
            "revoked_by_user_id": int(revoked_by_user_id),
            "token_ciphertext": None,
            "updated_at": revoked_at,
        }
        if superseded_by_link_id is not None:
            values["superseded_by_link_id"] = int(superseded_by_link_id)
        stmt = (
            update(PersonnelIntakeLink)
            .where(PersonnelIntakeLink.link_id == int(link_id))
            .values(**values)
            .returning(*_LINK_COLUMNS)
        )
        row = self._conn.execute(stmt).mappings().one()
        return _link_from_row(row)

    def mark_link_expired(self, link_id: int, *, expired_at: datetime) -> IntakeLinkSnapshot:
        stmt = (
            update(PersonnelIntakeLink)
            .where(PersonnelIntakeLink.link_id == int(link_id))
            .values(
                status=INTAKE_LINK_STATUS_EXPIRED,
                updated_at=expired_at,
            )
            .returning(*_LINK_COLUMNS)
        )
        row = self._conn.execute(stmt).mappings().one()
        return _link_from_row(row)

    def get_draft_by_application_id(self, application_id: int) -> IntakeDraftSnapshot | None:
        stmt = select(*_DRAFT_COLUMNS).where(
            PersonnelIntakeDraft.application_id == int(application_id)
        )
        row = self._conn.execute(stmt).mappings().one_or_none()
        if row is None:
            return None
        return _draft_from_row(row)

    def create_draft(
        self,
        *,
        application_id: int,
        link_id: int,
        payload: dict[str, Any] | None = None,
    ) -> IntakeDraftSnapshot:
        stmt = (
            pg_insert(PersonnelIntakeDraft)
            .values(
                application_id=int(application_id),
                link_id=int(link_id),
                payload=payload or empty_intake_draft_payload(),
            )
            .returning(*_DRAFT_COLUMNS)
        )
        row = self._conn.execute(stmt).mappings().one()
        return _draft_from_row(row)

    def update_draft_payload(
        self,
        draft_id: int,
        *,
        payload: dict[str, Any],
        updated_at: datetime,
    ) -> IntakeDraftSnapshot:
        stmt = (
            update(PersonnelIntakeDraft)
            .where(PersonnelIntakeDraft.draft_id == int(draft_id))
            .values(payload=payload, updated_at=updated_at)
            .returning(*_DRAFT_COLUMNS)
        )
        row = self._conn.execute(stmt).mappings().one()
        return _draft_from_row(row)

    def update_draft_payload_if_updated_at(
        self,
        draft_id: int,
        *,
        payload: dict[str, Any],
        updated_at: datetime,
        expected_updated_at: datetime,
    ) -> IntakeDraftSnapshot | None:
        stmt = (
            update(PersonnelIntakeDraft)
            .where(
                PersonnelIntakeDraft.draft_id == int(draft_id),
                PersonnelIntakeDraft.updated_at == expected_updated_at,
            )
            .values(payload=payload, updated_at=updated_at)
            .returning(*_DRAFT_COLUMNS)
        )
        row = self._conn.execute(stmt).mappings().one_or_none()
        if row is None:
            return None
        return _draft_from_row(row)

    def mark_draft_submitted(self, draft_id: int, *, submitted_at: datetime) -> IntakeDraftSnapshot:
        stmt = (
            update(PersonnelIntakeDraft)
            .where(PersonnelIntakeDraft.draft_id == int(draft_id))
            .values(
                status="submitted",
                submitted_at=submitted_at,
                updated_at=submitted_at,
            )
            .returning(*_DRAFT_COLUMNS)
        )
        row = self._conn.execute(stmt).mappings().one()
        return _draft_from_row(row)

    def mark_draft_editable_for_rework(self, draft_id: int, *, updated_at: datetime) -> IntakeDraftSnapshot:
        stmt = (
            update(PersonnelIntakeDraft)
            .where(PersonnelIntakeDraft.draft_id == int(draft_id))
            .values(
                status=INTAKE_DRAFT_STATUS_EDITABLE,
                updated_at=updated_at,
            )
            .returning(*_DRAFT_COLUMNS)
        )
        row = self._conn.execute(stmt).mappings().one()
        return _draft_from_row(row)

    def mark_link_reopened_for_rework(self, link_id: int, *, opened_at: datetime) -> IntakeLinkSnapshot:
        stmt = (
            update(PersonnelIntakeLink)
            .where(PersonnelIntakeLink.link_id == int(link_id))
            .values(
                status=INTAKE_LINK_STATUS_OPENED,
                opened_at=opened_at,
                updated_at=opened_at,
            )
            .returning(*_LINK_COLUMNS)
        )
        row = self._conn.execute(stmt).mappings().one()
        return _link_from_row(row)

    def rebind_draft_link(self, draft_id: int, *, link_id: int, updated_at: datetime) -> None:
        self._conn.execute(
            update(PersonnelIntakeDraft)
            .where(PersonnelIntakeDraft.draft_id == int(draft_id))
            .values(link_id=int(link_id), updated_at=updated_at)
        )

    def load_intake_summary(self, application_id: int) -> IntakeSummary:
        link = self.get_latest_link_for_application(application_id)
        draft = self.get_draft_by_application_id(application_id)
        return IntakeSummary(
            application_id=int(application_id),
            link_status=link.status if link else None,
            draft_status=draft.status if draft else None,
            link_id=link.link_id if link else None,
            issued_at=link.issued_at if link else None,
            expires_at=link.expires_at if link else None,
            opened_at=link.opened_at if link else None,
            submitted_at=(
                draft.submitted_at
                if draft and draft.submitted_at
                else (link.submitted_at if link else None)
            ),
            revoked_at=link.revoked_at if link else None,
            intake_url_path=None,
        )

    def load_intake_summaries(self, application_ids: list[int]) -> dict[int, IntakeSummary]:
        if not application_ids:
            return {}
        ids = [int(i) for i in application_ids]
        rows = self._conn.execute(
            text(
                """
                SELECT DISTINCT ON (l.application_id)
                    l.application_id,
                    l.link_id,
                    l.status AS link_status,
                    l.issued_at,
                    l.expires_at,
                    l.opened_at,
                    l.submitted_at AS link_submitted_at,
                    l.revoked_at,
                    d.status AS draft_status,
                    d.submitted_at AS draft_submitted_at
                FROM public.personnel_intake_links l
                LEFT JOIN public.personnel_intake_drafts d
                    ON d.application_id = l.application_id
                WHERE l.application_id = ANY(:ids)
                ORDER BY l.application_id, l.created_at DESC
                """
            ),
            {"ids": ids},
        ).mappings().all()
        result: dict[int, IntakeSummary] = {}
        for row in rows:
            app_id = int(row["application_id"])
            submitted_at = row.get("draft_submitted_at") or row.get("link_submitted_at")
            result[app_id] = IntakeSummary(
                application_id=app_id,
                link_status=str(row["link_status"]) if row.get("link_status") else None,
                draft_status=str(row["draft_status"]) if row.get("draft_status") else None,
                link_id=int(row["link_id"]) if row.get("link_id") is not None else None,
                issued_at=row.get("issued_at"),
                expires_at=row.get("expires_at"),
                opened_at=row.get("opened_at"),
                submitted_at=submitted_at,
                revoked_at=row.get("revoked_at"),
                intake_url_path=None,
            )
        return result
