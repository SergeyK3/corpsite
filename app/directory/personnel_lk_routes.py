"""Person-centric LK registry directory API."""
from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from starlette.requests import Request
from starlette.responses import Response

from app.auth import get_current_user
from app.db.engine import engine
from app.directory.common import as_http500
from app.directory.personnel_lk_schemas import (
    ActiveEmployeePersonCardApplyIn,
    ActiveEmployeePersonCardApplyOut,
    ActiveEmployeePersonCardPreflightIn,
    ActiveEmployeePersonCardPreflightOut,
    ControlListRepairPreflightIn,
    ControlListRepairPreflightOut,
    PersonnelLkRegistryListOut,
    registry_row_to_out,
)
from app.directory.rbac import require_personnel_admin_or_403
from app.directory.rbac import compute_scope
from app.services.adr065_person_link_service import PersonLinkError, link_person_tx
from app.services.active_employee_person_card_service import (
    active_employee_person_card_preflight,
    create_active_employee_person_card_tx,
)
from app.directory.personnel_lk_schemas import PersonLinkApplyIn, PersonLinkApplyOut
from app.personnel_lk.application.control_list_repair_preflight_service import (
    control_list_repair_preflight,
)
from app.personnel_lk.application.personnel_order_evidence_fingerprint import (
    resolve_evidence_key_snapshot,
)
from app.personnel_lk.application.registry_query_service import list_personnel_lk_registry
from app.services import test_employee_cleanup_service as employee_cleanup

logger = logging.getLogger(__name__)


class _ControlListRepairSafeValidationRoute(APIRoute):
    """Redact request values only for the exact-IIN preflight validation surface."""

    def get_route_handler(self):
        original_handler = super().get_route_handler()

        async def safe_handler(request: Request) -> Response:
            try:
                return await original_handler(request)
            except RequestValidationError as exc:
                if request.url.path != "/directory/personnel/lk/control-list-repair/preflight":
                    raise
                safe_errors = [
                    {
                        key: error[key]
                        for key in ("type", "loc", "msg")
                        if key in error
                    }
                    for error in exc.errors()
                ]
                return JSONResponse(status_code=422, content={"detail": safe_errors})

        return safe_handler


router = APIRouter(
    prefix="/personnel/lk",
    tags=["personnel-lk"],
    route_class=_ControlListRepairSafeValidationRoute,
)


class TestEmployeeMarkIn(BaseModel):
    evidence: str = Field(min_length=12, max_length=1000)
    confirmed_name: str


class TestEmployeeDeleteIn(BaseModel):
    confirmation: str
    expected_snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class TestPersonnelOrderMarkIn(BaseModel):
    evidence: str
    confirmed_number: str


def _require_sysadmin(user: dict[str, Any]) -> int:
    if (int(user.get("role_id") or 0) != employee_cleanup.SYSTEM_ADMIN_ROLE_ID
            or user.get("is_sysadmin_assistant")):
        raise HTTPException(status_code=403, detail={
            "code": "SYSADMIN_REQUIRED", "message": "Операция доступна только системному администратору.",
        })
    return int(user["user_id"])


def _cleanup_error(exc: employee_cleanup.TestEmployeeCleanupError) -> HTTPException:
    return HTTPException(status_code=exc.status_code,
                         detail={"code": exc.code, "message": exc.message})


