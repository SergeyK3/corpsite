"""Incoming Information permission helpers."""
from __future__ import annotations

from typing import Any

from app.security.admin_permissions import has_admin_permission
from app.security.directory_scope import is_privileged

PERMISSION_REGISTER = "INCOMING_INFO_REGISTER"
PERMISSION_READ = "INCOMING_INFO_READ"
PERMISSION_RESOLVE = "INCOMING_INFO_RESOLVE"
PERMISSION_EXECUTE = "INCOMING_INFO_EXECUTE"
PERMISSION_CONTROL = "INCOMING_INFO_CONTROL"
PERMISSION_ADMIN = "INCOMING_INFO_ADMIN"
PERMISSION_RESTRICTED_BYPASS = "INCOMING_INFO_RESTRICTED_BYPASS"


def _has(user: dict[str, Any], permission: str) -> bool:
    uid = int(user.get("user_id") or user.get("id") or 0)
    if uid <= 0:
        return False
    if is_privileged(user):
        return True
    return has_admin_permission(uid, permission)


def can_register(user: dict[str, Any]) -> bool:
    return _has(user, PERMISSION_REGISTER) or _has(user, PERMISSION_ADMIN)


def can_read(user: dict[str, Any]) -> bool:
    return _has(user, PERMISSION_READ) or _has(user, PERMISSION_ADMIN)


def can_resolve(user: dict[str, Any]) -> bool:
    return _has(user, PERMISSION_RESOLVE) or _has(user, PERMISSION_ADMIN)


def can_execute(user: dict[str, Any]) -> bool:
    return _has(user, PERMISSION_EXECUTE) or _has(user, PERMISSION_ADMIN)


def can_control(user: dict[str, Any]) -> bool:
    return _has(user, PERMISSION_CONTROL) or _has(user, PERMISSION_ADMIN)


def can_admin(user: dict[str, Any]) -> bool:
    return _has(user, PERMISSION_ADMIN)


def can_restricted_bypass(user: dict[str, Any]) -> bool:
    uid = int(user.get("user_id") or user.get("id") or 0)
    if uid <= 0:
        return False
    return has_admin_permission(uid, PERMISSION_RESTRICTED_BYPASS)


def has_base_read_permission(user: dict[str, Any]) -> bool:
    """Base II read/workflow permission. RESTRICTED_BYPASS alone is not sufficient."""
    return (
        can_read(user)
        or can_register(user)
        or can_resolve(user)
        or can_execute(user)
        or can_control(user)
    )
