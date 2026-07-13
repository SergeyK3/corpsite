"""Operational Orders lifecycle and signature readiness permissions (OO-IMP-004)."""
from __future__ import annotations

from typing import Any

from app.operational_orders.promotion_permissions import can_read_document
from app.operational_orders.scope import document_in_user_scope
from app.security.admin_permissions import has_admin_permission
from app.security.directory_scope import is_privileged

PERMISSION_SIGNATURE_READINESS_READ = "OPERATIONAL_ORDERS_SIGNATURE_READINESS_READ"
PERMISSION_ASSIGN_SIGNING_AUTHORITY = "OPERATIONAL_ORDERS_ASSIGN_SIGNING_AUTHORITY"
PERMISSION_MARK_READY_FOR_SIGNATURE = "OPERATIONAL_ORDERS_MARK_READY_FOR_SIGNATURE"
PERMISSION_RETURN_FROM_SIGNATURE = "OPERATIONAL_ORDERS_RETURN_FROM_SIGNATURE"
PERMISSION_SIGN = "OPERATIONAL_ORDERS_SIGN"


def can_read_signature_readiness(user: dict[str, Any], document: dict[str, Any]) -> bool:
    if not document_in_user_scope(user, document):
        return False
    if is_privileged(user):
        return True
    user_id = int(user["user_id"])
    if has_admin_permission(user_id, PERMISSION_SIGNATURE_READINESS_READ):
        return True
    return can_read_document(user, document)


def can_assign_signing_authority(user: dict[str, Any], document: dict[str, Any]) -> bool:
    if not document_in_user_scope(user, document):
        return False
    if is_privileged(user):
        return True
    return has_admin_permission(int(user["user_id"]), PERMISSION_ASSIGN_SIGNING_AUTHORITY)


def can_mark_ready_for_signature(user: dict[str, Any], document: dict[str, Any]) -> bool:
    if not document_in_user_scope(user, document):
        return False
    if is_privileged(user):
        return True
    return has_admin_permission(int(user["user_id"]), PERMISSION_MARK_READY_FOR_SIGNATURE)


def can_return_from_signature(user: dict[str, Any], document: dict[str, Any]) -> bool:
    if not document_in_user_scope(user, document):
        return False
    if is_privileged(user):
        return True
    return has_admin_permission(int(user["user_id"]), PERMISSION_RETURN_FROM_SIGNATURE)


def can_sign_document(user: dict[str, Any], document: dict[str, Any]) -> bool:
    if not document_in_user_scope(user, document):
        return False
    if is_privileged(user):
        return True
    return has_admin_permission(int(user["user_id"]), PERMISSION_SIGN)
