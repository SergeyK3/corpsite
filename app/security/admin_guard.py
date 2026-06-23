"""ADR-042 Phase B4/B5 — guard for /admin/* routes."""
from __future__ import annotations

import os
from typing import Any, Dict, Literal

from fastapi import Depends, HTTPException

from app.auth import get_current_user
from app.security.admin_permissions import has_any_admin_api_permission
from app.security.directory_scope import is_privileged, is_system_admin, privileged_user_ids
from app.services.security_audit_service import write_security_event

AdminGuardMode = Literal["legacy", "access_grants_shadow", "access_grants_enforced"]

_VALID_MODES = frozenset({"legacy", "access_grants_shadow", "access_grants_enforced"})


def admin_guard_mode() -> AdminGuardMode:
    raw = (os.getenv("ADR042_ADMIN_GUARD_MODE") or "legacy").strip().lower()
    if raw in _VALID_MODES:
        return raw  # type: ignore[return-value]
    return "legacy"


def is_sysadmin_emergency_fallback(user_ctx: Dict[str, Any]) -> bool:
    """Break-glass: system-admin role or explicit user allowlist only (not role allowlist)."""
    if is_system_admin(user_ctx):
        return True
    try:
        uid = int(user_ctx["user_id"])
    except (TypeError, ValueError, KeyError):
        return False
    return uid in privileged_user_ids()


def is_emergency_admin_fallback(user_ctx: Dict[str, Any]) -> bool:
    """Backward-compatible alias for sysadmin emergency fallback."""
    return is_sysadmin_emergency_fallback(user_ctx)


def _access_grants_allow_admin(user_id: int) -> bool:
    return has_any_admin_api_permission(int(user_id))


def _sysadmin_api_allowed(user_ctx: Dict[str, Any]) -> bool:
    uid = int(user_ctx["user_id"])
    return is_sysadmin_emergency_fallback(user_ctx) or _access_grants_allow_admin(uid)


def _log_shadow_guard_decision(
    *,
    user_ctx: Dict[str, Any],
    legacy_allowed: bool,
    grants_allowed: bool,
) -> None:
    if legacy_allowed == grants_allowed:
        return
    write_security_event(
        event_type="ACCESS_CHANGED",
        actor_user_id=int(user_ctx["user_id"]),
        target_user_id=int(user_ctx["user_id"]),
        metadata={
            "action": "admin_guard_shadow",
            "guard_mode": "access_grants_shadow",
            "legacy_allowed": legacy_allowed,
            "grants_allowed": grants_allowed,
            "permissions_checked": ["SYSADMIN_CABINET", "ACCESS_ADMIN"],
            "note": "legacy_allowed reflects pre-split is_privileged() gate",
        },
    )


def evaluate_admin_access(user_ctx: Dict[str, Any]) -> bool:
    """Sysadmin API access: role_id=2, break-glass user allowlist, or admin grants."""
    mode = admin_guard_mode()
    allowed = _sysadmin_api_allowed(user_ctx)

    if mode == "access_grants_shadow":
        pre_split_directory_privileged = is_privileged(user_ctx)
        _log_shadow_guard_decision(
            user_ctx=user_ctx,
            legacy_allowed=pre_split_directory_privileged,
            grants_allowed=allowed,
        )

    return allowed


def require_sysadmin_api(
    user_ctx: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Restrict sysadmin /admin/* routes (users, access grants, enrollment admin, …).

    Allowed when:
    - role_id=2 (system admin), or
    - user_id in DIRECTORY_PRIVILEGED_USER_IDS (break-glass), or
    - active SYSADMIN_CABINET / ACCESS_ADMIN access grant

    DIRECTORY_PRIVILEGED_ROLE_IDS does NOT grant sysadmin API access.
    """
    if not evaluate_admin_access(user_ctx):
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user_ctx
