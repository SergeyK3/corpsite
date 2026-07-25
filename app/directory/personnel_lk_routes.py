"""Person-centric LK registry directory API."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.db.engine import engine
from app.directory.common import as_http500
from app.directory.personnel_lk_schemas import (
    PersonnelLkRegistryListOut,
    registry_row_to_out,
)
from app.directory.rbac import require_personnel_admin_or_403
from app.personnel_lk.application.registry_query_service import list_personnel_lk_registry

router = APIRouter(prefix="/personnel/lk", tags=["personnel-lk"])


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
