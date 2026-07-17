"""Personnel Application registration API (WP-PPR-APPLICANT-001B)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from app.auth import get_current_user
from app.db.engine import engine
from app.directory.common import as_http500
from app.directory.personnel_applications_schemas import (
    ApplicationApplyOut,
    ApplicationTimelineOut,
    CombinedAuditListOut,
    CombinedAuditOut,
    DirectorResolutionActionOut,
    DirectorResolutionChangeIn,
    DirectorResolutionRecordIn,
    HireOrderDraftOut,
    LifecycleAuditListOut,
    LifecycleAuditOut,
    PersonnelApplicationCancelIn,
    PersonnelApplicationCancelOut,
    PersonnelApplicationDetailOut,
    PersonnelApplicationListOut,
    PersonnelApplicationPreviewIn,
    PersonnelApplicationPreviewOut,
    PersonnelApplicationRegisterIn,
    PersonnelApplicationRegisterOut,
    ResolutionAuditListOut,
    application_resolution_to_out,
    audit_to_out,
    lifecycle_audit_to_out,
    list_item_to_out,
    snapshot_to_detail,
    timeline_event_to_out,
)
from app.directory.rbac import require_personnel_admin_or_403
from app.personnel_applications.application.detail_enrichment import (
    load_application_detail_enrichment,
    load_application_lifecycle_fields,
)
from app.personnel_applications.application.lifecycle_service import (
    cancel_application,
    expire_due_applications,
)
from app.personnel_applications.application.query_service import list_personnel_applications
from app.personnel_applications.application.timeline_service import (
    build_application_timeline,
    list_combined_audit,
)
from app.personnel_applications.application.registration_service import (
    preview_registration,
    register_personnel_application,
)
from app.personnel_applications.application.hire_order_draft_service import (
    create_hire_order_draft_for_application,
)
from app.personnel_applications.application.application_apply_service import (
    apply_hire_for_application,
)
from app.personnel_applications.application.resolution_service import (
    change_director_resolution,
    list_resolution_audit,
    open_director_resolution,
    record_director_resolution,
    reopen_director_resolution,
)
from app.personnel_applications.domain.errors import (
    ActiveEmployeeBlocksRegistrationError,
    PersonnelApplicationApplyError,
    PersonnelApplicationHireOrderError,
    PersonnelApplicationLifecycleError,
    PersonnelApplicationNotFoundError,
    PersonnelApplicationResolutionError,
    PersonnelApplicationValidationError,
    VacancyCheckGateError,
)
from app.personnel_applications.infrastructure.repository import SqlAlchemyPersonnelApplicationRepository

router = APIRouter(prefix="/personnel-applications", tags=["personnel-applications"])


def _require_user_id(user: dict[str, Any]) -> int:
    uid = user.get("user_id") or user.get("id")
    if uid is None:
        raise HTTPException(status_code=401, detail="Unauthorized.")
    return int(uid)


def _validation_http422(exc: PersonnelApplicationValidationError | VacancyCheckGateError) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={"code": type(exc).__name__, "message": str(exc)},
    )


def _conflict_http409(exc: ActiveEmployeeBlocksRegistrationError) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={"code": exc.code, "message": str(exc)},
    )


def _resolution_http422(exc: PersonnelApplicationResolutionError) -> HTTPException:
    return HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)})


def _hire_order_http422(exc: PersonnelApplicationHireOrderError) -> HTTPException:
    return HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)})


def _apply_http422(exc: PersonnelApplicationApplyError) -> HTTPException:
    return HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)})


def _lifecycle_http422(exc: PersonnelApplicationLifecycleError) -> HTTPException:
    return HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)})


@router.post("/preview", response_model=PersonnelApplicationPreviewOut)
def post_personnel_application_preview(
    body: PersonnelApplicationPreviewIn,
    user: dict[str, Any] = Depends(get_current_user),
) -> PersonnelApplicationPreviewOut:
    require_personnel_admin_or_403(user)
    try:
        with engine.connect() as conn:
            result = preview_registration(conn, iin_raw=body.iin)
        return PersonnelApplicationPreviewOut(
            iin=result.iin,
            person_exists=result.person_exists,
            person_id=result.person_id,
            full_name=result.full_name,
            hr_relationship_context=result.hr_relationship_context,
            has_active_employee=result.has_active_employee,
            has_active_application=result.has_active_application,
            active_application_id=result.active_application_id,
            can_register=result.can_register,
            block_reason=result.block_reason,
        )
    except PersonnelApplicationValidationError as exc:
        raise _validation_http422(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post("", response_model=PersonnelApplicationRegisterOut)
def post_personnel_application_register(
    body: PersonnelApplicationRegisterIn,
    user: dict[str, Any] = Depends(get_current_user),
) -> PersonnelApplicationRegisterOut:
    require_personnel_admin_or_403(user)
    user_id = _require_user_id(user)
    actor_id = f"user:{user_id}"
    try:
        with engine.begin() as conn:
            result = register_personnel_application(
                conn,
                iin_raw=body.iin,
                full_name=body.full_name,
                birth_date=body.birth_date,
                application_received_at=body.application_received_at,
                vacancy_check_status=body.vacancy_check_status,
                vacancy_checked_at=body.vacancy_checked_at,
                vacancy_checked_by_user_id=body.vacancy_checked_by_user_id,
                intended_org_group_id=body.intended_org_group_id,
                intended_org_unit_id=body.intended_org_unit_id,
                intended_position_id=body.intended_position_id,
                intended_employment_rate=body.intended_employment_rate,
                intended_vacancy_text=body.intended_vacancy_text,
                contact_mobile_phone=body.contact_mobile_phone,
                contact_email=body.contact_email,
                hr_note=body.hr_note,
                idempotency_key=body.idempotency_key,
                registered_by_user_id=user_id,
                actor_id=actor_id,
            )
        return PersonnelApplicationRegisterOut(
            person_id=result.person_id,
            application_id=result.application_id,
            action=result.action,  # type: ignore[arg-type]
            card_href=result.card_href,
        )
    except VacancyCheckGateError as exc:
        raise _validation_http422(exc)
    except PersonnelApplicationValidationError as exc:
        raise _validation_http422(exc)
    except ActiveEmployeeBlocksRegistrationError as exc:
        raise _conflict_http409(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.get("", response_model=PersonnelApplicationListOut)
def list_personnel_applications_route(
    q: str | None = Query(None),
    status: str | None = Query(None),
    view: str = Query("active"),
    org_group_id: int | None = Query(None, ge=1),
    org_unit_id: int | None = Query(None, ge=1),
    position_id: int | None = Query(None, ge=1),
    sort: str = Query("application_received_at_desc"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict[str, Any] = Depends(get_current_user),
) -> PersonnelApplicationListOut:
    require_personnel_admin_or_403(user)
    try:
        with engine.begin() as conn:
            expire_due_applications(conn)
            items, total = list_personnel_applications(
                conn,
                q=q,
                status=status,
                view=view,
                org_group_id=org_group_id,
                org_unit_id=org_unit_id,
                position_id=position_id,
                sort=sort,
                limit=limit,
                offset=offset,
            )
        return PersonnelApplicationListOut(
            items=[list_item_to_out(item) for item in items],
            total=total,
            limit=limit,
            offset=offset,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.get("/{application_id}", response_model=PersonnelApplicationDetailOut)
def get_personnel_application(
    application_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> PersonnelApplicationDetailOut:
    require_personnel_admin_or_403(user)
    try:
        with engine.connect() as conn:
            repo = SqlAlchemyPersonnelApplicationRepository(conn)
            snapshot = repo.require_by_id(application_id)
            enrichment = load_application_detail_enrichment(conn, snapshot)
            from app.personnel_intake.infrastructure.repository import (
                SqlAlchemyPersonnelIntakeRepository,
            )

            intake_summary = SqlAlchemyPersonnelIntakeRepository(conn).load_intake_summary(
                application_id
            )
            lifecycle = load_application_lifecycle_fields(conn, application_id)
        return snapshot_to_detail(
            snapshot,
            **enrichment,
            **lifecycle,
            intake_link_status=intake_summary.link_status if intake_summary else None,
            intake_draft_status=intake_summary.draft_status if intake_summary else None,
            intake_opened_at=intake_summary.opened_at if intake_summary else None,
            intake_submitted_at=intake_summary.submitted_at if intake_summary else None,
        )
    except PersonnelApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post("/{application_id}/cancel", response_model=PersonnelApplicationCancelOut)
def post_personnel_application_cancel(
    body: PersonnelApplicationCancelIn,
    application_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> PersonnelApplicationCancelOut:
    require_personnel_admin_or_403(user)
    user_id = _require_user_id(user)
    try:
        with engine.begin() as conn:
            result = cancel_application(
                conn,
                application_id=application_id,
                reason=body.reason,
                actor_user_id=user_id,
            )
        return PersonnelApplicationCancelOut(
            application_id=result.application_id,
            status=result.status,
            closed_at=result.closed_at,
            audit=lifecycle_audit_to_out(result.audit),
        )
    except PersonnelApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelApplicationLifecycleError as exc:
        raise _lifecycle_http422(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.get("/{application_id}/timeline", response_model=ApplicationTimelineOut)
def get_personnel_application_timeline(
    application_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> ApplicationTimelineOut:
    require_personnel_admin_or_403(user)
    try:
        with engine.connect() as conn:
            SqlAlchemyPersonnelApplicationRepository(conn).require_by_id(application_id)
            events = build_application_timeline(conn, application_id)
        return ApplicationTimelineOut(
            application_id=application_id,
            items=[timeline_event_to_out(event) for event in events],
        )
    except PersonnelApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.get("/{application_id}/lifecycle-audit", response_model=CombinedAuditListOut)
def get_personnel_application_lifecycle_audit(
    application_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> CombinedAuditListOut:
    require_personnel_admin_or_403(user)
    try:
        with engine.connect() as conn:
            SqlAlchemyPersonnelApplicationRepository(conn).require_by_id(application_id)
            items = list_combined_audit(conn, application_id)
        return CombinedAuditListOut(
            items=[CombinedAuditOut(**item) for item in items],
        )
    except PersonnelApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post("/{application_id}/director-resolution/open", response_model=DirectorResolutionActionOut)
def post_director_resolution_open(
    application_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> DirectorResolutionActionOut:
    require_personnel_admin_or_403(user)
    user_id = _require_user_id(user)
    try:
        with engine.begin() as conn:
            result = open_director_resolution(
                conn,
                application_id=application_id,
                actor_user_id=user_id,
            )
        return application_resolution_to_out(result)
    except PersonnelApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelApplicationResolutionError as exc:
        raise _resolution_http422(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post("/{application_id}/director-resolution", response_model=DirectorResolutionActionOut)
def post_director_resolution_record(
    body: DirectorResolutionRecordIn,
    application_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> DirectorResolutionActionOut:
    require_personnel_admin_or_403(user)
    user_id = _require_user_id(user)
    try:
        with engine.begin() as conn:
            result = record_director_resolution(
                conn,
                application_id=application_id,
                outcome=body.outcome,
                comment=body.comment,
                actor_user_id=user_id,
            )
        return application_resolution_to_out(result)
    except PersonnelApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelApplicationResolutionError as exc:
        raise _resolution_http422(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post("/{application_id}/director-resolution/change", response_model=DirectorResolutionActionOut)
def post_director_resolution_change(
    body: DirectorResolutionChangeIn,
    application_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> DirectorResolutionActionOut:
    require_personnel_admin_or_403(user)
    user_id = _require_user_id(user)
    try:
        with engine.begin() as conn:
            result = change_director_resolution(
                conn,
                application_id=application_id,
                outcome=body.outcome,
                comment=body.comment,
                actor_user_id=user_id,
            )
        return application_resolution_to_out(result)
    except PersonnelApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelApplicationResolutionError as exc:
        raise _resolution_http422(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post("/{application_id}/director-resolution/reopen", response_model=DirectorResolutionActionOut)
def post_director_resolution_reopen(
    application_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> DirectorResolutionActionOut:
    require_personnel_admin_or_403(user)
    user_id = _require_user_id(user)
    try:
        with engine.begin() as conn:
            result = reopen_director_resolution(
                conn,
                application_id=application_id,
                actor_user_id=user_id,
            )
        return application_resolution_to_out(result)
    except PersonnelApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelApplicationResolutionError as exc:
        raise _resolution_http422(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.get("/{application_id}/director-resolution/audit", response_model=ResolutionAuditListOut)
def get_director_resolution_audit(
    application_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> ResolutionAuditListOut:
    require_personnel_admin_or_403(user)
    try:
        with engine.connect() as conn:
            SqlAlchemyPersonnelApplicationRepository(conn).require_by_id(application_id)
            items = list_resolution_audit(conn, application_id)
        return ResolutionAuditListOut(items=[audit_to_out(item) for item in items])
    except PersonnelApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post("/{application_id}/hire-order-draft", response_model=HireOrderDraftOut)
def post_hire_order_draft(
    application_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> HireOrderDraftOut:
    require_personnel_admin_or_403(user)
    user_id = _require_user_id(user)
    try:
        with engine.begin() as conn:
            result = create_hire_order_draft_for_application(
                conn,
                application_id=application_id,
                created_by_user_id=user_id,
            )
        return HireOrderDraftOut(
            application_id=result.application_id,
            personnel_order_id=result.personnel_order_id,
            idempotent_replay=result.idempotent_replay,
            application_status=result.application_status,
        )
    except PersonnelApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelApplicationHireOrderError as exc:
        raise _hire_order_http422(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post("/{application_id}/apply", response_model=ApplicationApplyOut)
def post_application_apply(
    application_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> ApplicationApplyOut:
    require_personnel_admin_or_403(user)
    user_id = _require_user_id(user)
    try:
        with engine.begin() as conn:
            result = apply_hire_for_application(
                conn,
                application_id=application_id,
                created_by_user_id=user_id,
            )
        return ApplicationApplyOut(
            application_id=result.application_id,
            personnel_order_id=result.personnel_order_id,
            employee_id=result.employee_id,
            idempotent_replay=result.idempotent_replay,
            application_status=result.application_status,
        )
    except PersonnelApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PersonnelApplicationApplyError as exc:
        raise _apply_http422(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)
