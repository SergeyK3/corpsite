"""Application service for intake applicant photo upload and retrieval."""
from __future__ import annotations

import uuid
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.engine import Connection

from app.personnel_intake.application.intake_service import (
    _applicant_reedit_allowed,
    _reopen_intake_for_applicant_edit,
    _resolve_link_by_token,
)
from app.personnel_intake.application.on_behalf_edit_service import load_on_behalf_edit_session
from app.personnel_intake.domain.errors import (
    PersonnelIntakeNotFoundError,
    PersonnelIntakeOnBehalfEditError,
    PersonnelIntakeTokenError,
    PersonnelIntakeValidationError,
)
from app.personnel_intake.domain.models import empty_intake_draft_payload
from app.personnel_intake.domain.photo_archive_name import build_intake_photo_archive_filename
from app.personnel_intake.domain.photo_validation import validate_intake_photo_bytes
from app.personnel_intake.domain.status import (
    INTAKE_DRAFT_STATUS_SUBMITTED,
    INTAKE_LINK_STATUS_ISSUED,
    INTAKE_LINK_STATUS_SUBMITTED,
    is_intake_draft_editable,
    is_intake_link_usable,
)
from app.personnel_intake.infrastructure.photo_storage import (
    delete_intake_photo,
    normalize_intake_photo_file_id,
    read_intake_photo,
    save_intake_photo,
)
from app.personnel_intake.infrastructure.repository import SqlAlchemyPersonnelIntakeRepository


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _photo_file_id_from_payload(payload: dict[str, Any]) -> str:
    personal = payload.get("personal") or {}
    raw = str(personal.get("photo_file_id") or "").strip()
    if not raw:
        return ""
    return normalize_intake_photo_file_id(raw)


def _archive_filename_from_payload(payload: dict[str, Any], *, application_id: int) -> str:
    personal = payload.get("personal") or {}
    return build_intake_photo_archive_filename(
        last_name=str(personal.get("last_name") or ""),
        first_name=str(personal.get("first_name") or ""),
        application_id=application_id,
        personnel_number=str(personal.get("personnel_number") or ""),
    )


def _prepare_public_photo_mutation(
    conn: Connection,
    repo: SqlAlchemyPersonnelIntakeRepository,
    link,
):
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
        raise PersonnelIntakeNotFoundError(f"Draft missing for application_id={link.application_id}")

    if link.status == INTAKE_LINK_STATUS_SUBMITTED and draft.status == INTAKE_DRAFT_STATUS_SUBMITTED:
        # Re-edit already gated by _applicant_reedit_allowed above.
        link, draft = _reopen_intake_for_applicant_edit(
            repo,
            link=link,
            draft=draft,
            now=now,
        )

    if not is_intake_draft_editable(draft.status):
        raise PersonnelIntakeTokenError("Intake draft is read-only.", code="DRAFT_READ_ONLY")
    return link, draft


def _set_photo_file_id(payload: dict[str, Any], file_id: str) -> dict[str, Any]:
    next_payload = deepcopy(payload or empty_intake_draft_payload())
    personal = dict(next_payload.get("personal") or {})
    personal["photo_file_id"] = file_id
    next_payload["personal"] = personal
    return next_payload


def _read_validated_photo(application_id: int, file_id: str) -> bytes:
    content = read_intake_photo(application_id, file_id)
    if content is None:
        raise PersonnelIntakeNotFoundError("Intake photo not found.")
    try:
        validate_intake_photo_bytes(content, content_type="image/jpeg")
    except PersonnelIntakeValidationError as exc:
        # Corrupt/unavailable bytes must not crash consumers (e.g. PDF); treat as missing.
        raise PersonnelIntakeNotFoundError("Intake photo unavailable.") from exc
    return content


@dataclass(frozen=True, slots=True)
class IntakePhotoMutationResult:
    application_id: int
    photo_file_id: str
    payload: dict[str, Any]
    saved_at: datetime


@dataclass(frozen=True, slots=True)
class IntakePhotoReadResult:
    content: bytes
    photo_file_id: str
    archive_filename: str


def upload_intake_photo_by_token(
    conn: Connection,
    *,
    raw_token: str,
    content: bytes,
    content_type: str | None,
) -> IntakePhotoMutationResult:
    validate_intake_photo_bytes(content, content_type=content_type)
    repo, link = _resolve_link_by_token(conn, raw_token)
    _link, draft = _prepare_public_photo_mutation(conn, repo, link)

    previous_id = _photo_file_id_from_payload(draft.payload)
    file_id = uuid.uuid4().hex
    save_intake_photo(link.application_id, file_id, content)
    next_payload = _set_photo_file_id(draft.payload, file_id)
    now = _now_utc()
    saved = repo.update_draft_payload(draft.draft_id, payload=next_payload, updated_at=now)
    if previous_id and previous_id != file_id:
        delete_intake_photo(link.application_id, previous_id)
    return IntakePhotoMutationResult(
        application_id=link.application_id,
        photo_file_id=file_id,
        payload=saved.payload,
        saved_at=now,
    )


