# FILE: app/api/admin_org_units_routes.py
"""Sysadmin CRUD for org_units dictionary."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field

from app.security.admin_guard import require_sysadmin_api
from app.services.org_units_admin_service import (
    OrgUnitDeleteRejected,
    activate_admin_org_unit,
    bulk_delete_admin_org_units,
    check_org_unit_dependencies,
    create_admin_org_unit,
    deactivate_admin_org_unit,
    delete_admin_org_unit,
    get_admin_org_unit,
    list_admin_org_units,
    preview_bulk_delete_admin_org_units,
    update_admin_org_unit,
)

router = APIRouter(prefix="/org-units", tags=["admin-org-units"])


def _lookup_to_404(exc: LookupError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


def _value_to_400(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


class AdminOrgUnitCreateIn(BaseModel):
    name: str = Field(..., min_length=1)
    parent_unit_id: Optional[int] = Field(default=None, ge=1)
    group_id: int = Field(..., ge=1)
    code: Optional[str] = None
    is_active: bool = True
    allow_duplicate: bool = False


class AdminOrgUnitUpdateIn(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1)
    code: Optional[str] = None
    group_id: Optional[int] = Field(default=None, ge=1)
    parent_unit_id: Optional[int] = Field(default=None, ge=1)
    is_active: Optional[bool] = None
    allow_duplicate: bool = False
    clear_parent: bool = False


class AdminOrgUnitBulkDeleteIn(BaseModel):
    unit_ids: List[int] = Field(..., min_length=1, max_length=200)


@router.get("")
def admin_list_org_units(
    q: Optional[str] = Query(default=None),
    org_group_id: Optional[int] = Query(default=None, ge=1),
    parent_unit_id: Optional[int] = Query(default=None, ge=1),
    status: str = Query(default="all"),
    roots_only: bool = Query(default=False),
    without_employees: bool = Query(default=False),
    deletable_only: bool = Query(default=False),
    limit: int = Query(default=500, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    _admin: Dict[str, Any] = Depends(require_sysadmin_api),
) -> Dict[str, Any]:
    if status not in ("active", "inactive", "all"):
        raise HTTPException(status_code=400, detail="status must be active, inactive, or all")
    return list_admin_org_units(
        q=q,
        org_group_id=org_group_id,
        parent_unit_id=parent_unit_id,
        status=status,
        roots_only=roots_only,
        without_employees=without_employees,
        deletable_only=deletable_only,
        limit=limit,
        offset=offset,
    )


@router.post("")
def admin_create_org_unit(
    body: AdminOrgUnitCreateIn,
    admin: Dict[str, Any] = Depends(require_sysadmin_api),
) -> Dict[str, Any]:
    try:
        return create_admin_org_unit(
            actor_user_id=int(admin["user_id"]),
            name=body.name,
            parent_unit_id=body.parent_unit_id,
            group_id=body.group_id,
            code=body.code,
            is_active=body.is_active,
            allow_duplicate=body.allow_duplicate,
        )
    except LookupError as exc:
        raise _lookup_to_404(exc) from exc
    except ValueError as exc:
        raise _value_to_400(exc) from exc


@router.post("/bulk-delete/preview")
def admin_preview_bulk_delete_org_units(
    body: AdminOrgUnitBulkDeleteIn,
    _admin: Dict[str, Any] = Depends(require_sysadmin_api),
) -> Dict[str, Any]:
    return preview_bulk_delete_admin_org_units(unit_ids=body.unit_ids)


@router.post("/bulk-delete")
def admin_bulk_delete_org_units(
    body: AdminOrgUnitBulkDeleteIn,
    admin: Dict[str, Any] = Depends(require_sysadmin_api),
) -> Dict[str, Any]:
    return bulk_delete_admin_org_units(
        actor_user_id=int(admin["user_id"]),
        unit_ids=body.unit_ids,
    )


@router.get("/{unit_id}")
def admin_get_org_unit(
    unit_id: int = Path(..., ge=1),
    _admin: Dict[str, Any] = Depends(require_sysadmin_api),
) -> Dict[str, Any]:
    try:
        return get_admin_org_unit(int(unit_id))
    except LookupError as exc:
        raise _lookup_to_404(exc) from exc


@router.get("/{unit_id}/dependencies")
def admin_get_org_unit_dependencies(
    unit_id: int = Path(..., ge=1),
    _admin: Dict[str, Any] = Depends(require_sysadmin_api),
) -> Dict[str, Any]:
    try:
        _ = get_admin_org_unit(int(unit_id))
    except LookupError as exc:
        raise _lookup_to_404(exc) from exc
    return check_org_unit_dependencies(int(unit_id)).to_dict()


@router.patch("/{unit_id}")
def admin_update_org_unit(
    unit_id: int = Path(..., ge=1),
    body: AdminOrgUnitUpdateIn = None,  # type: ignore[assignment]
    admin: Dict[str, Any] = Depends(require_sysadmin_api),
) -> Dict[str, Any]:
    if body is None:
        raise HTTPException(status_code=400, detail="body is required")
    parent_kw: Dict[str, Any] = {}
    if body.clear_parent:
        parent_kw["parent_unit_id"] = None
    elif body.parent_unit_id is not None:
        parent_kw["parent_unit_id"] = body.parent_unit_id
    try:
        return update_admin_org_unit(
            actor_user_id=int(admin["user_id"]),
            unit_id=int(unit_id),
            name=body.name,
            code=body.code,
            group_id=body.group_id,
            is_active=body.is_active,
            allow_duplicate=body.allow_duplicate,
            **parent_kw,
        )
    except LookupError as exc:
        raise _lookup_to_404(exc) from exc
    except ValueError as exc:
        raise _value_to_400(exc) from exc


@router.post("/{unit_id}/activate")
def admin_activate_org_unit(
    unit_id: int = Path(..., ge=1),
    admin: Dict[str, Any] = Depends(require_sysadmin_api),
) -> Dict[str, Any]:
    try:
        return activate_admin_org_unit(
            actor_user_id=int(admin["user_id"]),
            unit_id=int(unit_id),
        )
    except LookupError as exc:
        raise _lookup_to_404(exc) from exc
    except ValueError as exc:
        raise _value_to_400(exc) from exc


@router.post("/{unit_id}/deactivate")
def admin_deactivate_org_unit(
    unit_id: int = Path(..., ge=1),
    admin: Dict[str, Any] = Depends(require_sysadmin_api),
) -> Dict[str, Any]:
    try:
        return deactivate_admin_org_unit(
            actor_user_id=int(admin["user_id"]),
            unit_id=int(unit_id),
        )
    except LookupError as exc:
        raise _lookup_to_404(exc) from exc
    except ValueError as exc:
        raise _value_to_400(exc) from exc


@router.delete("/{unit_id}")
def admin_delete_org_unit(
    unit_id: int = Path(..., ge=1),
    admin: Dict[str, Any] = Depends(require_sysadmin_api),
) -> Dict[str, Any]:
    try:
        return delete_admin_org_unit(
            actor_user_id=int(admin["user_id"]),
            unit_id=int(unit_id),
        )
    except LookupError as exc:
        raise _lookup_to_404(exc) from exc
    except OrgUnitDeleteRejected as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "ORG_UNIT_HAS_DEPENDENCIES",
                "unit_id": exc.unit_id,
                "dependencies": exc.dependencies,
            },
        ) from exc
    except ValueError as exc:
        raise _value_to_400(exc) from exc

