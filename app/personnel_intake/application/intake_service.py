"""Personnel Intake link and draft application services."""
from __future__ import annotations

import hashlib
import os
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.engine import Connection

from app.personnel_applications.domain.errors import PersonnelApplicationNotFoundError
from app.personnel_applications.domain.status import (
    APPLICATION_STATUS_INTAKE_PENDING,
    APPLICATION_STATUS_INTAKE_SUBMITTED,
    APPLICATION_STATUS_REGISTERED,
)
from app.personnel_applications.infrastructure.repository import SqlAlchemyPersonnelApplicationRepository
from app.personnel_intake.domain.applicant_reedit import (
    can_applicant_reedit_submitted_intake,
    should_reopen_submitted_intake_for_applicant_edit,
)
from app.personnel_intake.domain.date_validation import collect_intake_date_validation_errors
from app.personnel_intake.domain.education_type import (
    INTAKE_EDUCATION_TYPES,
    intake_education_duplicate_fingerprint,
    normalize_intake_education_type,
)
from app.personnel_intake.domain.errors import (
    PersonnelIntakeConflictError,
    PersonnelIntakeNotFoundError,
    PersonnelIntakeTokenError,
    PersonnelIntakeValidationError,
)
from app.personnel_intake.domain.models import (
    IntakeDraftSnapshot,
    IntakeLinkSnapshot,
    IntakeSummary,
    empty_intake_draft_payload,
)
from app.personnel_intake.domain.prefill import build_initial_intake_draft_payload
from app.personnel_intake.domain.status import (
    INTAKE_DRAFT_STATUS_EDITABLE,
    INTAKE_DRAFT_STATUS_SUBMITTED,
    INTAKE_LINK_STATUS_EXPIRED,
    INTAKE_LINK_STATUS_ISSUED,
    INTAKE_LINK_STATUS_OPENED,
    INTAKE_LINK_STATUS_REVOKED,
    INTAKE_LINK_STATUS_SUBMITTED,
    is_intake_draft_editable,
    is_intake_link_usable,
)
from app.personnel_intake.infrastructure.repository import SqlAlchemyPersonnelIntakeRepository
from app.personnel_intake.infrastructure.review_repository import SqlAlchemyPersonnelIntakeReviewRepository
from app.personnel_intake.infrastructure.token_encryption import encrypt_intake_raw_token

DEFAULT_INTAKE_LINK_TTL_DAYS = 14
INTAKE_URL_PATH_PREFIX = "/intake/"


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _generate_raw_token() -> str:
    return secrets.token_urlsafe(32)


def _intake_link_ttl_days() -> int:
    raw = (os.getenv("PERSONNEL_INTAKE_LINK_TTL_DAYS") or "").strip()
    if not raw:
        return DEFAULT_INTAKE_LINK_TTL_DAYS
    try:
        days = int(raw)
    except ValueError:
        return DEFAULT_INTAKE_LINK_TTL_DAYS
    return max(1, min(days, 90))


def _intake_url_path(raw_token: str) -> str:
    return f"{INTAKE_URL_PATH_PREFIX}{raw_token}"


def _ensure_not_expired(link: IntakeLinkSnapshot, *, now: datetime, repo: SqlAlchemyPersonnelIntakeRepository) -> IntakeLinkSnapshot:
    if link.status in {INTAKE_LINK_STATUS_EXPIRED, INTAKE_LINK_STATUS_REVOKED, INTAKE_LINK_STATUS_SUBMITTED}:
        return link
    if link.expires_at <= now:
        return repo.mark_link_expired(link.link_id, expired_at=now)
    return link


@dataclass(frozen=True, slots=True)
class IssueIntakeLinkResult:
    application_id: int
    link_id: int
    raw_token: str
    intake_url_path: str
    expires_at: datetime
    status: str
    reissued: bool


@dataclass(frozen=True, slots=True)
class OpenIntakeSessionResult:
    application_id: int
    link: IntakeLinkSnapshot
    draft: IntakeDraftSnapshot
    read_only: bool


@dataclass(frozen=True, slots=True)
class AutosaveIntakeDraftResult:
    draft: IntakeDraftSnapshot
    saved_at: datetime


@dataclass(frozen=True, slots=True)
class SubmitIntakeDraftResult:
    application_id: int
    link: IntakeLinkSnapshot
    draft: IntakeDraftSnapshot
    submitted_at: datetime


