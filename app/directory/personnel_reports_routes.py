"""Personnel reports preview and Excel endpoints."""
from __future__ import annotations

from io import BytesIO
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import StreamingResponse

from app.auth import get_current_user
from app.db.engine import engine
from app.services.personnel_reports_service import (
    assert_report_org_unit_accessible,
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


def _build_accessible_report(org_unit_id: int, user: dict[str, Any]) -> dict[str, Any]:
    scope = _scope(user)
    with engine.connect() as conn:
        org_unit = assert_report_org_unit_accessible(
            conn,
            org_unit_id=org_unit_id,
            scope_unit_ids=scope["scope_unit_ids"],
        )
    if org_unit is None:
        raise HTTPException(status_code=404, detail="Отделение недоступно или не найдено.")
    return build_personnel_roster(engine, org_unit=org_unit)


@router.get("/personnel-roster/{org_unit_id}")
def preview_personnel_roster(
    org_unit_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        return _build_accessible_report(org_unit_id, user)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.get("/personnel-roster/{org_unit_id}/excel")
def download_personnel_roster(
    org_unit_id: int = Path(..., ge=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> StreamingResponse:
    try:
        report = _build_accessible_report(org_unit_id, user)
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
