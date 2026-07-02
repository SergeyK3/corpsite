# FILE: app/directory/users_routes.py
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.auth import get_current_user, hash_password
from app.db.engine import engine
from app.services.operational_contact_service import ensure_operational_contact_for_employee
from app.services.security_audit_service import write_security_event
from app.security.directory_scope import is_privileged as _is_privileged

router = APIRouter()


class UserCreateIn(BaseModel):
    employee_id: int = Field(..., ge=1)
    role_id: int = Field(..., ge=1)
    login: str = Field(..., min_length=1, max_length=200)
    password: str = Field(..., min_length=8, max_length=200)
    unit_id: Optional[int] = Field(default=None, ge=1)
    is_active: bool = True


class UserRoleUpdateIn(BaseModel):
    role_id: int = Field(..., ge=1)


USER_SELECT_SQL = """
SELECT
    u.user_id,
    u.employee_id,
    u.full_name,
    u.login,
    u.google_login,
    u.role_id,
    r.name AS role_name,
    r.code AS role_code,
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
        "role_code": _normalize_text(row.get("role_code")),
        "unit_id": int(unit_id_raw) if unit_id_raw is not None else None,
        "is_active": bool(row.get("is_active")),
        "created_at": row.get("created_at"),
    }


def _normalize_active(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    s = str(value).strip().lower()
    return s in ("1", "true", "yes", "y", "on", "active", "активна", "активен")


def _roles_active_column(conn) -> Optional[str]:
    rows = conn.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'roles'
            """
        )
    ).fetchall()
    cols = {str(r[0]) for r in rows}
    for candidate in ("is_active", "active", "status"):
        if candidate in cols:
            return candidate
    return None


def _fetch_role_row(
    conn,
    role_id: int,
    *,
    require_active: bool = False,
) -> Optional[Dict[str, Any]]:
    active_col = _roles_active_column(conn)
    active_expr = "TRUE AS is_active"
    if active_col == "status":
        active_expr = "status AS is_active"
    elif active_col:
        active_expr = f"{active_col} AS is_active"

    row = conn.execute(
        text(
            f"""
            SELECT role_id, code AS role_code, name AS role_name, {active_expr}
            FROM public.roles
            WHERE role_id = :role_id
            LIMIT 1
            """
        ),
        {"role_id": int(role_id)},
    ).mappings().first()
    if not row:
        return None

    mapped = dict(row)
    if require_active and active_col and not _normalize_active(mapped.get("is_active")):
        return None
    return mapped


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


@router.patch("/users/{user_id}/role")
def update_user_role(
    body: UserRoleUpdateIn,
    request: Request,
    user_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    if not _is_privileged(user):
        raise HTTPException(status_code=403, detail="Forbidden.")

    with engine.begin() as conn:
        current = conn.execute(
            text(f"{USER_SELECT_SQL} WHERE u.user_id = :user_id LIMIT 1"),
            {"user_id": int(user_id)},
        ).mappings().first()
        if not current:
            raise HTTPException(status_code=404, detail="User not found.")

        current_row = dict(current)
        current_role_id = int(current_row["role_id"]) if current_row.get("role_id") is not None else None
        next_role_id = int(body.role_id)

        if current_role_id == next_role_id:
            return _map_user(current_row)

        next_role = _fetch_role_row(conn, next_role_id, require_active=True)
        if not next_role:
            raise HTTPException(status_code=404, detail="Role not found.")

        conn.execute(
            text(
                """
                UPDATE public.users
                SET role_id = :role_id
                WHERE user_id = :user_id
                """
            ),
            {"role_id": next_role_id, "user_id": int(user_id)},
        )

        employee_id = current_row.get("employee_id")
        audit_metadata = {
            "from_role_id": current_role_id,
            "from_role_code": _normalize_text(current_row.get("role_code")),
            "from_role_name": _normalize_text(current_row.get("role_name")),
            "to_role_id": next_role_id,
            "to_role_code": _normalize_text(next_role.get("role_code")),
            "to_role_name": _normalize_text(next_role.get("role_name")),
            "login": _normalize_text(current_row.get("login")),
        }

        write_security_event(
            event_type="ACCESS_CHANGED",
            actor_user_id=int(user["user_id"]),
            target_user_id=int(user_id),
            target_employee_id=int(employee_id) if employee_id is not None else None,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            metadata=audit_metadata,
            conn=conn,
        )

    row = _fetch_user_by_id(int(user_id))
    if not row:
        raise HTTPException(status_code=500, detail="Unable to load updated user.")
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
        SELECT role_id, code AS role_code, name AS role_name
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
        ensure_operational_contact_for_employee(
            conn,
            employee_id=int(body.employee_id),
            full_name=full_name,
        )

    row = _fetch_user_by_id(user_id)
    if not row:
        raise HTTPException(status_code=500, detail="Unable to load created user.")
    return _map_user(row)
