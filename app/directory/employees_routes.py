# FILE: app/directory/employees_routes.py
from __future__ import annotations

from typing import Any, Dict, Optional, List

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.auth import get_current_user
from app.db.engine import engine

from app.services.directory_service import (
    list_departments as svc_list_departments,
    list_positions as svc_list_positions,
    list_employees as svc_list_employees,
    get_employee as svc_get_employee,
)

from .common import as_http500, call_service
from .rbac import compute_scope, require_privileged_or_403

router = APIRouter()


class DepartmentGroupCreateIn(BaseModel):
    code: Optional[str] = None
    group_name: str
    description: Optional[str] = None
    is_active: bool = True


class DepartmentGroupPatchIn(BaseModel):
    code: Optional[str] = None
    group_name: str
    description: Optional[str] = None
    is_active: bool = True


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
    try:
        _ = int(user["user_id"])
        _ = (status or "").strip().lower()

        sql = text(
            """
            SELECT role_id, code, name
            FROM public.roles
            ORDER BY role_id
            LIMIT :limit OFFSET :offset
            """
        )

        sql_total = text(
            """
            SELECT COUNT(*) AS cnt
            FROM public.roles
            """
        )

        with engine.begin() as c:
            rows = c.execute(sql, {"limit": int(limit), "offset": int(offset)}).mappings().all()
            total = int(c.execute(sql_total).scalar_one())

        return {
            "items": [
                {
                    "role_id": int(r["role_id"]),
                    "code": str(r["code"]) if r.get("code") is not None else None,
                    "name": str(r["name"]) if r.get("name") is not None else "",
                    "name_ru": None,
                    "is_active": True,
                }
                for r in rows
            ],
            "total": total,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)


@router.get("/department-groups")
def list_department_groups(
    status: str = Query(default="active", pattern="^(active|inactive|all)$"),
    limit: int = Query(default=500, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        _ = int(user["user_id"])
        _ = (status or "").strip().lower()

        sql = text(
            """
            SELECT group_id, group_name
            FROM public.deps_group
            ORDER BY group_id
            LIMIT :limit OFFSET :offset
            """
        )

        sql_total = text(
            """
            SELECT COUNT(*) AS cnt
            FROM public.deps_group
            """
        )

        with engine.begin() as c:
            rows = c.execute(sql, {"limit": int(limit), "offset": int(offset)}).mappings().all()
            total = int(c.execute(sql_total).scalar_one())

        return {
            "items": [
                {
                    "group_id": int(r["group_id"]),
                    "code": None,
                    "group_name": str(r["group_name"]) if r.get("group_name") is not None else "",
                    "is_active": True,
                }
                for r in rows
            ],
            "total": total,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)


@router.post("/department-groups")
def create_department_group(
    body: DepartmentGroupCreateIn,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        require_privileged_or_403(user)
        _ = int(user["user_id"])

        group_name = (body.group_name or "").strip()
        if not group_name:
            raise HTTPException(status_code=400, detail="group_name is required")

        sql = text(
            """
            INSERT INTO public.deps_group (group_name)
            VALUES (:group_name)
            RETURNING group_id, group_name
            """
        )

        with engine.begin() as c:
            row = c.execute(sql, {"group_name": group_name}).mappings().first()

        if not row:
            raise HTTPException(status_code=500, detail="create department group failed")

        return {
            "item": {
                "group_id": int(row["group_id"]),
                "code": None,
                "group_name": str(row["group_name"]) if row.get("group_name") is not None else "",
                "is_active": True,
            }
        }

    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Конфликт данных при создании группы отделений.")
    except Exception as e:
        raise as_http500(e)


@router.patch("/department-groups/{group_id}")
def update_department_group(
    group_id: int = Path(..., ge=1),
    body: DepartmentGroupPatchIn = None,  # type: ignore[assignment]
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        require_privileged_or_403(user)
        _ = int(user["user_id"])

        if body is None:
            raise HTTPException(status_code=400, detail="body is required")

        group_name = (body.group_name or "").strip()
        if not group_name:
            raise HTTPException(status_code=400, detail="group_name is required")

        sql = text(
            """
            UPDATE public.deps_group
            SET group_name = :group_name
            WHERE group_id = :group_id
            RETURNING group_id, group_name
            """
        )

        with engine.begin() as c:
            row = c.execute(
                sql,
                {
                    "group_id": int(group_id),
                    "group_name": group_name,
                },
            ).mappings().first()

        if not row:
            raise HTTPException(status_code=404, detail=f"department group not found: group_id={group_id}")

        return {
            "item": {
                "group_id": int(row["group_id"]),
                "code": None,
                "group_name": str(row["group_name"]) if row.get("group_name") is not None else "",
                "is_active": True,
            }
        }

    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Конфликт данных при обновлении группы отделений.")
    except Exception as e:
        raise as_http500(e)


@router.delete("/department-groups/{group_id}")
def delete_department_group(
    group_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        require_privileged_or_403(user)
        _ = int(user["user_id"])

        sql_exists = text(
            """
            SELECT 1
            FROM public.deps_group
            WHERE group_id = :group_id
            LIMIT 1
            """
        )

        sql_delete = text(
            """
            DELETE FROM public.deps_group
            WHERE group_id = :group_id
            """
        )

        with engine.begin() as c:
            exists = c.execute(sql_exists, {"group_id": int(group_id)}).first()
            if exists is None:
                raise HTTPException(status_code=404, detail=f"department group not found: group_id={group_id}")

            result = c.execute(sql_delete, {"group_id": int(group_id)})

        if not result.rowcount:
            raise HTTPException(status_code=404, detail=f"department group not found: group_id={group_id}")

        return {"ok": True}

    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="Нельзя удалить группу отделений, пока она используется в отделениях.",
        )
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