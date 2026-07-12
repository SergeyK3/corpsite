"""Org-scope helpers for Operational Orders intake (directory RBAC integration)."""
from __future__ import annotations

from typing import Any

from app.db.engine import engine
from app.operational_orders.errors import OperationalOrderForbiddenError
from app.security.directory_scope import is_privileged
from app.services.org_units_service import OrgUnitsService

_org_units = OrgUnitsService(engine)


def resolve_user_scope_unit_ids(user: dict[str, Any]) -> set[int] | None:
    """Return allowed org unit ids for user, or None when scope is unlimited."""
    if is_privileged(user):
        return None
    user_id = int(user["user_id"])
    try:
        scope = _org_units.compute_user_scope_unit_ids(user_id, include_inactive=False)
    except PermissionError as exc:
        raise OperationalOrderForbiddenError(str(exc)) from exc
    return scope


def assert_submitting_unit_in_scope(user: dict[str, Any], submitting_org_unit_id: int) -> None:
    scope = resolve_user_scope_unit_ids(user)
    if scope is None:
        return
    if int(submitting_org_unit_id) not in scope:
        raise OperationalOrderForbiddenError("Submitting unit is outside permitted org scope.")


def workspace_in_user_scope(user: dict[str, Any], workspace: dict[str, Any]) -> bool:
    scope = resolve_user_scope_unit_ids(user)
    if scope is None:
        return True
    submitting_unit_id = int(workspace.get("submitting_org_unit_id") or 0)
    return submitting_unit_id in scope


def document_in_user_scope(user: dict[str, Any], document: dict[str, Any]) -> bool:
    scope = resolve_user_scope_unit_ids(user)
    if scope is None:
        return True
    submitting_unit_id = int(document.get("submitting_org_unit_id") or 0)
    return submitting_unit_id in scope


def assert_document_in_scope(user: dict[str, Any], document: dict[str, Any]) -> None:
    if not document_in_user_scope(user, document):
        raise OperationalOrderForbiddenError("Document is outside permitted org scope.")


def assert_workspace_matches_document(
    *,
    workspace_id: int,
    document: dict[str, Any],
) -> None:
    if int(document.get("workspace_id") or 0) != int(workspace_id):
        raise OperationalOrderForbiddenError("Document does not belong to workspace.")
