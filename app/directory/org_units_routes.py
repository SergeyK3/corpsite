# FILE: app/directory/org_units_routes.py
from __future__ import annotations

from typing import Any, Dict, Optional, List

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel

from app.auth import get_current_user  # JWT
from .common import as_http500
from .rbac import compute_scope, require_privileged_or_403, load_ancestor_chain_units, org_units
from app.services.org_units_service import OrgUnit

router = APIRouter()


@router.get("/org-units/tree")
def org_units_tree(
    include_inactive: bool = Query(default=True),
    status: Optional[str] = Query(default=None),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        if status is not None:
            s = status.strip().lower()
            if s == "active":
                include_inactive = False
            elif s == "all":
                include_inactive = True

        uid = int(user["user_id"])
        user_ctx = user  # compat with existing RBAC helpers

        scope = compute_scope(uid, user_ctx, include_inactive=include_inactive)
        scope_unit_id: Optional[int] = scope["scope_unit_id"]
        scope_unit_ids: Optional[List[int]] = scope["scope_unit_ids"]

        units = org_units.list_org_units(scope_unit_ids=scope_unit_ids, include_inactive=include_inactive)

        top_id: Optional[int] = None
        if scope_unit_id is not None:
            chain = load_ancestor_chain_units(leaf_unit_id=int(scope_unit_id), include_inactive=include_inactive)

            merged: Dict[int, OrgUnit] = {u.unit_id: u for u in units}
            for u in chain:
                merged.setdefault(u.unit_id, u)
            units = list(merged.values())

            root_candidates = [u for u in chain if u.parent_unit_id is None]
            top_id = int(root_candidates[0].unit_id) if root_candidates else int(scope_unit_id)

        items, inactive_ids, total = org_units.build_ui_tree(units)

        def find_node(nodes: List[Dict[str, Any]], target_id: str) -> Optional[Dict[str, Any]]:
            for n in nodes:
                if str(n.get("id")) == target_id:
                    return n
                got = find_node(n.get("children") or [], target_id)
                if got is not None:
                    return got
            return None

        if scope_unit_id is not None:
            root_node: Optional[Dict[str, Any]] = None
            if top_id is not None:
                root_node = find_node(items, str(top_id))
            if root_node is None:
                root_node = find_node(items, str(scope_unit_id))

            root_id_out: Optional[int] = None
            if root_node is not None and root_node.get("id") is not None:
                try:
                    root_id_out = int(root_node["id"])
                except Exception:
                    root_id_out = int(scope_unit_id)
            else:
                root_id_out = int(scope_unit_id)

            return {
                "version": 1,
                "total": total,
                "inactive_ids": inactive_ids,
                "items": [root_node] if root_node is not None else [],
                "root_id": root_id_out,
            }

        return {
            "version": 1,
            "total": total,
            "inactive_ids": inactive_ids,
            "items": items,
            "root_id": None,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)


@router.get("/org-units")
def list_org_units_flat(
    include_inactive: bool = Query(default=True),
    status: Optional[str] = Query(default=None),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        if status is not None:
            s = status.strip().lower()
            if s == "active":
                include_inactive = False
            elif s == "all":
                include_inactive = True

        uid = int(user["user_id"])
        user_ctx = user
        scope = compute_scope(uid, user_ctx, include_inactive=include_inactive)

        units = org_units.list_org_units(scope_unit_ids=scope["scope_unit_ids"], include_inactive=include_inactive)
        return {
            "items": [
                {
                    "id": u.unit_id,
                    "parent_id": u.parent_unit_id,
                    "name": u.name,
                    "code": u.code,
                    "is_active": u.is_active,
                }
                for u in units
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)


@router.get("/departments/tree")
def departments_tree(
    include_inactive: bool = Query(default=True),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    return org_units_tree(include_inactive=include_inactive, status=None, user=user)


class OrgUnitRenameIn(BaseModel):
    name: str


class OrgUnitMoveIn(BaseModel):
    parent_unit_id: Optional[int] = None


class OrgUnitCreateIn(BaseModel):
    name: str
    parent_unit_id: Optional[int] = None
    code: Optional[str] = None
    is_active: bool = True


@router.patch("/org-units/{unit_id}/rename")
async def org_unit_rename(
    unit_id: int = Path(..., ge=1),
    body: OrgUnitRenameIn = None,  # type: ignore[assignment]
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        if body is None or not getattr(body, "name", None):
            raise HTTPException(status_code=400, detail="name is required")

        user_ctx = user
        require_privileged_or_403(user_ctx)

        uid = int(user["user_id"])
        _ = compute_scope(uid, user_ctx, include_inactive=True)

        u = org_units.rename_org_unit(unit_id=int(unit_id), new_name=body.name)
        return {"item": {"id": u.unit_id, "parent_id": u.parent_unit_id, "name": u.name, "code": u.code, "is_active": u.is_active}}

    except HTTPException:
        raise
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise as_http500(e)


@router.patch("/org-units/{unit_id}")
async def org_unit_patch_compat(
    unit_id: int = Path(..., ge=1),
    body: OrgUnitRenameIn = None,  # type: ignore[assignment]
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    return await org_unit_rename(unit_id=unit_id, body=body, user=user)


@router.patch("/org-units/{unit_id}/move")
async def org_unit_move(
    unit_id: int = Path(..., ge=1),
    body: OrgUnitMoveIn = None,  # type: ignore[assignment]
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        if body is None:
            raise HTTPException(status_code=400, detail="body is required")

        user_ctx = user
        require_privileged_or_403(user_ctx)

        uid = int(user["user_id"])
        _ = compute_scope(uid, user_ctx, include_inactive=True)

        u = org_units.move_org_unit(unit_id=int(unit_id), parent_unit_id=body.parent_unit_id)
        return {"item": {"id": u.unit_id, "parent_id": u.parent_unit_id, "name": u.name, "code": u.code, "is_active": u.is_active}}

    except HTTPException:
        raise
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise as_http500(e)


@router.patch("/org-units/{unit_id}/deactivate")
async def org_unit_deactivate(
    unit_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        user_ctx = user
        require_privileged_or_403(user_ctx)

        uid = int(user["user_id"])
        _ = compute_scope(uid, user_ctx, include_inactive=True)

        u = org_units.deactivate_org_unit(unit_id=int(unit_id))
        return {"item": {"id": u.unit_id, "parent_id": u.parent_unit_id, "name": u.name, "code": u.code, "is_active": u.is_active}}

    except HTTPException:
        raise
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise as_http500(e)


@router.patch("/org-units/{unit_id}/activate")
async def org_unit_activate(
    unit_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        user_ctx = user
        require_privileged_or_403(user_ctx)

        uid = int(user["user_id"])
        _ = compute_scope(uid, user_ctx, include_inactive=True)

        u = org_units.activate_org_unit(unit_id=int(unit_id))
        return {"item": {"id": u.unit_id, "parent_id": u.parent_unit_id, "name": u.name, "code": u.code, "is_active": u.is_active}}

    except HTTPException:
        raise
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise as_http500(e)


@router.post("/org-units")
async def org_unit_create(
    body: OrgUnitCreateIn = None,  # type: ignore[assignment]
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        if body is None or not getattr(body, "name", None):
            raise HTTPException(status_code=400, detail="name is required")

        user_ctx = user
        require_privileged_or_403(user_ctx)

        uid = int(user["user_id"])
        _ = compute_scope(uid, user_ctx, include_inactive=True)

        u = org_units.create_org_unit(
            name=body.name,
            parent_unit_id=body.parent_unit_id,
            code=body.code,
            is_active=bool(body.is_active),
        )
        return {"item": {"id": u.unit_id, "parent_id": u.parent_unit_id, "name": u.name, "code": u.code, "is_active": u.is_active}}

    except HTTPException:
        raise
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise as_http500(e)