def _require_application(conn: Connection, application_id: int):
    app_repo = SqlAlchemyPersonnelApplicationRepository(conn)
    return app_repo.require_by_id(application_id)


def _transition_application_status(
    conn: Connection,
    *,
    application_id: int,
    new_status: str,
    now: datetime,
) -> None:
    conn.execute(
        __import__("sqlalchemy").text(
            """
            UPDATE public.personnel_applications
            SET status = :status, updated_at = :now
            WHERE application_id = :application_id
            """
        ),
        {
            "status": new_status,
            "now": now,
            "application_id": int(application_id),
        },
    )


def issue_intake_link(
    conn: Connection,
    *,
    application_id: int,
    issued_by_user_id: int,
    reissue: bool = False,
) -> IssueIntakeLinkResult:
    """Issue a new protected intake link for an application."""
    _require_application(conn, application_id)
    repo = SqlAlchemyPersonnelIntakeRepository(conn)
    now = _now_utc()
    expires_at = now + timedelta(days=_intake_link_ttl_days())

    active = repo.get_active_link_for_application(application_id)
    if active is not None and not reissue:
        raise PersonnelIntakeConflictError(
            "Active intake link already exists for this application.",
            code="ACTIVE_INTAKE_LINK_EXISTS",
        )

    old_active_link_id: int | None = None
    if active is not None and reissue:
        old_active_link_id = active.link_id
        repo.mark_link_revoked(
            active.link_id,
            revoked_at=now,
            revoked_by_user_id=issued_by_user_id,
        )

    raw_token = _generate_raw_token()
    link = repo.create_link(
        application_id=application_id,
        token_hash=_hash_token(raw_token),
        token_ciphertext=encrypt_intake_raw_token(raw_token),
        issued_by_user_id=issued_by_user_id,
        expires_at=expires_at,
    )

    if old_active_link_id is not None:
        conn.execute(
            __import__("sqlalchemy").text(
                """
                UPDATE public.personnel_intake_links
                SET superseded_by_link_id = :new_link_id, updated_at = :now
                WHERE link_id = :old_link_id
                """
            ),
            {"new_link_id": link.link_id, "now": now, "old_link_id": old_active_link_id},
        )

    draft = repo.get_draft_by_application_id(application_id)
    if draft is None:
        repo.create_draft(
            application_id=application_id,
            link_id=link.link_id,
            payload=build_initial_intake_draft_payload(conn, application_id),
        )
    elif draft.status != INTAKE_DRAFT_STATUS_SUBMITTED:
        repo.rebind_draft_link(draft.draft_id, link_id=link.link_id, updated_at=now)

    app = _require_application(conn, application_id)
    if app.status in {APPLICATION_STATUS_REGISTERED, APPLICATION_STATUS_INTAKE_PENDING}:
        _transition_application_status(
            conn,
            application_id=application_id,
            new_status=APPLICATION_STATUS_INTAKE_PENDING,
            now=now,
        )

    return IssueIntakeLinkResult(
        application_id=application_id,
        link_id=link.link_id,
        raw_token=raw_token,
        intake_url_path=_intake_url_path(raw_token),
        expires_at=expires_at,
        status=link.status,
        reissued=old_active_link_id is not None,
    )


def revoke_intake_link(
    conn: Connection,
    *,
    application_id: int,
    revoked_by_user_id: int,
) -> IntakeLinkSnapshot:
    """Revoke the active intake link for an application."""
    _require_application(conn, application_id)
    repo = SqlAlchemyPersonnelIntakeRepository(conn)
    active = repo.get_revocable_link_for_application(application_id)
    if active is None:
        raise PersonnelIntakeNotFoundError(
            f"No revocable intake link for application_id={application_id}"
        )
    now = _now_utc()
    return repo.mark_link_revoked(
        active.link_id,
        revoked_at=now,
        revoked_by_user_id=revoked_by_user_id,
    )


def get_intake_summary(conn: Connection, application_id: int) -> IntakeSummary:
    _require_application(conn, application_id)
    repo = SqlAlchemyPersonnelIntakeRepository(conn)
    return repo.load_intake_summary(application_id)


