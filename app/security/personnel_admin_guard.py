"""ADR-043 Phase C4.1 — guards for /admin/personnel/* routes."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import Depends, HTTPException

from app.auth import get_current_user
from app.security.admin_guard import evaluate_admin_access
from app.security.admin_permissions import (
    has_any_personnel_read_permission,
    has_hr_governance_permission,
)


def evaluate_personnel_admin_access(user_ctx: Dict[str, Any]) -> bool:
    """SYSADMIN/ACCESS_ADMIN (via admin guard) or HR_ENROLLMENT_MANAGER grant."""
    if evaluate_admin_access(user_ctx):
        return True
    return has_any_personnel_read_permission(int(user_ctx["user_id"]))


def evaluate_hr_governance_access(user_ctx: Dict[str, Any]) -> bool:
    """Tier-2 override approve/reject: full admin or HR governance grant."""
    if evaluate_admin_access(user_ctx):
        return True
    return has_hr_governance_permission(int(user_ctx["user_id"]))


def require_personnel_admin_api(
    user_ctx: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    if not evaluate_personnel_admin_access(user_ctx):
        raise HTTPException(
            status_code=403,
            detail="Personnel admin access required (ADMIN or HR_ENROLLMENT_MANAGER).",
        )
    return user_ctx


def require_hr_governance_api(
    user_ctx: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    if not evaluate_hr_governance_access(user_ctx):
        raise HTTPException(
            status_code=403,
            detail="HR governance permission required for this override action.",
        )
    return user_ctx
