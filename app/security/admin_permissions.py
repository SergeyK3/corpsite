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
        "PERSONNEL_ORDERS_CANCEL_OWN",
        "PERSONNEL_ORDERS_CANCEL_SCOPE",
        "PERSONNEL_ORDERS_VOID",
        "PERSONNEL_ORDERS_VOID_APPLIED",
        "PERSONNEL_ORDERS_ARCHIVE",
        "PERSONNEL_ORDERS_RESTORE",
        "PERSONNEL_ORDERS_AUDIT_READ",
        "PERSONNEL_RECOVERY_ADMIN",
        "OPERATIONAL_ORDERS_INTAKE_CREATE",
        "OPERATIONAL_ORDERS_INTAKE_READ",
        "OPERATIONAL_ORDERS_INTAKE_OPERATE",
        "OPERATIONAL_ORDERS_TRANSLATION_ASSIGN",
        "OPERATIONAL_ORDERS_TRANSLATION_WORK",
        "OPERATIONAL_ORDERS_CONTENT_CONFIRM",
        "OPERATIONAL_ORDERS_RECONCILE",
        "OPERATIONAL_ORDERS_EDITORIAL_READY",
        "OPERATIONAL_ORDERS_PROMOTE",
        "OPERATIONAL_ORDERS_SIGNATURE_READINESS_READ",
        "OPERATIONAL_ORDERS_ASSIGN_SIGNING_AUTHORITY",
        "OPERATIONAL_ORDERS_MARK_READY_FOR_SIGNATURE",
        "OPERATIONAL_ORDERS_RETURN_FROM_SIGNATURE",
    }
)

ADMIN_API_PERMISSIONS: FrozenSet[str] = frozenset({"SYSADMIN_CABINET", "ACCESS_ADMIN"})

PERSONNEL_READ_PERMISSIONS: FrozenSet[str] = frozenset(
    {"SYSADMIN_CABINET", "ACCESS_ADMIN", "HR_ENROLLMENT_MANAGER"}
)

HR_GOVERNANCE_PERMISSIONS: FrozenSet[str] = frozenset(
    {"SYSADMIN_CABINET", "ACCESS_ADMIN", "HR_ENROLLMENT_MANAGER"}
)


def has_any_personnel_read_permission(user_id: int) -> bool:
    try:
        active_codes = set(list_active_access_role_codes(int(user_id)))
    except ValueError:
        return False
    return bool(active_codes.intersection(PERSONNEL_READ_PERMISSIONS))


def has_hr_governance_permission(user_id: int) -> bool:
    try:
        active_codes = set(list_active_access_role_codes(int(user_id)))
    except ValueError:
        return False
    return bool(active_codes.intersection(HR_GOVERNANCE_PERMISSIONS))


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