def _resolve_link_by_token(
    conn: Connection,
    raw_token: str,
) -> tuple[SqlAlchemyPersonnelIntakeRepository, IntakeLinkSnapshot]:
    token = str(raw_token or "").strip()
    if not token:
        raise PersonnelIntakeTokenError("Intake token is required.", code="TOKEN_MISSING")
    repo = SqlAlchemyPersonnelIntakeRepository(conn)
    link = repo.get_link_by_token_hash(_hash_token(token))
    if link is None:
        raise PersonnelIntakeTokenError("Invalid intake token.", code="TOKEN_INVALID")
    now = _now_utc()
    link = _ensure_not_expired(link, now=now, repo=repo)
    if link.status == INTAKE_LINK_STATUS_REVOKED:
        raise PersonnelIntakeTokenError("Intake link has been revoked.", code="TOKEN_REVOKED")
    if link.status == INTAKE_LINK_STATUS_EXPIRED:
        raise PersonnelIntakeTokenError("Intake link has expired.", code="TOKEN_EXPIRED")
    return repo, link


def _applicant_reedit_allowed(conn: Connection, application_id: int) -> bool:
    app_repo = SqlAlchemyPersonnelApplicationRepository(conn)
    app = app_repo.get_by_id(application_id)
    if app is None:
        return False
    review_repo = SqlAlchemyPersonnelIntakeReviewRepository(conn)
    sections = review_repo.list_section_reviews(application_id)
    return can_applicant_reedit_submitted_intake(
        application_status=app.status,
        section_statuses=[section.status for section in sections],
    )


def _should_reopen_submitted_intake_for_applicant_edit(
    conn: Connection,
    *,
    application_id: int,
    link: IntakeLinkSnapshot,
    draft: IntakeDraftSnapshot,
) -> bool:
    app_repo = SqlAlchemyPersonnelApplicationRepository(conn)
    app = app_repo.get_by_id(application_id)
    if app is None:
        return False
    review_repo = SqlAlchemyPersonnelIntakeReviewRepository(conn)
    sections = review_repo.list_section_reviews(application_id)
    return should_reopen_submitted_intake_for_applicant_edit(
        application_status=app.status,
        draft_status=draft.status,
        link_status=link.status,
        draft_submitted_at=draft.submitted_at,
        director_resolution_at=app.director_resolution_at,
        section_reviews=sections,
    )


def _reopen_intake_for_applicant_edit(
    repo: SqlAlchemyPersonnelIntakeRepository,
    *,
    link: IntakeLinkSnapshot,
    draft: IntakeDraftSnapshot,
    now: datetime,
) -> tuple[IntakeLinkSnapshot, IntakeDraftSnapshot]:
    next_link = link
    next_draft = draft
    if link.status == INTAKE_LINK_STATUS_SUBMITTED:
        next_link = repo.mark_link_reopened_for_rework(link.link_id, opened_at=now)
    if draft.status == INTAKE_DRAFT_STATUS_SUBMITTED:
        next_draft = repo.mark_draft_editable_for_rework(draft.draft_id, updated_at=now)
    return next_link, next_draft


def reopen_intake_for_applicant_rework(conn: Connection, application_id: int) -> None:
    """Reopen submitted intake link/draft when applicant must edit after HR rework."""
    if not _applicant_reedit_allowed(conn, application_id):
        return
    repo = SqlAlchemyPersonnelIntakeRepository(conn)
    link = repo.get_latest_link_for_application(application_id)
    draft = repo.get_draft_by_application_id(application_id)
    if link is None or draft is None:
        return
    _reopen_intake_for_applicant_edit(repo, link=link, draft=draft, now=_now_utc())


