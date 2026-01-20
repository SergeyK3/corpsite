# FILE: app/directory.py

from __future__ import annotations

import inspect
import os
from typing import Any, Dict, Optional, Set, List

from fastapi import APIRouter, Header, HTTPException, Path, Query, Request

from app.db.engine import engine
from app.security.directory_scope import (
    rbac_mode as _rbac_mode,
    privileged_user_ids as _privileged_user_ids,
    privileged_role_ids as _privileged_role_ids,
    require_user_id as _require_user_id,
    load_user_ctx as _load_user_ctx,
    is_privileged as _is_privileged,
    require_dept_scope as _require_dept_scope,
)
from app.services.org_units_service import OrgUnitsService
from app.services.directory_service import (
    list_departments as svc_list_departments,
    list_positions as svc_list_positions,
    list_employees as svc_list_employees,
    get_employee as svc_get_employee,
)
from app.services.directory_import_csv import import_employees_csv_bytes
from app.services.directory_import_xlsx import import_employees_xlsx_bytes

router = APIRouter(prefix="/directory", tags=["directory"])

_org_units = OrgUnitsService(engine)


def _as_http500(e: Exception) -> HTTPException:
    return HTTPException(
        status_code=500,
        detail=f"directory error: {type(e).__name__}: {str(e)}",
    )


def _call_service(fn, **kwargs):
    """
    Safe adapter: passes only supported kwargs to service.
    This prevents runtime TypeError while service layer is being refactored.
    """
    sig = inspect.signature(fn)
    params = sig.parameters

    # if service has **kwargs -> pass everything
    for p in params.values():
        if p.kind == inspect.Parameter.VAR_KEYWORD:
            return fn(**kwargs)

    filtered = {k: v for k, v in kwargs.items() if k in params}
    return fn(**filtered)


def _compute_scope(
    uid: int,
    user_ctx: Dict[str, Any],
    include_inactive: bool = False,
) -> Dict[str, Any]:
    """
    Returns dict with:
      - privileged: bool
      - scope_unit_id: Optional[int]  (backward-compatible root unit for older services)
      - scope_unit_ids: Optional[List[int]] (preferred: root + descendants)
    """
    privileged = _is_privileged(user_ctx)

    # Default: no scope
    scope_unit_id: Optional[int] = None
    scope_unit_ids: Optional[List[int]] = None

    if _rbac_mode() == "dept" and not privileged:
        # Keep old behavior as fallback (root unit_id)
        scope_unit_id = _require_dept_scope(user_ctx)

        # Preferred: full scope (root + descendants)
        try:
            s: Optional[Set[int]] = _org_units.compute_user_scope_unit_ids(uid, include_inactive=include_inactive)
        except PermissionError as pe:
            raise HTTPException(status_code=403, detail=str(pe))

        if s is not None:
            scope_unit_ids = sorted(list(s))

    return {
        "privileged": bool(privileged),
        "scope_unit_id": scope_unit_id,
        "scope_unit_ids": scope_unit_ids,
    }


# ---------------------------
# Debug helpers (temporary)
# ---------------------------
@router.get("/_debug/rbac")
def debug_rbac(
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
) -> Dict[str, Any]:
    uid = _require_user_id(x_user_id)
    user_ctx = _load_user_ctx(uid)

    scope = _compute_scope(uid, user_ctx)

    return {
        "rbac_mode": _rbac_mode(),
        "env": {
            "DIRECTORY_RBAC_MODE": (os.getenv("DIRECTORY_RBAC_MODE") or ""),
            "DIRECTORY_PRIVILEGED_ROLE_IDS": (os.getenv("DIRECTORY_PRIVILEGED_ROLE_IDS") or ""),
            "DIRECTORY_PRIVILEGED_USER_IDS": (os.getenv("DIRECTORY_PRIVILEGED_USER_IDS") or ""),
            "DIRECTORY_PRIVILEGED_IDS": (os.getenv("DIRECTORY_PRIVILEGED_IDS") or ""),
        },
        "parsed": {
            "privileged_role_ids": sorted(list(_privileged_role_ids())),
            "privileged_user_ids": sorted(list(_privileged_user_ids())),
        },
        "user_ctx": {
            "user_id": int(user_ctx.get("user_id")),
            "role_id": int(user_ctx.get("role_id")) if user_ctx.get("role_id") is not None else None,
            "unit_id": int(user_ctx.get("unit_id")) if user_ctx.get("unit_id") is not None else None,
            "is_active": bool(user_ctx.get("is_active")),
        },
        "computed": {
            "is_privileged": bool(scope["privileged"]),
            "scope_unit_id": scope["scope_unit_id"],
            "scope_unit_ids": scope["scope_unit_ids"],
        },
    }


