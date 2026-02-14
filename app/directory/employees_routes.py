# FILE: app/directory/employees_routes.py
from __future__ import annotations

from typing import Any, Dict, Optional, List

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import text

from app.auth import get_current_user
from app.db.engine import engine

from app.services.directory_service import (
    list_departments as svc_list_departments,
    list_positions as svc_list_positions,
    list_employees as svc_list_employees,
    get_employee as svc_get_employee,
)

from .common import as_http500, call_service
from .rbac import compute_scope

router = APIRouter()


@router.get("/departments")
def list_departments(
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        uid = int(user["user_id"])
        scope = compute_scope(uid, user)

        dept_scope_id: Optional[int] = scope["scope_unit_id"]
        dept_scope_ids: Optional[List[int]] = scope["scope_unit_ids"]

        return call_service(
            svc_list_departments,
            limit=limit,
            offset=offset,
            dept_scope_id=dept_scope_id,
            dept_scope_ids=dept_scope_ids,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)


@router.get("/positions")
def list_positions(
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        _ = int(user["user_id"])
        return call_service(svc_list_positions, limit=limit, offset=offset)

    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)


@router.get("/roles")
def list_roles(
    status: str = Query(default="active", pattern="^(active|inactive|all)$"),
    limit: int = Query(default=500, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Contract: {"items":[{"id": role_id, "code": "...", "name": "...", "is_active": true}]}

    NOTE: In your DB, public.roles has NO is_active column.
    We return is_active=True for all rows to keep UI contract stable.
    status is accepted but cannot be applied without the column.
    """
    try:
        _ = int(user["user_id"])
        _ = (status or "").strip().lower()  # keep accepted for compatibility

        sql = text(
            """
            SELECT role_id, code, name
            FROM public.roles
            ORDER BY role_id
            LIMIT :limit OFFSET :offset
            """
        )

        with engine.begin() as c:
            rows = c.execute(sql, {"limit": int(limit), "offset": int(offset)}).mappings().all()

        return {
            "items": [
                {
                    "id": int(r["role_id"]),
                    "code": str(r["code"]) if r.get("code") is not None else None,
                    "name": str(r["name"]) if r.get("name") is not None else "",
                    "is_active": True,
                }
                for r in rows
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)


@router.get("/employees")
def list_employees(
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
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        uid = int(user["user_id"])
        scope = compute_scope(uid, user)

        scope_unit_id: Optional[int] = scope["scope_unit_id"]
        scope_unit_ids: Optional[List[int]] = scope["scope_unit_ids"]

        return call_service(
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
        raise as_http500(e)


@router.get("/employees/{employee_id}")
def get_employee(
    employee_id: str = Path(..., min_length=1),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        uid = int(user["user_id"])
        scope = compute_scope(uid, user)

        scope_unit_id: Optional[int] = scope["scope_unit_id"]
        scope_unit_ids: Optional[List[int]] = scope["scope_unit_ids"]

        return call_service(
            svc_get_employee,
            scope_unit_id=scope_unit_id,
            scope_unit_ids=scope_unit_ids,
            employee_id=employee_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)
