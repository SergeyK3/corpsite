"""Public Personnel Intake API — token-based access without JWT (WP-PPR-INTAKE-001)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path

from app.db.engine import engine
from app.directory.common import as_http500
from app.directory.personnel_intake_schemas import (
    IntakeAutosaveIn,
    IntakeAutosaveOut,
    IntakeDraftOut,
    IntakeSubmitIn,
    IntakeSubmitOut,
    draft_session_to_out,
)
from app.personnel_intake.application.intake_service import (
    autosave_intake_draft,
    open_intake_session,
    submit_intake_draft,
)
from app.personnel_intake.domain.errors import (
    PersonnelIntakeNotFoundError,
    PersonnelIntakeTokenError,
    PersonnelIntakeValidationError,
)

router = APIRouter(prefix="/intake", tags=["personnel-intake-public"])


def _token_http403(exc: PersonnelIntakeTokenError) -> HTTPException:
    return HTTPException(
        status_code=403,
        detail={"code": exc.code, "message": str(exc)},
    )


def _validation_http422(exc: PersonnelIntakeValidationError) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={"code": type(exc).__name__, "message": str(exc)},
    )


@router.get("/{token}", response_model=IntakeDraftOut)
def get_intake_session(token: str = Path(..., min_length=8)) -> IntakeDraftOut:
    """Open or resume intake session by protected token."""
    try:
        with engine.begin() as conn:
            session = open_intake_session(conn, raw_token=token)
        return draft_session_to_out(
            draft=session.draft,
            link=session.link,
            read_only=session.read_only,
        )
    except PersonnelIntakeTokenError as exc:
        raise _token_http403(exc)
    except PersonnelIntakeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.patch("/{token}", response_model=IntakeAutosaveOut)
def patch_intake_autosave(
    body: IntakeAutosaveIn,
    token: str = Path(..., min_length=8),
) -> IntakeAutosaveOut:
    """Autosave intake draft payload."""
    try:
        with engine.begin() as conn:
            result = autosave_intake_draft(conn, raw_token=token, payload=body.payload)
        return IntakeAutosaveOut(
            draft_id=result.draft.draft_id,
            status=result.draft.status,
            payload=result.draft.payload,
            saved_at=result.saved_at,
        )
    except PersonnelIntakeTokenError as exc:
        raise _token_http403(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post("/{token}/submit", response_model=IntakeSubmitOut)
def post_intake_submit(
    body: IntakeSubmitIn,
    token: str = Path(..., min_length=8),
) -> IntakeSubmitOut:
    """Submit completed intake form."""
    try:
        with engine.begin() as conn:
            result = submit_intake_draft(conn, raw_token=token, payload=body.payload)
        return IntakeSubmitOut(
            application_id=result.application_id,
            draft_id=result.draft.draft_id,
            status=result.draft.status,
            submitted_at=result.submitted_at,
        )
    except PersonnelIntakeTokenError as exc:
        raise _token_http403(exc)
    except PersonnelIntakeValidationError as exc:
        raise _validation_http422(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)
