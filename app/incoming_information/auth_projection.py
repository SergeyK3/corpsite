"""Incoming Information auth projection for /auth/me."""
from __future__ import annotations

from typing import Any

from app.incoming_information.permissions import (
    can_control,
    can_execute,
    can_read,
    can_register,
    can_resolve,
    can_restricted_bypass,
)
from app.security.directory_scope import is_privileged


def build_incoming_information_permissions(user: dict[str, Any]) -> dict[str, bool]:
    uid = int(user.get("user_id") or user.get("id") or 0)
    if uid <= 0:
        return {key: False for key in _PERMISSION_KEYS}
    if is_privileged(user):
        return {
            "register": True,
            "read": True,
            "resolve": True,
            "execute": True,
            "control": True,
            "restricted_bypass": can_restricted_bypass(user),
        }
    return {
        "register": can_register(user),
        "read": can_read(user),
        "resolve": can_resolve(user),
        "execute": can_execute(user),
        "control": can_control(user),
        "restricted_bypass": can_restricted_bypass(user),
    }


def has_any_incoming_information_read(user: dict[str, Any]) -> bool:
    perms = build_incoming_information_permissions(user)
    return any(
        perms.get(key)
        for key in ("read", "register", "resolve", "execute", "control")
    )


_PERMISSION_KEYS = ("register", "read", "resolve", "execute", "control", "restricted_bypass")
