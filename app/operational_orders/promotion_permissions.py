"""Operational Orders promotion permission helpers (OO-IMP-003)."""
from __future__ import annotations

from typing import Any

from app.db.models.operational_orders import (
    WORKSPACE_STAGE_DOCUMENT_PROMOTED,
    WORKSPACE_STAGE_EDITORIAL_PACKAGE_READY,
)
from app.operational_orders.scope import document_in_user_scope, workspace_in_user_scope
from app.security.admin_permissions import has_admin_permission
from app.security.directory_scope import is_privileged

PERMISSION_PROMOTE = "OPERATIONAL_ORDERS_PROMOTE"


def can_promote_workspace(user: dict[str, Any], workspace: dict[str, Any]) -> bool:
    stage = str(workspace.get("stage"))
    if stage not in {
        WORKSPACE_STAGE_EDITORIAL_PACKAGE_READY,
        WORKSPACE_STAGE_DOCUMENT_PROMOTED,
    }:
        return False
    if not workspace_in_user_scope(user, workspace):
        return False
    if is_privileged(user):
        return True
    return has_admin_permission(int(user["user_id"]), PERMISSION_PROMOTE)


def can_read_document(user: dict[str, Any], document: dict[str, Any]) -> bool:
    if not document_in_user_scope(user, document):
        return False
    if is_privileged(user):
        return True
    user_id = int(user["user_id"])
    if has_admin_permission(user_id, PERMISSION_PROMOTE):
        return True
    from app.operational_orders.permissions import PERMISSION_INTAKE_READ, PERMISSION_INTAKE_OPERATE

    if has_admin_permission(user_id, PERMISSION_INTAKE_READ):
        return True
    if has_admin_permission(user_id, PERMISSION_INTAKE_OPERATE):
        return True
    return int(document.get("created_by_user_id") or 0) == user_id
