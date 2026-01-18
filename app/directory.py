# app/directory.py
from __future__ import annotations

import inspect
import os
from typing import Any, Dict, List, Optional, Tuple, Set

from fastapi import APIRouter, Header, HTTPException, Path, Query
from sqlalchemy import text

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
from app.services.directory_service import (
    list_departments as svc_list_departments,
    list_positions as svc_list_positions,
    list_employees as svc_list_employees,
    get_employee as svc_get_employee,
)

router = APIRouter(prefix="/directory", tags=["directory"])


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


# ---------------------------
# Debug helpers (temporary)
# ---------------------------
@router.get("/_debug/rbac")
def debug_rbac(
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
) -> Dict[str, Any]:
    """
    Temporary diagnostic endpoint.
    Shows what backend actually sees in env and computed privileged flag.
    Remove after issue is resolved.
    """
    uid = _require_user_id(x_user_id)
    user_ctx = _load_user_ctx(uid)
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
            "is_privileged": bool(_is_privileged(user_ctx)),
        },
    }


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
        privileged = _is_privileged(user_ctx)

        dept_scope_id: Optional[int] = None
        if _rbac_mode() == "dept" and not privileged:
            # For departments dictionary: scope is the user's own unit_id (mapped to department dict id if applicable)
            dept_scope_id = _require_dept_scope(user_ctx)

        return _call_service(
            svc_list_departments,
            limit=limit,
            offset=offset,
            dept_scope_id=dept_scope_id,
            user_ctx=user_ctx,          # backward-compat if service still expects it
            privileged=privileged,      # backward-compat
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
        return _call_service(
            svc_list_positions,
            limit=limit,
            offset=offset,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise _as_http500(e)


# ---------------------------
# org_units endpoints (read-only)
# ---------------------------
@router.get("/org-units")
def list_org_units(
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    active: Optional[bool] = Query(default=True),
    q: Optional[str] = Query(default=None),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
) -> Dict[str, Any]:
    try:
        _ = _require_user_id(x_user_id)

        where: List[str] = []
        params: Dict[str, Any] = {"limit": limit, "offset": offset}

        if active is not None:
            where.append("is_active = :active")
            params["active"] = bool(active)

        if q:
            params["q"] = f"%{q.strip().lower()}%"
            where.append("(LOWER(name) LIKE :q OR LOWER(COALESCE(code,'')) LIKE :q)")

        where_sql = " AND ".join(where) if where else "TRUE"

        q_total = text("SELECT COUNT(*) AS cnt FROM public.org_units WHERE " + where_sql)
        q_list = text(
            f"""
            SELECT unit_id, name, code, parent_unit_id, is_active
            FROM public.org_units
            WHERE {where_sql}
            ORDER BY parent_unit_id NULLS FIRST, unit_id ASC
            LIMIT :limit OFFSET :offset
            """
        )

        with engine.begin() as conn:
            total = int(conn.execute(q_total, params).mappings().first()["cnt"])
            rows = conn.execute(q_list, params).mappings().all()

        items = [
            {
                "unit_id": int(r["unit_id"]),
                "name": r["name"],
                "code": r.get("code"),
                "parent_unit_id": (int(r["parent_unit_id"]) if r.get("parent_unit_id") is not None else None),
                "is_active": bool(r["is_active"]),
            }
            for r in rows
        ]

        return {"items": items, "total": total}

    except HTTPException:
        raise
    except Exception as e:
        raise _as_http500(e)


@router.get("/org-units/tree")
def org_units_tree(
    active: Optional[bool] = Query(default=True),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
) -> Dict[str, Any]:
    try:
        _ = _require_user_id(x_user_id)

        params: Dict[str, Any] = {}
        where_sql = "TRUE"
        if active is not None:
            where_sql = "is_active = :active"
            params["active"] = bool(active)

        q_list = text(
            f"""
            SELECT unit_id, name, code, parent_unit_id, is_active
            FROM public.org_units
            WHERE {where_sql}
            ORDER BY parent_unit_id NULLS FIRST, unit_id ASC
            """
        )

        with engine.begin() as conn:
            rows = conn.execute(q_list, params).mappings().all()

        nodes: Dict[int, Dict[str, Any]] = {}
        children_map: Dict[Optional[int], List[int]] = {}

        for r in rows:
            uid = int(r["unit_id"])
            pid = int(r["parent_unit_id"]) if r.get("parent_unit_id") is not None else None
            node = {
                "unit_id": uid,
                "name": r["name"],
                "code": r.get("code"),
                "parent_unit_id": pid,
                "is_active": bool(r["is_active"]),
                "children": [],
            }
            nodes[uid] = node
            children_map.setdefault(pid, []).append(uid)

        for pid, child_ids in children_map.items():
            if pid is None:
                continue
            if pid in nodes:
                nodes[pid]["children"] = [nodes[cid] for cid in child_ids if cid in nodes]

        roots = [nodes[cid] for cid in children_map.get(None, []) if cid in nodes]
        return {"items": roots, "total": len(nodes)}

    except HTTPException:
        raise
    except Exception as e:
        raise _as_http500(e)


@router.get("/org-units/{unit_id}/managers")
def org_unit_managers(
    unit_id: int = Path(..., ge=1),
    active: Optional[bool] = Query(default=True),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
) -> Dict[str, Any]:
    try:
        _ = _require_user_id(x_user_id)

        where: List[str] = ["m.unit_id = :unit_id"]
        params: Dict[str, Any] = {"unit_id": int(unit_id)}

        if active is not None:
            where.append("m.is_active = :active")
            params["active"] = bool(active)

        where_sql = " AND ".join(where)

        q_list = text(
            f"""
            SELECT
              m.manager_id,
              m.unit_id,
              m.user_id,
              m.manager_type,
              m.date_from,
              m.date_to,
              m.is_active,
              u.full_name AS user_full_name,
              u.role_id AS user_role_id,
              u.unit_id AS user_unit_id
            FROM public.org_unit_managers m
            JOIN public.users u ON u.user_id = m.user_id
            WHERE {where_sql}
            ORDER BY
              CASE WHEN m.manager_type = 'HEAD' THEN 0 ELSE 1 END,
              m.manager_id ASC
            """
        )

        with engine.begin() as conn:
            rows = conn.execute(q_list, params).mappings().all()

        items = [
            {
                "manager_id": int(r["manager_id"]),
                "unit_id": int(r["unit_id"]),
                "user": {
                    "user_id": int(r["user_id"]),
                    "full_name": r["user_full_name"],
                    "role_id": int(r["user_role_id"]) if r.get("user_role_id") is not None else None,
                    "unit_id": int(r["user_unit_id"]) if r.get("user_unit_id") is not None else None,
                },
                "manager_type": r["manager_type"],
                "date_from": r.get("date_from"),
                "date_to": r.get("date_to"),
                "is_active": bool(r["is_active"]),
            }
            for r in rows
        ]

        return {"items": items, "total": len(items)}

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
        privileged = _is_privileged(user_ctx)

        # RBAC scope for employees: org_units subtree by user's unit_id (dept mode, non-privileged)
        scope_unit_id: Optional[int] = None
        if _rbac_mode() == "dept" and not privileged:
            scope_unit_id = _require_dept_scope(user_ctx)

        return _call_service(
            svc_list_employees,
            # new-style (preferred)
            scope_unit_id=scope_unit_id,
            rbac_scope_unit_id=scope_unit_id,
            # old-style (backward-compat if service still expects ctx/privileged)
            user_ctx=user_ctx,
            privileged=privileged,
            # common filters
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
        privileged = _is_privileged(user_ctx)

        scope_unit_id: Optional[int] = None
        if _rbac_mode() == "dept" and not privileged:
            scope_unit_id = _require_dept_scope(user_ctx)

        return _call_service(
            svc_get_employee,
            # new-style (preferred)
            scope_unit_id=scope_unit_id,
            rbac_scope_unit_id=scope_unit_id,
            # old-style (backward-compat)
            user_ctx=user_ctx,
            privileged=privileged,
            # target
            employee_id=employee_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise _as_http500(e)
