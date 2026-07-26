"""HIRE apply photo canonicalization hook (WP-ADR061-001D)."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from app.db.engine import engine
from app.db.models.person_photos import (
    BLOCKER_CODE_INTAKE_PHOTO_UNAVAILABLE,
    BLOCKER_CODE_PHOTO_CANONICALIZATION_FAILED,
    CANONICALIZATION_MODE_HIRE_APPLY,
)
from app.person_photos.application.canonicalization_service import canonicalize_person_photo
from app.person_photos.domain.errors import (
    ApplicationNotFoundError,
    ApplicationPersonMismatchError,
    CanonicalFileCollisionError,
    CanonicalFileIntegrityError,
    CanonicalFileMissingError,
    HirePhotoNotReadyError,
    IntakePhotoUnavailableError,
    PhotoCanonicalizationError,
)
from app.person_photos.domain.models import CanonicalizeIntakePhotoRequest, CanonicalizePersonPhotoResult
from app.person_photos.infrastructure.blocker_repository import PersonPhotoBlockerRepository
from app.personnel_intake.infrastructure.photo_storage import normalize_intake_photo_file_id

_EXPECTED_CANONICALIZATION_ERRORS = (
    IntakePhotoUnavailableError,
    PhotoCanonicalizationError,
    CanonicalFileMissingError,
    CanonicalFileIntegrityError,
    CanonicalFileCollisionError,
    ApplicationNotFoundError,
    ApplicationPersonMismatchError,
)


def read_intake_photo_file_id(application_id: int) -> str:
    """Read current intake photo_file_id from draft (closed read txn)."""
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT payload
                FROM public.personnel_intake_drafts
                WHERE application_id = :application_id
                LIMIT 1
                """
            ),
            {"application_id": int(application_id)},
        ).mappings().first()
    if row is None:
        return ""
    payload = row["payload"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    if not isinstance(payload, dict):
        return ""
    personal = payload.get("personal") or {}
    raw = str(personal.get("photo_file_id") or "").strip()
    if not raw:
        return ""
    return normalize_intake_photo_file_id(raw)


def _upsert_open_blocker_durable(
    *,
    application_id: int,
    blocker_code: str,
    detail_json: dict[str, Any] | None = None,
) -> None:
    with engine.begin() as conn:
        PersonPhotoBlockerRepository(conn).upsert_open_blocker(
            application_id=application_id,
            blocker_code=blocker_code,
            detail_json=detail_json,
        )


def _resolve_photo_blockers_durable(*, application_id: int, actor_user_id: int) -> None:
    with engine.begin() as conn:
        PersonPhotoBlockerRepository(conn).resolve_photo_blockers(
            application_id=application_id,
            resolved_by_user_id=actor_user_id,
        )


def ensure_hire_photo_ready(
    *,
    application_id: int,
    person_id: int,
    actor_user_id: int,
    correlation_id: str | None = None,
) -> CanonicalizePersonPhotoResult:
    """Canonicalize intake photo for HIRE apply outside caller-owned HIRE txn."""
    photo_file_id = read_intake_photo_file_id(application_id)
    if not photo_file_id:
        _upsert_open_blocker_durable(
            application_id=application_id,
            blocker_code=BLOCKER_CODE_INTAKE_PHOTO_UNAVAILABLE,
            detail_json={"reason": "missing_photo_file_id"},
        )
        raise HirePhotoNotReadyError(
            f"Intake photo is unavailable for application_id={application_id}.",
            code="INTAKE_PHOTO_UNAVAILABLE",
            blocker_code=BLOCKER_CODE_INTAKE_PHOTO_UNAVAILABLE,
        )

    request = CanonicalizeIntakePhotoRequest(
        person_id=int(person_id),
        application_id=int(application_id),
        intake_photo_file_id=photo_file_id,
        canonicalization_mode=CANONICALIZATION_MODE_HIRE_APPLY,
        actor_user_id=int(actor_user_id),
        correlation_id=correlation_id,
    )

    try:
        result = canonicalize_person_photo(request)
    except IntakePhotoUnavailableError as exc:
        _upsert_open_blocker_durable(
            application_id=application_id,
            blocker_code=BLOCKER_CODE_INTAKE_PHOTO_UNAVAILABLE,
            detail_json={"reason": str(exc)},
        )
        raise HirePhotoNotReadyError(
            str(exc),
            code="INTAKE_PHOTO_UNAVAILABLE",
            blocker_code=BLOCKER_CODE_INTAKE_PHOTO_UNAVAILABLE,
        ) from exc
    except _EXPECTED_CANONICALIZATION_ERRORS as exc:
        _upsert_open_blocker_durable(
            application_id=application_id,
            blocker_code=BLOCKER_CODE_PHOTO_CANONICALIZATION_FAILED,
            detail_json={"reason": str(exc), "error_type": type(exc).__name__},
        )
        raise HirePhotoNotReadyError(
            str(exc),
            code="PHOTO_CANONICALIZATION_FAILED",
            blocker_code=BLOCKER_CODE_PHOTO_CANONICALIZATION_FAILED,
        ) from exc

    _resolve_photo_blockers_durable(
        application_id=application_id,
        actor_user_id=actor_user_id,
    )
    return result
