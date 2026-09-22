"""Audited activation of an existing local User account."""
from __future__ import annotations

import json
from typing import Any, Dict

from sqlalchemy import text

from app.db.engine import engine
from app.security.admin_permissions import USER_ACCESS_ADMIN, has_admin_permission
from app.services.security_audit_service import write_security_event


class UserActivationError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(detail)


def activate_user(*, user_id: int, actor_user_id: int, reason: str) -> Dict[str, Any]:
    """Activate one inactive User without changing identity or credentials."""
    clean_reason = " ".join(str(reason or "").split())
    if not clean_reason:
        raise UserActivationError("REASON_REQUIRED", "Activation reason is required.")
    if len(clean_reason) > 500:
        raise UserActivationError("REASON_INVALID", "Activation reason is too long.")
    if not has_admin_permission(int(actor_user_id), USER_ACCESS_ADMIN):
        raise UserActivationError("PERMISSION_DENIED", "Permission required: USER_ACCESS_ADMIN")

    with engine.begin() as conn:
        row = conn.execute(text("""
            SELECT user_id, is_active, employee_id, role_id, login, token_version
            FROM public.users WHERE user_id=:user_id FOR UPDATE
        """), {"user_id": int(user_id)}).mappings().one_or_none()
        if row is None:
            raise UserActivationError("USER_NOT_FOUND", "User not found.")
        if bool(row["is_active"]):
            raise UserActivationError("USER_ALREADY_ACTIVE", "User is already active.")
        before = {"is_active": False, "token_version": int(row["token_version"] or 1)}
        updated = conn.execute(text("""
            UPDATE public.users SET is_active=TRUE, token_version=COALESCE(token_version,1)+1
            WHERE user_id=:user_id RETURNING token_version
        """), {"user_id": int(user_id)}).mappings().one()
        after = {"is_active": True, "token_version": int(updated["token_version"])}
        conn.execute(text("""
            INSERT INTO public.audit_log (actor_user_id, entity, entity_id, action, before_data, after_data)
            VALUES (:actor_user_id, 'users', :user_id, 'USER_ACTIVATED', CAST(:before_data AS jsonb), CAST(:after_data AS jsonb))
        """), {"actor_user_id": int(actor_user_id), "user_id": int(user_id), "before_data": json.dumps(before), "after_data": json.dumps(after)})
        write_security_event(
            # The database constrains security events to its established
            # vocabulary; activation is therefore recorded as this precise
            # access-change operation rather than inventing a schema value.
            event_type="ACCESS_CHANGED", actor_user_id=int(actor_user_id), target_user_id=int(user_id),
            target_employee_id=int(row["employee_id"]) if row["employee_id"] is not None else None,
            metadata={"operation": "USER_ACTIVATED", "reason": clean_reason, "previous_active": False, "new_version": after["token_version"]}, conn=conn,
        )
    return {"user_id": int(user_id), "is_active": True, "token_version": after["token_version"]}
