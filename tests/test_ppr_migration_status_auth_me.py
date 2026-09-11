"""WP-PPR-MIG-005D exact /auth/me capability projection."""
from __future__ import annotations

import pytest

from app import auth
from app.incoming_information import auth_projection as incoming_auth_projection
from app.operational_orders import auth_projection as operational_auth_projection
from app.security import admin_guard, admin_permissions
from app.services import personnel_visibility_resolver_service


def _project(monkeypatch: pytest.MonkeyPatch, granted: bool) -> dict:
    checked: list[str] = []
    def has_permission(_uid: int, code: str) -> bool:
        checked.append(code)
        return granted and code == admin_permissions.PPR_MIGRATION_STATUS_READ_PERMISSION
    monkeypatch.setattr(auth, "is_privileged", lambda _user: False)
    monkeypatch.setattr(admin_guard, "evaluate_admin_access", lambda _user: False)
    monkeypatch.setattr(admin_permissions, "has_any_personnel_read_permission", lambda _uid: False)
    monkeypatch.setattr(admin_permissions, "has_hr_governance_permission", lambda _uid: False)
    monkeypatch.setattr(admin_permissions, "has_admin_permission", has_permission)
    monkeypatch.setattr(operational_auth_projection, "build_operational_orders_permissions", lambda _u: {})
    monkeypatch.setattr(operational_auth_projection, "has_any_operational_orders_read", lambda _u: False)
    monkeypatch.setattr(incoming_auth_projection, "build_incoming_information_permissions", lambda _u: {})
    monkeypatch.setattr(incoming_auth_projection, "has_any_incoming_information_read", lambda _u: False)
    monkeypatch.setattr(personnel_visibility_resolver_service, "enrich_user_with_personnel_visibility", lambda user: user)
    result = auth.me(auth._enrich_user_context({"user_id": 41, "role_id": 0, "role_code": "ADMIN"}))
    assert admin_permissions.PPR_MIGRATION_STATUS_READ_PERMISSION in checked
    return result


def test_auth_me_projects_only_the_exact_ppr_migration_status_read_grant(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _project(monkeypatch, True)["has_ppr_migration_status_read"] is True


def test_auth_me_does_not_grant_ppr_migration_status_read_from_admin_role(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _project(monkeypatch, False)["has_ppr_migration_status_read"] is False
