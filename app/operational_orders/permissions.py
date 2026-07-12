"""Operational Orders intake permission helpers (OO-IMP-001 bootstrap)."""
from __future__ import annotations

from typing import Any

from app.operational_orders.scope import workspace_in_user_scope
from app.security.admin_permissions import has_admin_permission
from app.security.directory_scope import is_privileged

PERMISSION_INTAKE_CREATE = "OPERATIONAL_ORDERS_INTAKE_CREATE"
PERMISSION_INTAKE_READ = "OPERATIONAL_ORDERS_INTAKE_READ"
PERMISSION_INTAKE_OPERATE = "OPERATIONAL_ORDERS_INTAKE_OPERATE"


def can_create_intake(user: dict[str, Any]) -> bool:
    user_id = int(user["user_id"])
    if is_privileged(user):
        return True
    return has_admin_permission(user_id, PERMISSION_INTAKE_CREATE)


def can_read_workspace(user: dict[str, Any], workspace: dict[str, Any]) -> bool:
    if not workspace_in_user_scope(user, workspace):
        return False
    user_id = int(user["user_id"])
    if is_privileged(user):
        return True
    if has_admin_permission(user_id, PERMISSION_INTAKE_READ):
        return True
    if has_admin_permission(user_id, PERMISSION_INTAKE_OPERATE):
        return True
    return int(workspace.get("record_creator_user_id") or 0) == user_id


def can_operate_intake(user: dict[str, Any], workspace: dict[str, Any]) -> bool:
    if not workspace_in_user_scope(user, workspace):
        return False
    user_id = int(user["user_id"])
    if is_privileged(user):
        return True
    if has_admin_permission(user_id, PERMISSION_INTAKE_OPERATE):
        return True
    return int(workspace.get("record_creator_user_id") or 0) == user_id