def open_intake_session(conn: Connection, *, raw_token: str) -> OpenIntakeSessionResult:
    """Open or resume an intake session by token."""
    repo, link = _resolve_link_by_token(conn, raw_token)
    now = _now_utc()

    if link.status == INTAKE_LINK_STATUS_SUBMITTED:
        draft = repo.get_draft_by_application_id(link.application_id)
        if draft is None:
            raise PersonnelIntakeNotFoundError(
                f"Draft missing for application_id={link.application_id}"
            )
        if _applicant_reedit_allowed(conn, link.application_id):
            if _should_reopen_submitted_intake_for_applicant_edit(
                conn,
                application_id=link.application_id,
                link=link,
                draft=draft,
            ):
                link, draft = _reopen_intake_for_applicant_edit(
                    repo,
                    link=link,
                    draft=draft,
                    now=now,
                )
                return OpenIntakeSessionResult(
                    application_id=link.application_id,
                    link=link,
                    draft=draft,
                    read_only=False,
                )
            return OpenIntakeSessionResult(
                application_id=link.application_id,
                link=link,
                draft=draft,
                read_only=True,
            )
        return OpenIntakeSessionResult(
            application_id=link.application_id,
            link=link,
            draft=draft,
            read_only=True,
        )

    if not is_intake_link_usable(link.status):
        raise PersonnelIntakeTokenError(
            f"Intake link is not accessible (status={link.status}).",
            code="TOKEN_NOT_ACCESSIBLE",
        )

    if link.status == INTAKE_LINK_STATUS_ISSUED:
        link = repo.mark_link_opened(link.link_id, opened_at=now)
    elif link.status == INTAKE_LINK_STATUS_OPENED:
        pass
    else:
        raise PersonnelIntakeTokenError(
            f"Intake link is not accessible (status={link.status}).",
            code="TOKEN_NOT_ACCESSIBLE",
        )

    draft = repo.get_draft_by_application_id(link.application_id)
    if draft is None:
        draft = repo.create_draft(
            application_id=link.application_id,
            link_id=link.link_id,
            payload=build_initial_intake_draft_payload(conn, link.application_id),
        )

    read_only = draft.status == INTAKE_DRAFT_STATUS_SUBMITTED
    return OpenIntakeSessionResult(
        application_id=link.application_id,
        link=link,
        draft=draft,
        read_only=read_only,
    )


def autosave_intake_draft(
    conn: Connection,
    *,
    raw_token: str,
    payload: dict[str, Any],
) -> AutosaveIntakeDraftResult:
    """Autosave draft payload for an open intake session."""
    repo, link = _resolve_link_by_token(conn, raw_token)
    now = _now_utc()

    if link.status == INTAKE_LINK_STATUS_SUBMITTED:
        if not _applicant_reedit_allowed(conn, link.application_id):
            raise PersonnelIntakeTokenError(
                "Intake form has already been submitted.",
                code="ALREADY_SUBMITTED",
            )
    elif not is_intake_link_usable(link.status):
        raise PersonnelIntakeTokenError(
            f"Intake link is not editable (status={link.status}).",
            code="TOKEN_NOT_EDITABLE",
        )

    if link.status == INTAKE_LINK_STATUS_ISSUED:
        link = repo.mark_link_opened(link.link_id, opened_at=now)

    draft = repo.get_draft_by_application_id(link.application_id)
    if draft is None:
        draft = repo.create_draft(
            application_id=link.application_id,
            link_id=link.link_id,
            payload=payload,
        )
        return AutosaveIntakeDraftResult(draft=draft, saved_at=now)

    if link.status == INTAKE_LINK_STATUS_SUBMITTED and draft.status == INTAKE_DRAFT_STATUS_SUBMITTED:
        if _should_reopen_submitted_intake_for_applicant_edit(
            conn,
            application_id=link.application_id,
            link=link,
            draft=draft,
        ):
            link, draft = _reopen_intake_for_applicant_edit(
                repo,
                link=link,
                draft=draft,
                now=now,
            )
        else:
            raise PersonnelIntakeTokenError(
                "Intake draft is read-only.",
                code="DRAFT_READ_ONLY",
            )

    if not is_intake_draft_editable(draft.status):
        raise PersonnelIntakeTokenError(
            "Intake draft is read-only.",
            code="DRAFT_READ_ONLY",
        )

    updated = repo.update_draft_payload(draft.draft_id, payload=payload, updated_at=now)
    return AutosaveIntakeDraftResult(draft=updated, saved_at=now)


