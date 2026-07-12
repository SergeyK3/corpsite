"""Operational Orders editorial workflow permission helpers (OO-IMP-002)."""
from __future__ import annotations

from typing import Any

from app.operational_orders.permissions import can_read_workspace
from app.operational_orders.scope import workspace_in_user_scope
from app.security.admin_permissions import has_admin_permission
from app.security.directory_scope import is_privileged

PERMISSION_TRANSLATION_ASSIGN = "OPERATIONAL_ORDERS_TRANSLATION_ASSIGN"
PERMISSION_TRANSLATION_WORK = "OPERATIONAL_ORDERS_TRANSLATION_WORK"
PERMISSION_CONTENT_CONFIRM = "OPERATIONAL_ORDERS_CONTENT_CONFIRM"
PERMISSION_RECONCILE = "OPERATIONAL_ORDERS_RECONCILE"
PERMISSION_EDITORIAL_READY = "OPERATIONAL_ORDERS_EDITORIAL_READY"


def _has(user: dict[str, Any], permission_code: str) -> bool:
    return has_admin_permission(int(user["user_id"]), permission_code)


def can_assign_translation(user: dict[str, Any], workspace: dict[str, Any]) -> bool:
    if not workspace_in_user_scope(user, workspace):
        return False
    if is_privileged(user):
        return True
    return _has(user, PERMISSION_TRANSLATION_ASSIGN)


def can_work_translation(
    user: dict[str, Any],
    workspace: dict[str, Any],
    assignment: dict[str, Any] | None = None,
) -> bool:
    if not workspace_in_user_scope(user, workspace):
        return False
    if is_privileged(user):
        return True
    if _has(user, PERMISSION_TRANSLATION_WORK):
        return True
    if assignment is None:
        return False
    user_id = str(user["user_id"])
    if (
        assignment.get("assigned_to_type") == "PERSON"
        and str(assignment.get("assigned_to_reference")) == user_id
    ):
        return True
    return False


def can_confirm_content(user: dict[str, Any], workspace: dict[str, Any]) -> bool:
    if not workspace_in_user_scope(user, workspace):
        return False
    if is_privileged(user):
        return True
    return _has(user, PERMISSION_CONTENT_CONFIRM)


def user_matches_content_author(user: dict[str, Any], workspace: dict[str, Any]) -> bool:
    if workspace.get("content_author_type") != "PERSON":
        return False
    return str(workspace.get("content_author_reference")) == str(user["user_id"])


def can_confirm_as_content_author(user: dict[str, Any], workspace: dict[str, Any]) -> bool:
    if not can_confirm_content(user, workspace):
        return False
    return user_matches_content_author(user, workspace)


def can_reconcile(user: dict[str, Any], workspace: dict[str, Any]) -> bool:
    if not workspace_in_user_scope(user, workspace):
        return False
    if is_privileged(user):
        return True
    return _has(user, PERMISSION_RECONCILE)


def can_mark_editorial_ready(user: dict[str, Any], workspace: dict[str, Any]) -> bool:
    if not workspace_in_user_scope(user, workspace):
        return False
    if is_privileged(user):
        return True
    return _has(user, PERMISSION_EDITORIAL_READY)


def can_read_editorial(user: dict[str, Any], workspace: dict[str, Any]) -> bool:
    return can_read_workspace(user, workspace)
