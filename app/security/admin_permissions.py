"""ADR-042 Phase B5 — admin permission helpers via access_grants."""
from __future__ import annotations

from typing import Any, Dict, FrozenSet

from fastapi import Depends, HTTPException

from app.auth import get_current_user
from app.services.access_resolver_service import list_active_access_role_codes

PERMISSION_CODES: FrozenSet[str] = frozenset(
    {
        "SYSADMIN_CABINET",
        "HR_ENROLLMENT_MANAGER",
        "ACCESS_MANAGER",
        "SECURITY_AUDITOR",
        "ACCESS_ADMIN",
    }
)

ADMIN_API_PERMISSIONS: FrozenSet[str] = frozenset({"SYSADMIN_CABINET", "ACCESS_ADMIN"})


def has_admin_permission(user_id: int, permission_code: str) -> bool:
    code = (permission_code or "").strip().upper()
    if code not in PERMISSION_CODES:
        return False
    try:
        active_codes = list_active_access_role_codes(int(user_id))
    except ValueError:
        return False
    return code in active_codes


def has_any_admin_api_permission(user_id: int) -> bool:
    try:
        active_codes = set(list_active_access_role_codes(int(user_id)))
    except ValueError:
        return False
    return bool(active_codes.intersection(ADMIN_API_PERMISSIONS))


def require_admin_permission(permission_code: str):
    """FastAPI dependency factory requiring a specific access_grants permission."""

    def _dependency(user_ctx: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        uid = int(user_ctx["user_id"])
        if not has_admin_permission(uid, permission_code):
            raise HTTPException(
                status_code=403,
                detail=f"Permission required: {(permission_code or '').strip().upper()}",
            )
        return user_ctx

    return _dependency
