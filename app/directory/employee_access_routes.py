"""WP-ACCESS-002 read-only employee account-access endpoints."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Path

from app.auth import get_current_user
from app.security.admin_permissions import USER_ACCESS_ADMIN, has_admin_permission
from app.services.employee_access_read_service import (
    EmployeeAccessReadError,
    get_employee_access_state,
    get_employee_termination_preview,
)

router = APIRouter()


def _require_user_access_admin(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if not has_admin_permission(int(user["user_id"]), USER_ACCESS_ADMIN):
        raise HTTPException(status_code=403, detail="Permission required: USER_ACCESS_ADMIN")
    return user


def _read_error(exc: EmployeeAccessReadError) -> HTTPException:
    status = 404 if exc.code == "EMPLOYEE_NOT_FOUND" else 409
    return HTTPException(status_code=status, detail={"code": exc.code, "message": str(exc)})


@router.get("/personnel/employees/{employee_id}/access")
def get_access_state(
    employee_id: int = Path(..., ge=1),
    _user: Dict[str, Any] = Depends(_require_user_access_admin),
) -> Dict[str, Any]:
    try:
        return get_employee_access_state(employee_id)
    except EmployeeAccessReadError as exc:
        raise _read_error(exc) from exc


@router.get("/personnel/employees/{employee_id}/access/termination-preview")
def get_termination_preview(
    employee_id: int = Path(..., ge=1),
    _user: Dict[str, Any] = Depends(_require_user_access_admin),
) -> Dict[str, Any]:
    try:
        return get_employee_termination_preview(employee_id)
    except EmployeeAccessReadError as exc:
        raise _read_error(exc) from exc
