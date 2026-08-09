"""Person-centric LK registry directory API."""
from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from fastapi.responses import JSONResponse
from starlette.requests import Request
from starlette.responses import Response

from app.auth import get_current_user
from app.db.engine import engine
from app.directory.common import as_http500
from app.directory.personnel_lk_schemas import (
    ControlListRepairPreflightIn,
    ControlListRepairPreflightOut,
    PersonnelLkRegistryListOut,
    registry_row_to_out,
)
from app.directory.rbac import require_personnel_admin_or_403
from app.personnel_lk.application.control_list_repair_preflight_service import (
    control_list_repair_preflight,
)
from app.personnel_lk.application.personnel_order_evidence_fingerprint import (
    resolve_evidence_key_snapshot,
)
from app.personnel_lk.application.registry_query_service import list_personnel_lk_registry

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