# ---------------------------
# Org structure (B1): UI tree + flat org units
# ---------------------------
@router.get("/org-units/tree")
def org_units_tree(
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    include_inactive: bool = Query(default=True),
) -> Dict[str, Any]:
    """
    UI Tree for corpsite-ui TreeView.
    - privileged/off -> forest of roots
    - dept-scoped user -> subtree rooted at user's unit (single root), if found
    """
    try:
        uid = _require_user_id(x_user_id)
        user_ctx = _load_user_ctx(uid)

        scope = _compute_scope(uid, user_ctx, include_inactive=include_inactive)
        scope_unit_id: Optional[int] = scope["scope_unit_id"]
        scope_unit_ids: Optional[List[int]] = scope["scope_unit_ids"]

        units = _org_units.list_org_units(scope_unit_ids=scope_unit_ids, include_inactive=include_inactive)
        items, inactive_ids, total = _org_units.build_ui_tree(units)

        # If user is dept-scoped -> return subtree rooted at scope_unit_id (if present)
        if scope_unit_id is not None:
            def find_node(nodes: List[Dict[str, Any]], target_id: str) -> Optional[Dict[str, Any]]:
                for n in nodes:
                    if str(n.get("id")) == target_id:
                        return n
                    got = find_node(n.get("children") or [], target_id)
                    if got is not None:
                        return got
                return None

            root = find_node(items, str(scope_unit_id))
            return {
                "version": 1,
                "total": total,
                "inactive_ids": inactive_ids,
                "items": [root] if root is not None else [],
                "root_id": int(scope_unit_id),
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
        raise _as_http500(e)


@router.get("/org-units")
def list_org_units_flat(
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    include_inactive: bool = Query(default=True),
) -> Dict[str, Any]:
    """
    Flat list of org units within RBAC scope (for admin tools / debugging).
    """
    try:
        uid = _require_user_id(x_user_id)
        user_ctx = _load_user_ctx(uid)
        scope = _compute_scope(uid, user_ctx, include_inactive=include_inactive)

        units = _org_units.list_org_units(scope_unit_ids=scope["scope_unit_ids"], include_inactive=include_inactive)
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
        raise _as_http500(e)


# Backward-compat alias (if you already used it somewhere)
@router.get("/departments/tree")
def departments_tree(
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    include_inactive: bool = Query(default=True),
) -> Dict[str, Any]:
    return org_units_tree(x_user_id=x_user_id, include_inactive=include_inactive)


# ---------------------------
# Dictionaries endpoints
# ---------------------------
@router.get("/departments")
def list_departments(
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
) -> Dict[str, Any]:
    try:
        uid = _require_user_id(x_user_id)
        user_ctx = _load_user_ctx(uid)

        scope = _compute_scope(uid, user_ctx)

        # Backward compatible (old services):
        dept_scope_id: Optional[int] = scope["scope_unit_id"]

        # Preferred (newer services may support):
        dept_scope_ids: Optional[List[int]] = scope["scope_unit_ids"]

        return _call_service(
            svc_list_departments,
            limit=limit,
            offset=offset,
            dept_scope_id=dept_scope_id,
            dept_scope_ids=dept_scope_ids,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise _as_http500(e)


@router.get("/positions")
def list_positions(
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
) -> Dict[str, Any]:
    try:
        _ = _require_user_id(x_user_id)
        return _call_service(svc_list_positions, limit=limit, offset=offset)

    except HTTPException:
        raise
    except Exception as e:
        raise _as_http500(e)


# ---------------------------
# Employees endpoints (service-driven)
# ---------------------------
@router.get("/employees")
def list_employees(
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    status: str = Query(default="active", pattern="^(active|inactive|all)$"),
    q: Optional[str] = Query(default=None),
    department_id: Optional[int] = Query(default=None, ge=1),
    position_id: Optional[int] = Query(default=None, ge=1),
    org_unit_id: Optional[int] = Query(default=None, ge=1),
    include_children: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort: Optional[str] = Query(default=None),
    order: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    try:
        uid = _require_user_id(x_user_id)
        user_ctx = _load_user_ctx(uid)

        scope = _compute_scope(uid, user_ctx)

        # Backward-compatible:
        scope_unit_id: Optional[int] = scope["scope_unit_id"]

        # Preferred:
        scope_unit_ids: Optional[List[int]] = scope["scope_unit_ids"]

        return _call_service(
            svc_list_employees,
            scope_unit_id=scope_unit_id,
            scope_unit_ids=scope_unit_ids,
            status=status,
            q=q,
            department_id=department_id,
            position_id=position_id,
            org_unit_id=org_unit_id,
            include_children=include_children,
            limit=limit,
            offset=offset,
            sort=sort,
            order=order,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise _as_http500(e)


@router.get("/employees/{employee_id}")
def get_employee(
    employee_id: str = Path(..., min_length=1),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
) -> Dict[str, Any]:
    try:
        uid = _require_user_id(x_user_id)
        user_ctx = _load_user_ctx(uid)

        scope = _compute_scope(uid, user_ctx)

        # Backward-compatible:
        scope_unit_id: Optional[int] = scope["scope_unit_id"]

        # Preferred:
        scope_unit_ids: Optional[List[int]] = scope["scope_unit_ids"]

        return _call_service(
            svc_get_employee,
            scope_unit_id=scope_unit_id,
            scope_unit_ids=scope_unit_ids,
            employee_id=employee_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise _as_http500(e)


# ---------------------------
# Import endpoints (privileged only)
# ---------------------------
@router.post("/import/employees_csv")
async def import_employees_csv(
    request: Request,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
) -> Dict[str, Any]:
    uid = _require_user_id(x_user_id)
    user_ctx = _load_user_ctx(uid)
    if not _is_privileged(user_ctx):
        raise HTTPException(status_code=403, detail="Forbidden.")

    try:
        raw = await request.body()
        return import_employees_csv_bytes(raw=raw)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"import error: {type(e).__name__}: {str(e)}")


@router.post("/import/employees_xlsx")
async def import_employees_xlsx(
    request: Request,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
) -> Dict[str, Any]:
    uid = _require_user_id(x_user_id)
    user_ctx = _load_user_ctx(uid)
    if not _is_privileged(user_ctx):
        raise HTTPException(status_code=403, detail="Forbidden.")

    try:
        raw = await request.body()
        return import_employees_xlsx_bytes(raw=raw)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"import xlsx error: {type(e).__name__}: {str(e)}")
