# FILE: app/directory/employees_routes.py
from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional, List, Literal, Union

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.auth import get_current_user
from app.db.engine import engine
from app.security.directory_scope import is_privileged as _is_privileged

from app.services.directory_service import (
    list_departments as svc_list_departments,
    list_employees as svc_list_employees,
    get_employee as svc_get_employee,
    create_employee as svc_create_employee,
    terminate_employee as svc_terminate_employee,
    update_employee as svc_update_employee,
    transfer_employee as svc_transfer_employee,
    correct_employee_org_unit as svc_correct_employee_org_unit,
    correct_employee as svc_correct_employee,
    list_employee_events as svc_list_employee_events,
)
from app.services.hr_event_registry import list_registry_for_ui
from app.services.personnel_events_service import create_personnel_event

from .common import as_http500, call_service
from .rbac import compute_scope, require_privileged_or_403, require_personnel_visibility_or_403

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


class EmployeeCreateIn(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=500)
    org_unit_id: int = Field(..., ge=1)
    position_id: int = Field(..., ge=1)
    date_from: Optional[date] = None
    employment_rate: Optional[float] = Field(default=None, gt=0, le=2)
    department_id: Optional[int] = Field(default=None, ge=1)


class EmployeeTerminateIn(BaseModel):
    date_to: Optional[date] = None


class EmployeeUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: Optional[str] = Field(default=None, min_length=1, max_length=500)


class EmployeeTransferIn(BaseModel):
    to_org_unit_id: int = Field(..., ge=1)
    to_position_id: Optional[int] = Field(default=None, ge=1)
    to_employment_rate: Optional[float] = Field(default=None, gt=0, le=2)
    effective_date: date
    order_ref: Optional[str] = Field(default=None, max_length=500)
    comment: Optional[str] = Field(default=None, max_length=2000)


class EmployeeCorrectOrgUnitIn(BaseModel):
    to_org_unit_id: int = Field(..., ge=1)
    to_position_id: Optional[int] = Field(default=None, ge=1)
    effective_date: date
    comment: str = Field(..., min_length=1, max_length=2000)


class EmployeeCorrectGeneralIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: Literal["general"]
    full_name: str = Field(..., min_length=1, max_length=500)
    effective_date: date
    reason: str = Field(..., min_length=1, max_length=500)
    comment: str = Field(..., min_length=1, max_length=2000)


class EmployeeCorrectAssignmentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: Literal["assignment"]
    org_unit_id: int = Field(..., ge=1)
    position_id: Optional[int] = Field(default=None, ge=1)
    employment_rate: Optional[float] = Field(default=None, gt=0, le=2)
    date_from: Optional[date] = Field(...)
    date_to: Optional[date] = None
    effective_date: date
    reason: str = Field(..., min_length=1, max_length=500)
    comment: str = Field(..., min_length=1, max_length=2000)


EmployeeCorrectIn = Union[EmployeeCorrectGeneralIn, EmployeeCorrectAssignmentIn]


class PersonnelEventCreateIn(BaseModel):
    event_type: str = Field(..., min_length=1, max_length=50)
    to_org_unit_id: Optional[int] = Field(default=None, ge=1)
    to_position_id: Optional[int] = Field(default=None, ge=1)
    to_rate: Optional[float] = Field(default=None, gt=0, le=2)
    to_employment_rate: Optional[float] = Field(default=None, gt=0, le=2)
    effective_date: date
    order_ref: Optional[str] = Field(default=None, max_length=500)
    comment: Optional[str] = Field(default=None, max_length=2000)
    metadata: Optional[Dict[str, Any]] = None


def _map_department_group_row(row: Dict[str, Any]) -> Dict[str, Any]:
    from app.medical_org_groups import department_group_api_row

    return department_group_api_row(
        int(row["group_id"]),
        db_group_name=str(row["group_name"]) if row.get("group_name") is not None else None,
    )


