# FILE: app/directory/users_routes.py
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.auth import get_current_user, hash_password
from app.db.engine import engine
from app.security.directory_scope import is_privileged as _is_privileged

router = APIRouter()


class UserCreateIn(BaseModel):
    employee_id: int = Field(..., ge=1)
    role_id: int = Field(..., ge=1)
    login: str = Field(..., min_length=1, max_length=200)
    password: str = Field(..., min_length=8, max_length=200)
    unit_id: Optional[int] = Field(default=None, ge=1)
    is_active: bool = True


USER_SELECT_SQL = """
SELECT
    u.user_id,
    u.employee_id,
    u.full_name,
    u.login,
    u.google_login,
    u.role_id,
    r.name AS role_name,
    u.unit_id,
    u.is_active,
    u.created_at
FROM public.users u
LEFT JOIN public.roles r
  ON r.role_id = u.role_id
"""


def _normalize_text(value: Any) -> Optional[str]:
    s = " ".join(str(value or "").split()).strip()
    return s or None


def _map_user(row: Dict[str, Any]) -> Dict[str, Any]:
    employee_id_raw = row.get("employee_id")
    unit_id_raw = row.get("unit_id")
    role_id_raw = row.get("role_id")
    return {
        "user_id": int(row["user_id"]),
        "employee_id": int(employee_id_raw) if employee_id_raw is not None else None,
        "full_name": _normalize_text(row.get("full_name")),
        "login": _normalize_text(row.get("login")),
        "google_login": _normalize_text(row.get("google_login")),
        "role_id": int(role_id_raw) if role_id_raw is not None else None,
        "role_name": _normalize_text(row.get("role_name")),
        "unit_id": int(unit_id_raw) if unit_id_raw is not None else None,
        "is_active": bool(row.get("is_active")),
        "created_at": row.get("created_at"),
    }


def _fetch_user_by_employee_id(employee_id: int) -> Optional[Dict[str, Any]]:
    q = text(
        f"""
        {USER_SELECT_SQL}
        WHERE u.employee_id = :employee_id
        LIMIT 1
        """
    )
    with engine.begin() as conn:
        row = conn.execute(q, {"employee_id": int(employee_id)}).mappings().first()
    return dict(row) if row else None


def _fetch_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    q = text(
        f"""
        {USER_SELECT_SQL}
        WHERE u.user_id = :user_id
        LIMIT 1
        """
    )
    with engine.begin() as conn:
        row = conn.execute(q, {"user_id": int(user_id)}).mappings().first()
    return dict(row) if row else None


@router.get("/users")
def get_user_by_employee_id(
    employee_id: int = Query(..., ge=1),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    _ = user
    row = _fetch_user_by_employee_id(int(employee_id))
    if not row:
        raise HTTPException(status_code=404, detail="User not found.")
    return _map_user(row)


@router.post("/users", status_code=201)
def create_user(
    body: UserCreateIn,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    if not _is_privileged(user):
        raise HTTPException(status_code=403, detail="Forbidden.")

    login = _normalize_text(body.login)
    if not login:
        raise HTTPException(status_code=422, detail="login is required.")

    q_employee = text(
        """
        SELECT employee_id, full_name, org_unit_id
        FROM public.employees
        WHERE employee_id = :employee_id
        LIMIT 1
        """
    )
    q_role = text(
        """
        SELECT role_id
        FROM public.roles
        WHERE role_id = :role_id
        LIMIT 1
        """
    )
    q_unit = text(
        """
        SELECT unit_id
        FROM public.org_units
        WHERE unit_id = :unit_id
        LIMIT 1
        """
    )
    q_login = text(
        """
        SELECT user_id
        FROM public.users
        WHERE lower(login) = lower(:login)
        LIMIT 1
        """
    )
    q_employee_user = text(
        """
        SELECT user_id
        FROM public.users
        WHERE employee_id = :employee_id
        LIMIT 1
        """
    )

    with engine.begin() as conn:
        emp_row = conn.execute(q_employee, {"employee_id": int(body.employee_id)}).mappings().first()
        if not emp_row:
            raise HTTPException(status_code=404, detail="Employee not found.")

        role_row = conn.execute(q_role, {"role_id": int(body.role_id)}).mappings().first()
        if not role_row:
            raise HTTPException(status_code=404, detail="Role not found.")

        unit_id = int(body.unit_id) if body.unit_id is not None else emp_row.get("org_unit_id")
        if unit_id is None:
            raise HTTPException(status_code=404, detail="Org unit not found.")

        unit_row = conn.execute(q_unit, {"unit_id": int(unit_id)}).mappings().first()
        if unit_row is None:
            raise HTTPException(status_code=404, detail="Org unit not found.")

        if conn.execute(q_login, {"login": login}).first():
            raise HTTPException(status_code=409, detail="Login already exists.")

        if conn.execute(q_employee_user, {"employee_id": int(body.employee_id)}).first():
            raise HTTPException(status_code=409, detail="User for this employee already exists.")

        full_name = _normalize_text(emp_row.get("full_name")) or login
        password_hash = hash_password(body.password)

        q_insert = text(
            """
            INSERT INTO public.users (
                full_name,
                google_login,
                role_id,
                unit_id,
                is_active,
                login,
                password_hash,
                employee_id
            )
            VALUES (
                :full_name,
                :google_login,
                :role_id,
                :unit_id,
                :is_active,
                :login,
                :password_hash,
                :employee_id
            )
            RETURNING user_id
            """
        )

        try:
            created = conn.execute(
                q_insert,
                {
                    "full_name": full_name,
                    "google_login": login,
                    "role_id": int(body.role_id),
                    "unit_id": int(unit_id),
                    "is_active": bool(body.is_active),
                    "login": login,
                    "password_hash": password_hash,
                    "employee_id": int(body.employee_id),
                },
            ).mappings().first()
        except IntegrityError as exc:
            msg = str(getattr(exc, "orig", exc)).lower()
            if "employee_id" in msg or "uq_users_employee_id" in msg:
                raise HTTPException(status_code=409, detail="User for this employee already exists.") from exc
            if "login" in msg:
                raise HTTPException(status_code=409, detail="Login already exists.") from exc
            raise HTTPException(status_code=409, detail="Unable to create user.") from exc

        if not created or created.get("user_id") is None:
            raise HTTPException(status_code=500, detail="Unable to create user.")

        user_id = int(created["user_id"])

    row = _fetch_user_by_id(user_id)
    if not row:
        raise HTTPException(status_code=500, detail="Unable to load created user.")
    return _map_user(row)
