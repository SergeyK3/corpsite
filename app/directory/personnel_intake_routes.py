"""HR-facing Personnel Intake API (WP-PPR-INTAKE-001/002)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from app.auth import get_current_user
from app.db.engine import engine
from app.directory.common import as_http500
from app.directory.personnel_intake_schemas import (
    IntakeAutosaveIn,
    IntakeDraftOut,
    IntakeLinkAccessOut,
    IntakeLinkIssueOut,
    IntakeOnBehalfEditSessionOut,
    IntakeOnBehalfSaveOut,
    IntakeReviewStateOut,
    IntakeRevokeOut,
    IntakeSectionReworkIn,
    IntakeSummaryOut,
    IntakeTransferAuditListOut,
    IntakeTransferOut,
    draft_session_to_out,
    review_state_to_out,
    summary_to_out,
    transfer_to_out,
)
from app.directory.rbac import require_personnel_admin_or_403
from app.personnel_applications.domain.errors import PersonnelApplicationNotFoundError
from app.personnel_intake.application.hr_link_access_service import get_hr_intake_link_display
from app.personnel_intake.application.intake_service import (
    get_hr_intake_draft,
    get_intake_summary,
    issue_intake_link,
    revoke_intake_link,
)
from app.personnel_intake.application.on_behalf_edit_service import (
    load_on_behalf_edit_session,
    save_on_behalf_intake_draft,
)
from app.personnel_intake.application.review_service import (
    accept_intake_section,
    load_intake_review_state,
    rework_intake_section,
    skip_intake_section,
)
from app.personnel_intake.application.transfer_service import (
    list_intake_transfer_audit,
    transfer_intake_to_ppr,
)
from app.personnel_intake.domain.errors import (
    PersonnelIntakeConflictError,
    PersonnelIntakeNotFoundError,
    PersonnelIntakeOnBehalfEditError,
    PersonnelIntakeReviewError,
    PersonnelIntakeTransferError,
    PersonnelIntakeValidationError,
)
from app.personnel_intake.infrastructure.repository import SqlAlchemyPersonnelIntakeRepository

router = APIRouter(prefix="/personnel-applications", tags=["personnel-intake"])


def _require_user_id(user: dict[str, Any]) -> int:
    uid = user.get("user_id") or user.get("id")
    if uid is None:
        raise HTTPException(status_code=401, detail="Unauthorized.")
    return int(uid)


def _review_error_http422(exc: PersonnelIntakeReviewError) -> HTTPException:
    return HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)})


def _transfer_error_http422(exc: PersonnelIntakeTransferError) -> HTTPException:
    return HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)})


def _on_behalf_edit_error_http422(exc: PersonnelIntakeOnBehalfEditError) -> HTTPException:
    return HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)})


@router.post("/{application_id}/intake-link", response_model=IntakeLinkIssueOut)
def post_intake_link_issue(
    application_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> IntakeLinkIssueOut:
    require_personnel_admin_or_403(user)
    user_id = _require_user_id(user)
    try:
        with engine.begin() as conn:
            result = issue_intake_link(
                conn,
                application_id=application_id,
                issued_by_user_id=user_id,
                reissue=False,
            )
        return IntakeLinkIssueOut(
            application_id=result.application_id,
            link_id=result.link_id,
            intake_url_path=result.intake_url_path,
            expires_at=result.expires_at,
            status=result.status,
            reissued=result.reissued,
        )
    except PersonnelApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelIntakeConflictError as exc:
        raise HTTPException(status_code=409, detail={"code": exc.code, "message": str(exc)})
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.get("/{application_id}/intake-link/active", response_model=IntakeLinkAccessOut)
def get_intake_link_active(
    application_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> IntakeLinkAccessOut:
    require_personnel_admin_or_403(user)
    try:
        with engine.connect() as conn:
            display = get_hr_intake_link_display(conn, application_id)
        return IntakeLinkAccessOut(
            application_id=display.application_id,
            display_state=display.display_state,
            link_id=display.link_id,
            link_status=display.link_status,
            intake_url_path=display.intake_url_path,
            expires_at=display.expires_at,
        )
    except PersonnelApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post("/{application_id}/intake-link/reissue", response_model=IntakeLinkIssueOut)
def post_intake_link_reissue(
    application_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> IntakeLinkIssueOut:
    require_personnel_admin_or_403(user)
    user_id = _require_user_id(user)
    try:
        with engine.begin() as conn:
            result = issue_intake_link(
                conn,
                application_id=application_id,
                issued_by_user_id=user_id,
                reissue=True,
            )
        return IntakeLinkIssueOut(
            application_id=result.application_id,
            link_id=result.link_id,
            intake_url_path=result.intake_url_path,
            expires_at=result.expires_at,
            status=result.status,
            reissued=result.reissued,
        )
    except PersonnelApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post("/{application_id}/intake-link/revoke", response_model=IntakeRevokeOut)
def post_intake_link_revoke(
    application_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> IntakeRevokeOut:
    require_personnel_admin_or_403(user)
    user_id = _require_user_id(user)
    try:
        with engine.begin() as conn:
            link = revoke_intake_link(
                conn,
                application_id=application_id,
                revoked_by_user_id=user_id,
            )
        return IntakeRevokeOut(
            application_id=application_id,
            link_id=link.link_id,
            status=link.status,
            revoked_at=link.revoked_at,  # type: ignore[arg-type]
        )
    except PersonnelApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelIntakeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.get("/{application_id}/intake", response_model=IntakeSummaryOut)
def get_intake_summary_route(
    application_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> IntakeSummaryOut:
    require_personnel_admin_or_403(user)
    try:
        with engine.connect() as conn:
            summary = get_intake_summary(conn, application_id)
        return summary_to_out(summary)
    except PersonnelApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.get("/{application_id}/intake/draft", response_model=IntakeDraftOut)
def get_intake_draft_for_hr(
    application_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> IntakeDraftOut:
    require_personnel_admin_or_403(user)
    try:
        with engine.connect() as conn:
            draft = get_hr_intake_draft(conn, application_id)
            if draft is None:
                raise HTTPException(status_code=404, detail="Intake draft not found.")
            repo = SqlAlchemyPersonnelIntakeRepository(conn)
            link = repo.get_link_by_id(draft.link_id)
            if link is None:
                raise HTTPException(status_code=404, detail="Intake link not found.")
            read_only = draft.status == "submitted"
        return draft_session_to_out(draft=draft, link=link, read_only=read_only)
    except PersonnelApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.get("/{application_id}/intake/draft/on-behalf-edit", response_model=IntakeOnBehalfEditSessionOut)
def get_intake_on_behalf_edit_session(
    application_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> IntakeOnBehalfEditSessionOut:
    require_personnel_admin_or_403(user)
    try:
        with engine.connect() as conn:
            session = load_on_behalf_edit_session(conn, application_id)
        return IntakeOnBehalfEditSessionOut(
            application_id=session.application_id,
            draft=draft_session_to_out(
                draft=session.draft,
                link=session.link,
                read_only=not session.editable,
            ),
            editable=session.editable,
            blocked_reason=session.blocked_reason,
            reason_code=session.reason_code,
        )
    except PersonnelApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelIntakeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.patch("/{application_id}/intake/draft/on-behalf", response_model=IntakeOnBehalfSaveOut)
def patch_intake_on_behalf_draft(
    body: IntakeAutosaveIn,
    application_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> IntakeOnBehalfSaveOut:
    require_personnel_admin_or_403(user)
    user_id = _require_user_id(user)
    try:
        with engine.begin() as conn:
            result = save_on_behalf_intake_draft(
                conn,
                application_id=application_id,
                payload=body.payload,
                actor_user_id=user_id,
            )
        return IntakeOnBehalfSaveOut(
            application_id=result.application_id,
            draft_id=result.draft.draft_id,
            status=result.draft.status,
            saved_at=result.saved_at,
            changed_fields=list(result.changed_fields),
        )
    except PersonnelApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelIntakeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelIntakeOnBehalfEditError as exc:
        raise _on_behalf_edit_error_http422(exc)
    except PersonnelIntakeValidationError as exc:
        raise HTTPException(status_code=422, detail={"code": "VALIDATION_FAILED", "message": str(exc)})
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.get("/{application_id}/intake/review", response_model=IntakeReviewStateOut)
def get_intake_review_state_route(
    application_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> IntakeReviewStateOut:
    require_personnel_admin_or_403(user)
    try:
        with engine.begin() as conn:
            state = load_intake_review_state(conn, application_id)
            link = SqlAlchemyPersonnelIntakeRepository(conn).get_link_by_id(state.draft.link_id)
        return review_state_to_out(state, link=link)
    except PersonnelApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelIntakeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelIntakeReviewError as exc:
        raise _review_error_http422(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post(
    "/{application_id}/intake/review/sections/{section_code}/accept",
    response_model=IntakeReviewStateOut,
)
def post_intake_section_accept(
    application_id: int = Path(..., ge=1),
    section_code: str = Path(..., min_length=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> IntakeReviewStateOut:
    require_personnel_admin_or_403(user)
    user_id = _require_user_id(user)
    try:
        with engine.begin() as conn:
            result = accept_intake_section(
                conn,
                application_id=application_id,
                section_code=section_code,
                reviewed_by_user_id=user_id,
            )
            link = SqlAlchemyPersonnelIntakeRepository(conn).get_link_by_id(
                result.review_state.draft.link_id
            )
        return review_state_to_out(result.review_state, link=link)
    except PersonnelApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelIntakeReviewError as exc:
        raise _review_error_http422(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post(
    "/{application_id}/intake/review/sections/{section_code}/rework",
    response_model=IntakeReviewStateOut,
)
def post_intake_section_rework(
    body: IntakeSectionReworkIn,
    application_id: int = Path(..., ge=1),
    section_code: str = Path(..., min_length=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> IntakeReviewStateOut:
    require_personnel_admin_or_403(user)
    user_id = _require_user_id(user)
    try:
        with engine.begin() as conn:
            result = rework_intake_section(
                conn,
                application_id=application_id,
                section_code=section_code,
                reviewed_by_user_id=user_id,
                comment=body.comment,
            )
            link = SqlAlchemyPersonnelIntakeRepository(conn).get_link_by_id(
                result.review_state.draft.link_id
            )
        return review_state_to_out(result.review_state, link=link)
    except PersonnelApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelIntakeReviewError as exc:
        raise _review_error_http422(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post(
    "/{application_id}/intake/review/sections/{section_code}/skip",
    response_model=IntakeReviewStateOut,
)
def post_intake_section_skip(
    application_id: int = Path(..., ge=1),
    section_code: str = Path(..., min_length=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> IntakeReviewStateOut:
    require_personnel_admin_or_403(user)
    user_id = _require_user_id(user)
    try:
        with engine.begin() as conn:
            result = skip_intake_section(
                conn,
                application_id=application_id,
                section_code=section_code,
                reviewed_by_user_id=user_id,
            )
            link = SqlAlchemyPersonnelIntakeRepository(conn).get_link_by_id(
                result.review_state.draft.link_id
            )
        return review_state_to_out(result.review_state, link=link)
    except PersonnelApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelIntakeReviewError as exc:
        raise _review_error_http422(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post("/{application_id}/intake/transfer", response_model=IntakeTransferOut)
def post_intake_transfer_to_ppr(
    application_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> IntakeTransferOut:
    require_personnel_admin_or_403(user)
    user_id = _require_user_id(user)
    actor_id = f"user:{user_id}"
    try:
        with engine.begin() as conn:
            result = transfer_intake_to_ppr(
                conn,
                application_id=application_id,
                transferred_by_user_id=user_id,
                actor_id=actor_id,
            )
        return IntakeTransferOut(
            application_id=result.application_id,
            transfer=transfer_to_out(result.transfer),
            idempotent_replay=result.idempotent_replay,
        )
    except PersonnelApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelIntakeTransferError as exc:
        raise _transfer_error_http422(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.get("/intake/transfers", response_model=IntakeTransferAuditListOut)
def get_intake_transfer_audit_journal(
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict[str, Any] = Depends(get_current_user),
) -> IntakeTransferAuditListOut:
    require_personnel_admin_or_403(user)
    try:
        with engine.connect() as conn:
            items = list_intake_transfer_audit(conn, limit=limit, offset=offset)
        return IntakeTransferAuditListOut(
            items=[transfer_to_out(item) for item in items],
            total=len(items),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)