@router.get("/departments")
def list_departments(
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        uid = int(user["user_id"])
        scope = compute_scope(uid, user)
        require_personnel_visibility_or_403(user, scope)

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
            "items": [_map_department_group_row(r) for r in rows],
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

        return {"item": _map_department_group_row(row)}

    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Конфликт данных при создании группы отделений.")
    except Exception as e:
        raise as_http500(e)


@router.patch("/department-groups/{group_id}")
def update_department_group(
    group_id: int = Path(..., ge=1),
    body: DepartmentGroupPatchIn = ...,
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

        return {"item": _map_department_group_row(row)}

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
    org_group_id: Optional[int] = Query(
        default=None,
        ge=1,
        description="Filter by top-level org group of employee's org unit.",
    ),
    org_unit_id: Optional[int] = Query(default=None, ge=1),
    include_children: bool = Query(default=False),
    include_applicants: bool = Query(
        default=False,
        description="Include PPR applicants (CANDIDATE without active employee) in roster.",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort: Optional[str] = Query(default=None),
    order: Optional[str] = Query(default=None),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        uid = int(user["user_id"])
        scope = compute_scope(uid, user)
        require_personnel_visibility_or_403(user, scope)

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
            org_group_id=org_group_id,
            org_unit_id=org_unit_id,
            include_children=include_children,
            include_applicants=include_applicants,
            limit=limit,
            offset=offset,
            sort=sort,
            order=order,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)


@router.post("/employees", status_code=201)
def create_employee(
    body: EmployeeCreateIn,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        if not _is_privileged(user):
            raise HTTPException(status_code=403, detail="Forbidden.")

        q_org_unit = text(
            """
            SELECT unit_id
            FROM public.org_units
            WHERE unit_id = :org_unit_id
            LIMIT 1
            """
        )
        q_position = text(
            """
            SELECT position_id
            FROM public.positions
            WHERE position_id = :position_id
            LIMIT 1
            """
        )
        q_department = text(
            """
            SELECT department_id
            FROM public.departments
            WHERE department_id = :department_id
            LIMIT 1
            """
        )

        with engine.begin() as conn:
            org_row = conn.execute(q_org_unit, {"org_unit_id": int(body.org_unit_id)}).first()
            if org_row is None:
                raise HTTPException(status_code=404, detail="Org unit not found.")

            pos_row = conn.execute(q_position, {"position_id": int(body.position_id)}).first()
            if pos_row is None:
                raise HTTPException(status_code=404, detail="Position not found.")

            if body.department_id is not None:
                dept_row = conn.execute(
                    q_department,
                    {"department_id": int(body.department_id)},
                ).first()
                if dept_row is None:
                    raise HTTPException(status_code=404, detail="Department not found.")

        new_employee_id = call_service(
            svc_create_employee,
            full_name=body.full_name,
            org_unit_id=body.org_unit_id,
            position_id=body.position_id,
            date_from=body.date_from,
            employment_rate=body.employment_rate,
            department_id=body.department_id,
            created_by=int(user["user_id"]),
        )

        return call_service(
            svc_get_employee,
            scope_unit_id=None,
            scope_unit_ids=None,
            employee_id=new_employee_id,
        )

    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Unable to create employee.")
    except Exception as e:
        raise as_http500(e)


@router.patch("/employees/{employee_id}")
def update_employee(
    employee_id: str = Path(..., min_length=1),
    body: EmployeeUpdateIn = ...,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        if not _is_privileged(user):
            raise HTTPException(status_code=403, detail="Forbidden.")

        if body.model_dump(exclude_unset=True) == {}:
            raise HTTPException(status_code=422, detail="At least one field is required.")

        updates = body.model_dump(exclude_unset=True)

        call_service(
            svc_update_employee,
            employee_id=employee_id,
            full_name=updates.get("full_name"),
            employment_rate=None,
            date_from=None,
            position_id=None,
        )

        return call_service(
            svc_get_employee,
            scope_unit_id=None,
            scope_unit_ids=None,
            employee_id=employee_id,
        )

    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Unable to update employee.")
    except Exception as e:
        raise as_http500(e)


@router.post("/employees/{employee_id}/terminate")
def terminate_employee(
    employee_id: str = Path(..., min_length=1),
    body: Optional[EmployeeTerminateIn] = None,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        if not _is_privileged(user):
            raise HTTPException(status_code=403, detail="Forbidden.")

        date_to = body.date_to if body is not None else None

        call_service(
            svc_terminate_employee,
            employee_id=employee_id,
            date_to=date_to,
            created_by=int(user["user_id"]),
        )

        return call_service(
            svc_get_employee,
            scope_unit_id=None,
            scope_unit_ids=None,
            employee_id=employee_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)


@router.get("/hr-event-registry")
def get_hr_event_registry(
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        if not _is_privileged(user):
            raise HTTPException(status_code=403, detail="Forbidden.")
        return {"items": list_registry_for_ui()}
    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)


@router.post("/employees/{employee_id}/personnel-events")
def create_personnel_event_route(
    employee_id: str = Path(..., min_length=1),
    body: PersonnelEventCreateIn = ...,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        if not _is_privileged(user):
            raise HTTPException(status_code=403, detail="Forbidden.")

        payload = body.model_dump(exclude={"event_type"}, exclude_none=False)
        event = call_service(
            create_personnel_event,
            employee_id=employee_id,
            event_type=body.event_type,
            payload=payload,
            created_by=int(user["user_id"]),
        )

        item = call_service(
            svc_get_employee,
            scope_unit_id=None,
            scope_unit_ids=None,
            employee_id=employee_id,
        )

        return {"item": item, "event": event}

    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Unable to create personnel event.")
    except Exception as e:
        raise as_http500(e)


@router.post("/employees/{employee_id}/transfer")
def transfer_employee(
    employee_id: str = Path(..., min_length=1),
    body: EmployeeTransferIn = ...,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        if not _is_privileged(user):
            raise HTTPException(status_code=403, detail="Forbidden.")

        event = call_service(
            svc_transfer_employee,
            employee_id=employee_id,
            to_org_unit_id=body.to_org_unit_id,
            to_position_id=body.to_position_id,
            to_employment_rate=body.to_employment_rate,
            effective_date=body.effective_date,
            order_ref=body.order_ref,
            comment=body.comment,
            created_by=int(user["user_id"]),
        )

        item = call_service(
            svc_get_employee,
            scope_unit_id=None,
            scope_unit_ids=None,
            employee_id=employee_id,
        )

        return {"item": item, "event": event}

    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Unable to transfer employee.")
    except Exception as e:
        raise as_http500(e)


@router.post("/employees/{employee_id}/correct")
def correct_employee(
    employee_id: str = Path(..., min_length=1),
    body: EmployeeCorrectGeneralIn | EmployeeCorrectAssignmentIn = ...,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        if not _is_privileged(user):
            raise HTTPException(status_code=403, detail="Forbidden.")

        if isinstance(body, EmployeeCorrectGeneralIn):
            event = call_service(
                svc_correct_employee,
                employee_id=employee_id,
                domain="general",
                full_name=body.full_name,
                effective_date=body.effective_date,
                reason=body.reason,
                comment=body.comment,
                created_by=int(user["user_id"]),
            )
        else:
            event = call_service(
                svc_correct_employee,
                employee_id=employee_id,
                domain="assignment",
                org_unit_id=body.org_unit_id,
                position_id=body.position_id,
                employment_rate=body.employment_rate,
                date_from=body.date_from,
                date_to=body.date_to,
                effective_date=body.effective_date,
                reason=body.reason,
                comment=body.comment,
                created_by=int(user["user_id"]),
            )

        item = call_service(
            svc_get_employee,
            scope_unit_id=None,
            scope_unit_ids=None,
            employee_id=employee_id,
        )

        return {"item": item, "event": event}

    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Unable to correct employee.")
    except Exception as e:
        raise as_http500(e)


@router.post("/employees/{employee_id}/correct-org-unit")
def correct_employee_org_unit(
    employee_id: str = Path(..., min_length=1),
    body: EmployeeCorrectOrgUnitIn = ...,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        if not _is_privileged(user):
            raise HTTPException(status_code=403, detail="Forbidden.")

        event = call_service(
            svc_correct_employee_org_unit,
            employee_id=employee_id,
            to_org_unit_id=body.to_org_unit_id,
            to_position_id=body.to_position_id,
            effective_date=body.effective_date,
            comment=body.comment,
            created_by=int(user["user_id"]),
        )

        item = call_service(
            svc_get_employee,
            scope_unit_id=None,
            scope_unit_ids=None,
            employee_id=employee_id,
        )

        return {"item": item, "event": event}

    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Unable to correct employee org unit.")
    except Exception as e:
        raise as_http500(e)


@router.get("/employees/{employee_id}/events")
def list_employee_events(
    employee_id: str = Path(..., min_length=1),
    event_type: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        if not _is_privileged(user):
            raise HTTPException(status_code=403, detail="Forbidden.")

        return call_service(
            svc_list_employee_events,
            employee_id=employee_id,
            event_type=event_type,
            limit=limit,
            offset=offset,
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
        require_personnel_visibility_or_403(user, scope)

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