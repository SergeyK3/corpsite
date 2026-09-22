"""WP-ACCESS-002 read-only employee account-access endpoints."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from app.auth import get_current_user
from app.security.admin_permissions import USER_ACCESS_ADMIN, has_admin_permission
from app.services.employee_access_read_service import (
    EmployeeAccessReadError,
    get_employee_access_state,
    get_employee_termination_preview,
)
from app.services.admin_password_reset_service import AdminPasswordResetError, issue_temporary_password, issue_temporary_password_for_user, search_users_for_access
from app.services.user_activation_service import UserActivationError, activate_user

router = APIRouter()


def _require_user_access_admin(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if not has_admin_permission(int(user["user_id"]), USER_ACCESS_ADMIN):
        raise HTTPException(status_code=403, detail="Permission required: USER_ACCESS_ADMIN")
    return user


def _read_error(exc: EmployeeAccessReadError) -> HTTPException:
    status = 404 if exc.code == "EMPLOYEE_NOT_FOUND" else 409
    return HTTPException(status_code=status, detail={"code": exc.code, "message": str(exc)})


def _password_reset_error(exc: AdminPasswordResetError) -> HTTPException:
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


@router.post("/personnel/employees/{employee_id}/access/password-reset")
def reset_employee_password(
    employee_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Depends(_require_user_access_admin),
) -> Dict[str, Any]:
    try:
        return issue_temporary_password(employee_id=employee_id, actor_user_id=int(user["user_id"]))
    except AdminPasswordResetError as exc:
        raise _password_reset_error(exc) from exc


@router.get("/access/users")
def search_access_users(q: str = Query(..., min_length=1, max_length=120), _user: Dict[str, Any] = Depends(_require_user_access_admin)) -> Dict[str, Any]:
    return {"items": search_users_for_access(q=q)}


@router.post("/access/users/{user_id}/password-reset")
def reset_access_user_password(user_id: int = Path(..., ge=1), user: Dict[str, Any] = Depends(_require_user_access_admin)) -> Dict[str, Any]:
    try:
        return issue_temporary_password_for_user(user_id=user_id, actor_user_id=int(user["user_id"]))
    except AdminPasswordResetError as exc:
        raise _password_reset_error(exc) from exc


@router.post("/access/users/{user_id}/activate")
def activate_access_user(
    user_id: int = Path(..., ge=1),
    reason: str = Query(..., min_length=1, max_length=500),
    user: Dict[str, Any] = Depends(_require_user_access_admin),
) -> Dict[str, Any]:
    try:
        return activate_user(user_id=user_id, actor_user_id=int(user["user_id"]), reason=reason)
    except UserActivationError as exc:
        status = 403 if exc.code == "PERMISSION_DENIED" else 404 if exc.code == "USER_NOT_FOUND" else 409
        raise HTTPException(status_code=status, detail={"code": exc.code, "message": str(exc)}) from exc
