"""Org-scope helpers for Incoming Information."""
from __future__ import annotations

from typing import Any

from app.db.engine import engine
from app.incoming_information.domain.errors import IncomingDocumentForbiddenError
from app.incoming_information.domain.models import IncomingDocumentSnapshot
from app.incoming_information.permissions import can_read
from app.security.directory_scope import is_privileged
from app.security.platform_role_classification import is_hr_head_platform_role
from app.services.org_units_service import OrgUnitsService

_org_units = OrgUnitsService(engine)


def resolve_user_scope_unit_ids(user: dict[str, Any]) -> set[int] | None:
    if is_privileged(user):
        return None
    user_id = int(user["user_id"])
    try:
        return _org_units.compute_user_scope_unit_ids(user_id, include_inactive=False)
    except PermissionError as exc:
        raise IncomingDocumentForbiddenError(str(exc)) from exc


def has_organization_wide_normal_read_scope(user: dict[str, Any]) -> bool:
    """HR_HEAD policy: NORMAL is organization-wide only with explicit II read."""
    return is_hr_head_platform_role(user.get("role_code")) and can_read(user)


def resolve_document_read_scope_unit_ids(user: dict[str, Any]) -> set[int] | None:
    if has_organization_wide_normal_read_scope(user):
        return None
    return resolve_user_scope_unit_ids(user)


def document_in_user_scope(user: dict[str, Any], document: IncomingDocumentSnapshot) -> bool:
    scope = resolve_document_read_scope_unit_ids(user)
    if scope is None:
        return True
    return int(document.responsible_org_unit_id) in scope