@router.get("/test-employees/{employee_id}/preview")
def test_employee_delete_preview_route(
    employee_id: int, user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    actor = _require_sysadmin(user)
    try:
        return employee_cleanup.preview(employee_id=employee_id, actor_user_id=actor)
    except employee_cleanup.TestEmployeeCleanupError as exc:
        raise _cleanup_error(exc) from None


@router.post("/test-employees/{employee_id}/mark")
def mark_test_employee_route(
    employee_id: int, body: TestEmployeeMarkIn,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    actor = _require_sysadmin(user)
    try:
        return employee_cleanup.mark_employee(
            employee_id=employee_id, actor_user_id=actor,
            evidence=body.evidence, confirmed_name=body.confirmed_name,
        )
    except employee_cleanup.TestEmployeeCleanupError as exc:
        raise _cleanup_error(exc) from None


@router.post("/test-employees/{employee_id}/orders/{order_id}/mark")
def mark_test_personnel_order_route(
    employee_id: int, order_id: int, body: TestPersonnelOrderMarkIn,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    actor = _require_sysadmin(user)
    try:
        return employee_cleanup.mark_personnel_order(
            employee_id=employee_id, order_id=order_id, actor_user_id=actor,
            evidence=body.evidence, confirmed_number=body.confirmed_number,
        )
    except employee_cleanup.TestEmployeeCleanupError as exc:
        raise _cleanup_error(exc) from None


@router.post("/test-employees/{employee_id}/delete")
def delete_test_employee_route(
    employee_id: int, body: TestEmployeeDeleteIn,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    actor = _require_sysadmin(user)
    try:
        return employee_cleanup.execute(
            employee_id=employee_id, actor_user_id=actor,
            confirmation=body.confirmation,
            expected_snapshot_hash=body.expected_snapshot_hash,
        )
    except employee_cleanup.TestEmployeeCleanupError as exc:
        raise _cleanup_error(exc) from None
    except SQLAlchemyError as exc:
        logger.error("test employee cleanup rolled back: %s", type(exc).__name__)
        raise HTTPException(status_code=409, detail={
            "code": "DELETE_ROLLED_BACK",
            "message": "Удаление не выполнено: база откатила операцию из-за связанной записи или блокировки.",
        }) from None


@router.post("/test-employees/file-cleanup/{deletion_id}/retry")
def retry_test_employee_files_route(
    deletion_id: str, user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, int]:
    actor = _require_sysadmin(user)
    try:
        return employee_cleanup.retry_file_cleanup(deletion_id=deletion_id, actor_user_id=actor)
    except employee_cleanup.TestEmployeeCleanupError as exc:
        raise _cleanup_error(exc) from None



@router.post(
    "/active-employee-card/preflight",
    response_model=ActiveEmployeePersonCardPreflightOut,
)
def active_employee_person_card_preflight_route(
    body: ActiveEmployeePersonCardPreflightIn,
    user: dict[str, Any] = Depends(get_current_user),
) -> ActiveEmployeePersonCardPreflightOut:
    """Read-only HR preflight; deliberately does not accept assignment intent."""
    require_personnel_admin_or_403(user)
    scope = compute_scope(int(user["user_id"]), user)
    scope_ids = None if scope.get("scope_unit_ids") is None else set(scope.get("scope_unit_ids") or [])
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            conn.exec_driver_sql("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            result = active_employee_person_card_preflight(
                conn, employee_id=body.employee_id, scope_unit_ids=scope_ids
            )
        finally:
            transaction.rollback()
    return ActiveEmployeePersonCardPreflightOut.model_validate(result)


@router.post(
    "/active-employee-card/apply",
    response_model=ActiveEmployeePersonCardApplyOut,
)
def active_employee_person_card_apply_route(
    body: ActiveEmployeePersonCardApplyIn,
    user: dict[str, Any] = Depends(get_current_user),
) -> ActiveEmployeePersonCardApplyOut:
    require_personnel_admin_or_403(user)
    scope = compute_scope(int(user["user_id"]), user)
    scope_ids = None if scope.get("scope_unit_ids") is None else set(scope.get("scope_unit_ids") or [])
    try:
        with engine.begin() as conn:
            result = create_active_employee_person_card_tx(
                conn,
                employee_id=body.employee_id,
                expected_precondition=body.expected_precondition,
                request_id=body.request_id,
                actor_user_id=int(user["user_id"]),
                hr_confirmed=body.hr_confirmed,
                scope_unit_ids=scope_ids,
            )
        return ActiveEmployeePersonCardApplyOut.model_validate(result)
    except PersonLinkError as exc:
        raise HTTPException(status_code=exc.status, detail={"code": exc.code, "message": str(exc)}) from None


@router.post("/control-list-repair/apply", response_model=PersonLinkApplyOut)
def control_list_repair_apply_route(
    body: PersonLinkApplyIn,
    user: dict[str, Any] = Depends(get_current_user),
) -> PersonLinkApplyOut:
    require_personnel_admin_or_403(user)
    scope = compute_scope(int(user["user_id"]), user)
    scope_ids = None if scope.get("scope_unit_ids") is None else set(scope.get("scope_unit_ids") or [])
    try:
        with engine.begin() as conn:
            result = link_person_tx(
                conn,
                employee_id=body.employee_id,
                normalized_record_ids=body.normalized_record_ids,
                expected_precondition=body.expected_precondition,
                request_id=body.request_id,
                actor_user_id=int(user["user_id"]),
                confirm_name_correction=body.confirm_name_correction,
                scope_unit_ids=scope_ids,
            )
        return PersonLinkApplyOut.model_validate(result)
    except PersonLinkError as exc:
        raise HTTPException(status_code=exc.status, detail={"code": exc.code, "message": str(exc)}) from None


@router.post(
    "/control-list-repair/preflight",
    response_model=ControlListRepairPreflightOut,
)
def control_list_repair_preflight_route(
    body: ControlListRepairPreflightIn,
    user: dict[str, Any] = Depends(get_current_user),
) -> ControlListRepairPreflightOut:
    require_personnel_admin_or_403(user)
    try:
        key_snapshot = None
        evidence = body.assignment_intent.evidence if body.assignment_intent else None
        if evidence is not None and evidence.evidence_type == "PERSONNEL_ORDER":
            if (
                evidence.evidence_profile_id is not None
                and evidence.evidence_profile_version is not None
                and evidence.evidence_key_id is not None
            ):
                try:
                    key_snapshot = resolve_evidence_key_snapshot(
                        profile_id=evidence.evidence_profile_id,
                        profile_version=evidence.evidence_profile_version,
                        key_id=evidence.evidence_key_id,
                    )
                except Exception:
                    key_snapshot = None
        with engine.connect() as conn:
            transaction = conn.begin()
            try:
                conn.exec_driver_sql(
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
                )
                result = control_list_repair_preflight(
                    conn,
                    iin=body.iin,
                    import_selection=(
                        body.import_selection.model_dump()
                        if body.import_selection is not None
                        else None
                    ),
                    assignment_intent=(
                        body.assignment_intent.model_dump()
                        if body.assignment_intent is not None
                        else None
                    ),
                    evidence_key_snapshot=key_snapshot,
                )
            finally:
                transaction.rollback()
        return ControlListRepairPreflightOut.model_validate(result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "control-list repair preflight failed error_type=%s",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail={
                "code": "CONTROL_LIST_REPAIR_PREFLIGHT_INTERNAL_ERROR",
                "message": "Control-list repair preflight is temporarily unavailable.",
            },
        ) from None


@router.get("", response_model=PersonnelLkRegistryListOut)
def list_personnel_lk_registry_route(
    q: str | None = Query(default=None),
    record_kind: Literal["employee", "applicant"] | None = Query(default=None),
    status: str = Query(default="active", pattern="^(active|inactive|all)$"),
    application_status: str | None = Query(default=None),
    org_group_id: int | None = Query(default=None, ge=1),
    org_unit_id: int | None = Query(default=None, ge=1),
    position_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: dict[str, Any] = Depends(get_current_user),
) -> PersonnelLkRegistryListOut:
    require_personnel_admin_or_403(user)
    try:
        with engine.begin() as conn:
            items, total = list_personnel_lk_registry(
                conn,
                q=q,
                record_kind=record_kind,
                status=status,
                application_status=application_status,
                org_group_id=org_group_id,
                org_unit_id=org_unit_id,
                position_id=position_id,
                limit=limit,
                offset=offset,
            )
        return PersonnelLkRegistryListOut(
            items=[registry_row_to_out(item) for item in items],
            total=total,
            limit=limit,
            offset=offset,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)
