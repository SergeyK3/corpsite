"""Personnel reports preview and Excel endpoints."""
from __future__ import annotations

from io import BytesIO
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import StreamingResponse

from app.auth import get_current_user
from app.db.engine import engine
from app.services.personnel_reports_service import (
    PersonnelReportAccessError,
    PersonnelReportFilterError,
    build_personnel_roster,
    build_personnel_roster_xlsx,
    list_report_org_options,
    roster_filename,
)

from .common import as_http500
from .rbac import compute_scope, require_personnel_visibility_or_403


router = APIRouter(prefix="/personnel/reports", tags=["personnel-reports"])


def _scope(user: dict[str, Any]) -> dict[str, Any]:
    scope = compute_scope(int(user["user_id"]), user, include_inactive=False)
    require_personnel_visibility_or_403(user, scope)
    return scope


@router.get("/options")
def get_report_options(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    try:
        scope = _scope(user)
        return list_report_org_options(engine, scope_unit_ids=scope["scope_unit_ids"])
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


def _build_accessible_report(
    user: dict[str, Any],
    *,
    group_id: int | None,
    org_unit_id: int | None,
) -> dict[str, Any]:
    scope = _scope(user)
    try:
        return build_personnel_roster(
            engine,
            scope_unit_ids=scope["scope_unit_ids"],
            group_id=group_id,
            org_unit_id=org_unit_id,
        )
    except PersonnelReportAccessError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PersonnelReportFilterError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/personnel-roster")
def preview_personnel_roster(
    group_id: int | None = Query(default=None, ge=1),
    org_unit_id: int | None = Query(default=None, ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        return _build_accessible_report(user, group_id=group_id, org_unit_id=org_unit_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.get("/personnel-roster/excel")
def download_personnel_roster(
    group_id: int | None = Query(default=None, ge=1),
    org_unit_id: int | None = Query(default=None, ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> StreamingResponse:
    try:
        report = _build_accessible_report(user, group_id=group_id, org_unit_id=org_unit_id)
        payload = build_personnel_roster_xlsx(report)
        filename = roster_filename(report)
        return StreamingResponse(
            BytesIO(payload),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.get("/personnel-roster/{org_unit_id}", include_in_schema=False)
def preview_personnel_roster_for_department(
    org_unit_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Keep the former department-only URL compatible with the shared service."""
    return preview_personnel_roster(group_id=None, org_unit_id=org_unit_id, user=user)


@router.get("/personnel-roster/{org_unit_id}/excel", include_in_schema=False)
def download_personnel_roster_for_department(
    org_unit_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> StreamingResponse:
    """Keep the former department-only Excel URL compatible."""
    return download_personnel_roster(group_id=None, org_unit_id=org_unit_id, user=user)
