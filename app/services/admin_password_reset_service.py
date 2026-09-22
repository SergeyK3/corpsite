"""Transactional administrative temporary-password issuance."""
from __future__ import annotations

import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from sqlalchemy import text

from app.auth import hash_password
from app.db.engine import engine
from app.services.security_audit_service import write_security_event


class AdminPasswordResetError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(detail)


def _temporary_password() -> str:
    """Generate a password that satisfies the current 8..200 character policy."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(24))


def issue_temporary_password(*, employee_id: int, actor_user_id: int) -> Dict[str, Any]:
    """Reset the password of the single User linked to ``employee_id``.

    The plaintext is deliberately returned only to the immediate caller. It is
    neither persisted nor passed to the audit writer.
    """
    with engine.begin() as conn:
        employee = conn.execute(text("""
            SELECT employee_id, person_id FROM public.employees
            WHERE employee_id = :employee_id
        """), {"employee_id": int(employee_id)}).mappings().one_or_none()
        if employee is None:
            raise AdminPasswordResetError("EMPLOYEE_NOT_FOUND", "Employee not found.")
        if employee["person_id"] is None:
            raise AdminPasswordResetError("PERSON_MISSING", "Employee/User linkage is not unambiguous.")

        users = conn.execute(text("""
            SELECT user_id, locked_reason FROM public.users
            WHERE employee_id = :employee_id
            ORDER BY user_id FOR UPDATE
        """), {"employee_id": int(employee_id)}).mappings().all()
        if not users:
            raise AdminPasswordResetError("USER_MISSING", "Employee/User linkage is not unambiguous.")
        if len(users) != 1:
            raise AdminPasswordResetError("USER_AMBIGUOUS", "Employee/User linkage is not unambiguous.")

        user = users[0]
        return _issue_for_locked_user(conn, user=user, actor_user_id=actor_user_id, employee=employee)


def _issue_for_locked_user(conn, *, user: Dict[str, Any], actor_user_id: int, employee: Dict[str, Any] | None = None) -> Dict[str, Any]:
    temporary_password = _temporary_password()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    brute_force_lock_cleared = str(user.get("locked_reason") or "") == "brute_force"
    updated = conn.execute(text("""
            UPDATE public.users
            SET password_hash = :password_hash,
                password_changed_at = now(),
                must_change_password = TRUE,
                temp_password_expires_at = :expires_at,
                token_version = COALESCE(token_version, 1) + 1,
                locked_at = CASE WHEN :clear_brute_force THEN NULL ELSE locked_at END,
                locked_until = CASE WHEN :clear_brute_force THEN NULL ELSE locked_until END,
                locked_reason = CASE WHEN :clear_brute_force THEN NULL ELSE locked_reason END,
                failed_login_count = CASE WHEN :clear_brute_force THEN 0 ELSE failed_login_count END,
                last_failed_login_at = CASE WHEN :clear_brute_force THEN NULL ELSE last_failed_login_at END
            WHERE user_id = :user_id
            RETURNING token_version
    """), {
        "password_hash": hash_password(temporary_password), "expires_at": expires_at,
        "clear_brute_force": brute_force_lock_cleared, "user_id": int(user["user_id"]),
    }).mappings().one()
    write_security_event(
        event_type="TEMP_PASSWORD_ISSUED", actor_user_id=int(actor_user_id), target_user_id=int(user["user_id"]),
        target_person_id=int(employee["person_id"]) if employee else None,
        target_employee_id=int(employee["employee_id"]) if employee else None,
        metadata={"action": "administrative_credential_reset", "brute_force_lock_cleared": brute_force_lock_cleared}, conn=conn,
    )

    return {
        "employee_id": int(employee["employee_id"]) if employee else None,
        "user_id": int(user["user_id"]),
        "temporary_password": temporary_password,
        "must_change_password": True,
        "temp_password_expires_at": expires_at.isoformat(),
        "token_version": int(updated["token_version"]),
        "brute_force_lock_cleared": brute_force_lock_cleared,
    }


def issue_temporary_password_for_user(*, user_id: int, actor_user_id: int) -> Dict[str, Any]:
    """Issue a temporary password without requiring an Employee linkage."""
    with engine.begin() as conn:
        user = conn.execute(text("""
            SELECT user_id, employee_id, locked_reason FROM public.users
            WHERE user_id=:user_id FOR UPDATE
        """), {"user_id": int(user_id)}).mappings().one_or_none()
        if user is None:
            raise AdminPasswordResetError("USER_NOT_FOUND", "User not found.")
        employee = None
        if user["employee_id"] is not None:
            employee = conn.execute(text("SELECT employee_id, person_id FROM public.employees WHERE employee_id=:employee_id"), {"employee_id": int(user["employee_id"])}).mappings().one_or_none()
        return _issue_for_locked_user(conn, user=user, actor_user_id=actor_user_id, employee=employee)


def search_users_for_access(*, q: str, limit: int = 30) -> list[Dict[str, Any]]:
    query = (q or "").strip()
    if not query:
        return []
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT u.user_id, u.login, u.is_active, r.code AS role_code, r.name AS role_name,
                   u.locked_at, u.locked_until, u.locked_reason, u.employee_id
            FROM public.users u LEFT JOIN public.roles r ON r.role_id=u.role_id
            WHERE lower(COALESCE(u.login,'')) LIKE :pattern
               OR lower(COALESCE(u.full_name,'')) LIKE :pattern
               OR lower(COALESCE(r.code,'')) LIKE :pattern
               OR lower(COALESCE(r.name,'')) LIKE :pattern
            ORDER BY u.login NULLS LAST, u.user_id LIMIT :limit
        """), {"pattern": f"%{query.lower()}%", "limit": max(1, min(int(limit), 50))}).mappings().all()
    return [{
        "user_id": int(row["user_id"]), "login": row["login"], "is_active": bool(row["is_active"]),
        "role": row["role_code"] or row["role_name"], "lock_active": row["locked_at"] is not None,
        "lock_reason": row["locked_reason"], "locked_until": row["locked_until"].isoformat() if row["locked_until"] else None,
        "employee_id": row["employee_id"], "has_linked_employee": row["employee_id"] is not None,
    } for row in rows]
