"""ADR-042 Phase B4/B5 — guard for /admin/* routes."""
from __future__ import annotations

import os
from typing import Any, Dict, Literal

from fastapi import Depends, HTTPException

from app.auth import get_current_user
from app.security.admin_permissions import has_any_admin_api_permission
from app.security.directory_scope import is_privileged
from app.services.security_audit_service import write_security_event

AdminGuardMode = Literal["legacy", "access_grants_shadow", "access_grants_enforced"]

_VALID_MODES = frozenset({"legacy", "access_grants_shadow", "access_grants_enforced"})


def admin_guard_mode() -> AdminGuardMode:
    raw = (os.getenv("ADR042_ADMIN_GUARD_MODE") or "legacy").strip().lower()
    if raw in _VALID_MODES:
        return raw  # type: ignore[return-value]
    return "legacy"


def is_emergency_admin_fallback(user_ctx: Dict[str, Any]) -> bool:
    """Env allowlist + legacy role_id=2 — always honored in enforced mode."""
    return is_privileged(user_ctx)


def _access_grants_allow_admin(user_id: int) -> bool:
    return has_any_admin_api_permission(int(user_id))


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
        },
    )


def evaluate_admin_access(user_ctx: Dict[str, Any]) -> bool:
    """Core admin access decision for the current guard mode."""
    mode = admin_guard_mode()
    uid = int(user_ctx["user_id"])
    legacy_allowed = is_emergency_admin_fallback(user_ctx)
    grants_allowed = _access_grants_allow_admin(uid)

    if mode == "legacy":
        return legacy_allowed

    if mode == "access_grants_shadow":
        _log_shadow_guard_decision(
            user_ctx=user_ctx,
            legacy_allowed=legacy_allowed,
            grants_allowed=grants_allowed,
        )
        return legacy_allowed

    # access_grants_enforced
    if legacy_allowed:
        return True
    return grants_allowed


def require_sysadmin_api(
    user_ctx: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Restrict /admin/* based on ADR042_ADMIN_GUARD_MODE.

    Modes:
    - legacy (default): is_privileged()
    - access_grants_shadow: legacy decides; mismatches logged to security_audit_log
    - access_grants_enforced: SYSADMIN_CABINET/ACCESS_ADMIN grant OR emergency fallback
    """
    if not evaluate_admin_access(user_ctx):
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user_ctx