def delete_intake_photo_by_token(conn: Connection, *, raw_token: str) -> IntakePhotoMutationResult:
    repo, link = _resolve_link_by_token(conn, raw_token)
    _link, draft = _prepare_public_photo_mutation(conn, repo, link)

    previous_id = _photo_file_id_from_payload(draft.payload)
    next_payload = _set_photo_file_id(draft.payload, "")
    now = _now_utc()
    saved = repo.update_draft_payload(draft.draft_id, payload=next_payload, updated_at=now)
    if previous_id:
        delete_intake_photo(link.application_id, previous_id)
    return IntakePhotoMutationResult(
        application_id=link.application_id,
        photo_file_id="",
        payload=saved.payload,
        saved_at=now,
    )


def get_intake_photo_by_token(conn: Connection, *, raw_token: str) -> IntakePhotoReadResult:
    repo, link = _resolve_link_by_token(conn, raw_token)
    draft = repo.get_draft_by_application_id(link.application_id)
    if draft is None:
        raise PersonnelIntakeNotFoundError(f"Draft missing for application_id={link.application_id}")
    file_id = _photo_file_id_from_payload(draft.payload)
    if not file_id:
        raise PersonnelIntakeNotFoundError("Intake photo not found.")
    content = _read_validated_photo(link.application_id, file_id)
    return IntakePhotoReadResult(
        content=content,
        photo_file_id=file_id,
        archive_filename=_archive_filename_from_payload(draft.payload, application_id=link.application_id),
    )


def upload_intake_photo_on_behalf(
    conn: Connection,
    *,
    application_id: int,
    actor_user_id: int,
    content: bytes,
    content_type: str | None,
) -> IntakePhotoMutationResult:
    validate_intake_photo_bytes(content, content_type=content_type)
    session = load_on_behalf_edit_session(conn, application_id)
    if not session.editable:
        raise PersonnelIntakeOnBehalfEditError(
            session.blocked_reason or "On-behalf edit is not allowed.",
            code=session.reason_code or "ON_BEHALF_BLOCKED",
        )
    repo = SqlAlchemyPersonnelIntakeRepository(conn)
    draft = session.draft
    previous_id = _photo_file_id_from_payload(draft.payload)
    file_id = uuid.uuid4().hex
    save_intake_photo(application_id, file_id, content)
    next_payload = _set_photo_file_id(draft.payload, file_id)
    now = _now_utc()
    saved = repo.update_draft_payload(draft.draft_id, payload=next_payload, updated_at=now)
    if previous_id and previous_id != file_id:
        delete_intake_photo(application_id, previous_id)
    return IntakePhotoMutationResult(
        application_id=application_id,
        photo_file_id=file_id,
        payload=saved.payload,
        saved_at=now,
    )


def delete_intake_photo_on_behalf(
    conn: Connection,
    *,
    application_id: int,
    actor_user_id: int,
) -> IntakePhotoMutationResult:
    session = load_on_behalf_edit_session(conn, application_id)
    if not session.editable:
        raise PersonnelIntakeOnBehalfEditError(
            session.blocked_reason or "On-behalf edit is not allowed.",
            code=session.reason_code or "ON_BEHALF_BLOCKED",
        )
    repo = SqlAlchemyPersonnelIntakeRepository(conn)
    draft = session.draft
    previous_id = _photo_file_id_from_payload(draft.payload)
    next_payload = _set_photo_file_id(draft.payload, "")
    now = _now_utc()
    saved = repo.update_draft_payload(draft.draft_id, payload=next_payload, updated_at=now)
    if previous_id:
        delete_intake_photo(application_id, previous_id)
    return IntakePhotoMutationResult(
        application_id=application_id,
        photo_file_id="",
        payload=saved.payload,
        saved_at=now,
    )


def get_intake_photo_on_behalf(conn: Connection, *, application_id: int) -> IntakePhotoReadResult:
    repo = SqlAlchemyPersonnelIntakeRepository(conn)
    draft = repo.get_draft_by_application_id(application_id)
    if draft is None:
        raise PersonnelIntakeNotFoundError(f"Draft missing for application_id={application_id}")
    file_id = _photo_file_id_from_payload(draft.payload)
    if not file_id:
        raise PersonnelIntakeNotFoundError("Intake photo not found.")
    content = _read_validated_photo(application_id, file_id)
    return IntakePhotoReadResult(
        content=content,
        photo_file_id=file_id,
        archive_filename=_archive_filename_from_payload(draft.payload, application_id=application_id),
    )


def get_intake_photo_by_token_for_application(
    conn: Connection,
    *,
    raw_token: str,
    requested_application_id: int,
) -> IntakePhotoReadResult:
    repo, link = _resolve_link_by_token(conn, raw_token)
    if int(link.application_id) != int(requested_application_id):
        raise PersonnelIntakeTokenError("Intake token does not match application.", code="TOKEN_FORBIDDEN")
    return get_intake_photo_by_token(conn, raw_token=raw_token)
