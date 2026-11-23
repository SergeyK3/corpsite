"""Strict server-side authorization for PPR migration Stage 0."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.security.admin_permissions import PPR_STAGE0_COHORT_MANAGE_PERMISSION, has_admin_permission


def require_ppr_stage0_cohort_manage(user: dict[str, Any]) -> int:
    try:
        user_id = int(user["user_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Unauthorized.") from exc
    if str(user.get("role_code") or "").upper() != "HR_HEAD":
        raise HTTPException(status_code=403, detail="HR_HEAD role required.")
    if not has_admin_permission(user_id, PPR_STAGE0_COHORT_MANAGE_PERMISSION):
        raise HTTPException(status_code=403, detail="PPR Stage 0 cohort permission required.")
    return user_id
