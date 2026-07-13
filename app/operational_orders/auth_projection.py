"""Operational Orders permission projection for /auth/me (OO-UI-001)."""
from __future__ import annotations

from typing import Any

from app.operational_orders.editorial_permissions import (
    PERMISSION_CONTENT_CONFIRM,
    PERMISSION_EDITORIAL_READY,
    PERMISSION_RECONCILE,
    PERMISSION_TRANSLATION_ASSIGN,
    PERMISSION_TRANSLATION_WORK,
)
from app.operational_orders.lifecycle_permissions import (
    PERMISSION_ASSIGN_SIGNING_AUTHORITY,
    PERMISSION_MARK_READY_FOR_SIGNATURE,
    PERMISSION_RETURN_FROM_SIGNATURE,
    PERMISSION_SIGN,
    PERMISSION_SIGNATURE_READINESS_READ,
)
from app.operational_orders.permissions import (
    PERMISSION_INTAKE_CREATE,
    PERMISSION_INTAKE_OPERATE,
    PERMISSION_INTAKE_READ,
)
from app.operational_orders.promotion_permissions import PERMISSION_PROMOTE
from app.security.admin_permissions import has_admin_permission
from app.security.directory_scope import is_privileged


def build_operational_orders_permissions(user: dict[str, Any]) -> dict[str, bool]:
    """Authoritative OO permission flags for frontend action gating."""
    uid = int(user.get("user_id") or user.get("id") or 0)
    if uid <= 0:
        return {key: False for key in _PERMISSION_KEYS}

    if is_privileged(user):
        return {key: True for key in _PERMISSION_KEYS}

    return {
        "intake_create": has_admin_permission(uid, PERMISSION_INTAKE_CREATE),
        "intake_read": has_admin_permission(uid, PERMISSION_INTAKE_READ),
        "intake_operate": has_admin_permission(uid, PERMISSION_INTAKE_OPERATE),
        "translation_assign": has_admin_permission(uid, PERMISSION_TRANSLATION_ASSIGN),
        "translation_work": has_admin_permission(uid, PERMISSION_TRANSLATION_WORK),
        "content_confirm": has_admin_permission(uid, PERMISSION_CONTENT_CONFIRM),
        "reconcile": has_admin_permission(uid, PERMISSION_RECONCILE),
        "editorial_ready": has_admin_permission(uid, PERMISSION_EDITORIAL_READY),
        "promote": has_admin_permission(uid, PERMISSION_PROMOTE),
        "signature_readiness_read": has_admin_permission(uid, PERMISSION_SIGNATURE_READINESS_READ),
        "assign_signing_authority": has_admin_permission(uid, PERMISSION_ASSIGN_SIGNING_AUTHORITY),
        "mark_ready_for_signature": has_admin_permission(uid, PERMISSION_MARK_READY_FOR_SIGNATURE),
        "return_from_signature": has_admin_permission(uid, PERMISSION_RETURN_FROM_SIGNATURE),
        "sign_document": has_admin_permission(uid, PERMISSION_SIGN),
    }


def has_any_operational_orders_read(user: dict[str, Any]) -> bool:
    """Navigation projection — true when user can open the OO preparation section (OO-UI-001B).

    Gates the workspace preparation contour (intake/editorial), not organization-wide
    official document read (OO-SEC-002). Typical leadership grant: OPERATIONAL_ORDERS_INTAKE_READ.
    Also true for operate, promote, or signature-readiness read (broader preparation read family).
    """
    perms = build_operational_orders_permissions(user)
    return any(
        perms.get(key)
        for key in (
            "intake_read",
            "intake_operate",
            "promote",
            "signature_readiness_read",
        )
    )


_PERMISSION_KEYS = (
    "intake_create",
    "intake_read",
    "intake_operate",
    "translation_assign",
    "translation_work",
    "content_confirm",
    "reconcile",
    "editorial_ready",
    "promote",
    "signature_readiness_read",
    "assign_signing_authority",
    "mark_ready_for_signature",
    "return_from_signature",
    "sign_document",
)