def submit_intake_draft(
    conn: Connection,
    *,
    raw_token: str,
    payload: dict[str, Any] | None = None,
) -> SubmitIntakeDraftResult:
    """Submit intake draft — becomes read-only; application moves to intake_submitted."""
    repo, link = _resolve_link_by_token(conn, raw_token)
    now = _now_utc()

    if link.status == INTAKE_LINK_STATUS_SUBMITTED:
        if not _applicant_reedit_allowed(conn, link.application_id):
            raise PersonnelIntakeTokenError(
                "Intake form has already been submitted.",
                code="ALREADY_SUBMITTED",
            )
    elif not is_intake_link_usable(link.status):
        raise PersonnelIntakeTokenError(
            f"Intake link cannot accept submission (status={link.status}).",
            code="TOKEN_NOT_SUBMITTABLE",
        )

    if link.status == INTAKE_LINK_STATUS_ISSUED:
        link = repo.mark_link_opened(link.link_id, opened_at=now)

    draft = repo.get_draft_by_application_id(link.application_id)
    if draft is None:
        draft = repo.create_draft(
            application_id=link.application_id,
            link_id=link.link_id,
            payload=payload or empty_intake_draft_payload(),
        )
    elif payload is not None and is_intake_draft_editable(draft.status):
        draft = repo.update_draft_payload(draft.draft_id, payload=payload, updated_at=now)

    if link.status == INTAKE_LINK_STATUS_SUBMITTED and draft.status == INTAKE_DRAFT_STATUS_SUBMITTED:
        link, draft = _reopen_intake_for_applicant_edit(
            repo,
            link=link,
            draft=draft,
            now=now,
        )
        if payload is not None:
            draft = repo.update_draft_payload(draft.draft_id, payload=payload, updated_at=now)

    if not is_intake_draft_editable(draft.status):
        raise PersonnelIntakeTokenError(
            "Intake draft is already submitted.",
            code="ALREADY_SUBMITTED",
        )

    _validate_submit_payload(draft.payload)

    draft = repo.mark_draft_submitted(draft.draft_id, submitted_at=now)
    link = repo.mark_link_submitted(link.link_id, submitted_at=now)
    app_repo = SqlAlchemyPersonnelApplicationRepository(conn)
    app = app_repo.require_by_id(link.application_id)
    if app.status == APPLICATION_STATUS_INTAKE_PENDING:
        _transition_application_status(
            conn,
            application_id=link.application_id,
            new_status=APPLICATION_STATUS_INTAKE_SUBMITTED,
            now=now,
        )

    return SubmitIntakeDraftResult(
        application_id=link.application_id,
        link=link,
        draft=draft,
        submitted_at=now,
    )


def _validate_submit_payload(payload: dict[str, Any]) -> None:
    personal = payload.get("personal") or {}
    contacts = payload.get("contacts") or {}
    errors: list[str] = []
    if not str(personal.get("last_name") or "").strip():
        errors.append("personal.last_name")
    if not str(personal.get("first_name") or "").strip():
        errors.append("personal.first_name")
    if not str(contacts.get("mobile_phone") or "").strip():
        errors.append("contacts.mobile_phone")
    education = payload.get("education") or []
    if not isinstance(education, list) or len(education) == 0:
        errors.append("education")
    else:
        seen_fingerprints: dict[tuple[str, str], int] = {}
        for index, item in enumerate(education):
            if not isinstance(item, dict):
                errors.append(f"education[{index}]")
                continue
            raw_type = str(item.get("education_type") or "").strip().lower()
            if raw_type and raw_type not in INTAKE_EDUCATION_TYPES:
                errors.append(f"education[{index}].education_type")
                continue
            education_type = normalize_intake_education_type(item.get("education_type"))
            try:
                fingerprint = intake_education_duplicate_fingerprint(item)
            except ValueError:
                errors.append(f"education[{index}].education_type")
                continue
            if fingerprint in seen_fingerprints:
                prior = seen_fingerprints[fingerprint]
                raise PersonnelIntakeValidationError(
                    "Duplicate education records: same education_type and institution "
                    f"(education[{prior}], education[{index}], "
                    f"education_type={education_type!r}, "
                    f"institution={fingerprint[1]!r})"
                )
            seen_fingerprints[fingerprint] = index
    date_errors = collect_intake_date_validation_errors(payload)
    errors.extend(date_errors)
    if errors:
        if date_errors:
            raise PersonnelIntakeValidationError(
                "Intake dates must be full day precision (ДД.ММ.ГГГГ): "
                + ", ".join(date_errors)
            )
        raise PersonnelIntakeValidationError(
            f"Required intake fields missing: {', '.join(errors)}"
        )


def get_hr_intake_draft(conn: Connection, application_id: int) -> IntakeDraftSnapshot | None:
    """HR read-only access to submitted/editable draft."""
    _require_application(conn, application_id)
    repo = SqlAlchemyPersonnelIntakeRepository(conn)
    return repo.get_draft_by_application_id(application_id)
