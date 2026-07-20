"""HR-facing recovery of applicant intake link paths."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.engine import Connection

from app.personnel_applications.infrastructure.repository import SqlAlchemyPersonnelApplicationRepository
from app.personnel_intake.domain.status import (
    INTAKE_LINK_STATUS_EXPIRED,
    INTAKE_LINK_STATUS_ISSUED,
    INTAKE_LINK_STATUS_OPENED,
    INTAKE_LINK_STATUS_REVOKED,
    INTAKE_LINK_STATUS_SUBMITTED,
)
from app.personnel_intake.infrastructure.repository import SqlAlchemyPersonnelIntakeRepository
from app.personnel_intake.infrastructure.token_encryption import decrypt_intake_url_path

HR_INTAKE_LINK_DISPLAY_NOT_ISSUED = "not_issued"
HR_INTAKE_LINK_DISPLAY_ACTIVE = "active"
HR_INTAKE_LINK_DISPLAY_SUBMITTED = "submitted"
HR_INTAKE_LINK_DISPLAY_REISSUE_REQUIRED = "reissue_required"
HR_INTAKE_LINK_DISPLAY_REVOKED = "revoked"
HR_INTAKE_LINK_DISPLAY_EXPIRED = "expired"

_RECOVERABLE_STATUSES = frozenset(
    {
        INTAKE_LINK_STATUS_ISSUED,
        INTAKE_LINK_STATUS_OPENED,
        INTAKE_LINK_STATUS_SUBMITTED,
    }
)


@dataclass(frozen=True, slots=True)
class HrIntakeLinkDisplay:
    application_id: int
    display_state: str
    link_id: int | None
    link_status: str | None
    intake_url_path: str | None
    expires_at: datetime | None


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _resolve_link_for_hr_display(repo: SqlAlchemyPersonnelIntakeRepository, application_id: int):
    active = repo.get_active_link_for_application(application_id)
    if active is not None:
        return active

    latest = repo.get_latest_link_for_application(application_id)
    if latest is None:
        return None
    if latest.status == INTAKE_LINK_STATUS_SUBMITTED:
        return latest
    if latest.status in {INTAKE_LINK_STATUS_REVOKED, INTAKE_LINK_STATUS_EXPIRED}:
        return latest
    return None


def _build_display(application_id: int, link) -> HrIntakeLinkDisplay:
    if link is None:
        return HrIntakeLinkDisplay(
            application_id=application_id,
            display_state=HR_INTAKE_LINK_DISPLAY_NOT_ISSUED,
            link_id=None,
            link_status=None,
            intake_url_path=None,
            expires_at=None,
        )

    status = str(link.status)
    now = _now_utc()
    if status in {INTAKE_LINK_STATUS_ISSUED, INTAKE_LINK_STATUS_OPENED} and link.expires_at <= now:
        return HrIntakeLinkDisplay(
            application_id=application_id,
            display_state=HR_INTAKE_LINK_DISPLAY_EXPIRED,
            link_id=link.link_id,
            link_status=INTAKE_LINK_STATUS_EXPIRED,
            intake_url_path=None,
            expires_at=link.expires_at,
        )
    if status == INTAKE_LINK_STATUS_REVOKED:
        return HrIntakeLinkDisplay(
            application_id=application_id,
            display_state=HR_INTAKE_LINK_DISPLAY_REVOKED,
            link_id=link.link_id,
            link_status=status,
            intake_url_path=None,
            expires_at=link.expires_at,
        )
    if status == INTAKE_LINK_STATUS_EXPIRED:
        return HrIntakeLinkDisplay(
            application_id=application_id,
            display_state=HR_INTAKE_LINK_DISPLAY_EXPIRED,
            link_id=link.link_id,
            link_status=status,
            intake_url_path=None,
            expires_at=link.expires_at,
        )

    if status not in _RECOVERABLE_STATUSES:
        return HrIntakeLinkDisplay(
            application_id=application_id,
            display_state=HR_INTAKE_LINK_DISPLAY_NOT_ISSUED,
            link_id=link.link_id,
            link_status=status,
            intake_url_path=None,
            expires_at=link.expires_at,
        )

    path = decrypt_intake_url_path(getattr(link, "token_ciphertext", None))
    if not path:
        return HrIntakeLinkDisplay(
            application_id=application_id,
            display_state=HR_INTAKE_LINK_DISPLAY_REISSUE_REQUIRED,
            link_id=link.link_id,
            link_status=status,
            intake_url_path=None,
            expires_at=link.expires_at,
        )

    display_state = (
        HR_INTAKE_LINK_DISPLAY_SUBMITTED
        if status == INTAKE_LINK_STATUS_SUBMITTED
        else HR_INTAKE_LINK_DISPLAY_ACTIVE
    )
    return HrIntakeLinkDisplay(
        application_id=application_id,
        display_state=display_state,
        link_id=link.link_id,
        link_status=status,
        intake_url_path=path,
        expires_at=link.expires_at,
    )


def get_hr_intake_link_display(conn: Connection, application_id: int) -> HrIntakeLinkDisplay:
    app_repo = SqlAlchemyPersonnelApplicationRepository(conn)
    app_repo.require_by_id(application_id)
    repo = SqlAlchemyPersonnelIntakeRepository(conn)
    link = _resolve_link_for_hr_display(repo, application_id)
    return _build_display(application_id, link)


def batch_hr_intake_link_displays(
    conn: Connection,
    application_ids: list[int],
) -> dict[int, HrIntakeLinkDisplay]:
    if not application_ids:
        return {}
    repo = SqlAlchemyPersonnelIntakeRepository(conn)
    return {
        int(app_id): _build_display(int(app_id), _resolve_link_for_hr_display(repo, int(app_id)))
        for app_id in application_ids
    }
