from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth
from app.incoming_information import auth_projection as incoming_auth_projection
from app.operational_orders import auth_projection as operational_auth_projection
from app.security import admin_guard, admin_permissions
from app.services import personnel_visibility_resolver_service


def _project(monkeypatch: pytest.MonkeyPatch, *, granted: bool, role_code: str) -> dict:
    checked_codes: list[str] = []

    def has_permission(_user_id: int, code: str) -> bool:
        checked_codes.append(code)
        return granted and code == admin_permissions.CONTROL_LIST_EXPORT_PERMISSION

    monkeypatch.setattr(auth, "is_privileged", lambda _user: False)
    monkeypatch.setattr(auth, "is_system_admin", lambda _user: False)
    monkeypatch.setattr(admin_guard, "evaluate_admin_access", lambda _user: False)
    monkeypatch.setattr(admin_permissions, "has_any_personnel_read_permission", lambda _uid: False)
    monkeypatch.setattr(admin_permissions, "has_hr_governance_permission", lambda _uid: False)
    monkeypatch.setattr(admin_permissions, "has_admin_permission", has_permission)
    monkeypatch.setattr(operational_auth_projection, "build_operational_orders_permissions", lambda _u: {})
    monkeypatch.setattr(operational_auth_projection, "has_any_operational_orders_read", lambda _u: False)
    monkeypatch.setattr(incoming_auth_projection, "build_incoming_information_permissions", lambda _u: {})
    monkeypatch.setattr(incoming_auth_projection, "has_any_incoming_information_read", lambda _u: False)
    monkeypatch.setattr(
        personnel_visibility_resolver_service,
        "enrich_user_with_personnel_visibility",
        lambda user: user,
    )

    result = auth.me(
        auth._enrich_user_context(
            {"user_id": 41, "role_id": 0, "role_code": role_code}
        )
    )
    assert admin_permissions.CONTROL_LIST_EXPORT_PERMISSION in checked_codes
    return result


def test_auth_me_projects_exact_control_list_export_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert _project(monkeypatch, granted=True, role_code="EMPLOYEE")[
        "has_control_list_export"
    ] is True


def test_auth_me_does_not_infer_control_list_export_from_role_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert _project(monkeypatch, granted=False, role_code="HR_HEAD")[
        "has_control_list_export"
    ] is False


def test_cors_exposes_binary_download_headers() -> None:
    from app.main import app

    with TestClient(app) as client:
        response = client.get(
            "/auth/me", headers={"Origin": "http://localhost:3000"}
        )
    exposed = {
        value.strip().lower()
        for value in response.headers["access-control-expose-headers"].split(",")
    }
    assert {"content-disposition", "x-content-sha256", "x-request-id"} <= exposed
