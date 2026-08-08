from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi import HTTPException

from app import auth
from app.security import admin_guard, admin_permissions
from app.operational_orders import auth_projection as operational_auth_projection
from app.incoming_information import auth_projection as incoming_auth_projection
from app.services import directory_service, personnel_visibility_resolver_service


def _project_auth_me(monkeypatch: pytest.MonkeyPatch, *, exact_permission: bool, role_code: str) -> dict:
    monkeypatch.setattr(auth, "is_privileged", lambda _user: False)
    monkeypatch.setattr(auth, "is_system_admin", lambda _user: False)
    monkeypatch.setattr(admin_guard, "evaluate_admin_access", lambda _user: False)
    monkeypatch.setattr(admin_permissions, "has_any_personnel_read_permission", lambda _uid: False)
    monkeypatch.setattr(admin_permissions, "has_hr_governance_permission", lambda _uid: False)
    monkeypatch.setattr(
        admin_permissions,
        "has_admin_permission",
        lambda _uid, code: exact_permission if code == "HR_ENROLLMENT_MANAGER" else False,
    )
    monkeypatch.setattr(operational_auth_projection, "build_operational_orders_permissions", lambda _u: {})
    monkeypatch.setattr(operational_auth_projection, "has_any_operational_orders_read", lambda _u: False)
    monkeypatch.setattr(incoming_auth_projection, "build_incoming_information_permissions", lambda _u: {})
    monkeypatch.setattr(incoming_auth_projection, "has_any_incoming_information_read", lambda _u: False)
    monkeypatch.setattr(
        personnel_visibility_resolver_service,
        "enrich_user_with_personnel_visibility",
        lambda user: user,
    )
    return auth.me(auth._enrich_user_context({"user_id": 41, "role_id": 0, "role_code": role_code}))


def test_auth_me_projects_exact_hr_enrollment_manager_permission(monkeypatch: pytest.MonkeyPatch):
    body = _project_auth_me(monkeypatch, exact_permission=True, role_code="EMPLOYEE")
    assert body["has_hr_enrollment_manager"] is True


def test_auth_me_view_only_user_does_not_get_hr_enrollment_manager(monkeypatch: pytest.MonkeyPatch):
    body = _project_auth_me(monkeypatch, exact_permission=False, role_code="PERSONNEL_VIEWER")
    assert body["has_hr_enrollment_manager"] is False


def test_auth_me_does_not_infer_permission_from_hr_head_role(monkeypatch: pytest.MonkeyPatch):
    body = _project_auth_me(monkeypatch, exact_permission=False, role_code="HR_HEAD")
    assert body["has_hr_enrollment_manager"] is False


@dataclass
class _ScalarResult:
    values: list[int]

    def scalars(self) -> "_ScalarResult":
        return self

    def all(self) -> list[int]:
        return self.values


class _AssignmentConnection:
    def __init__(self, assignment_ids: list[int]):
        self.assignment_ids = assignment_ids

    def execute(self, statement, params):
        assert "active_flag IS TRUE" in str(statement)
        assert "lifecycle_status = 'active'" in str(statement)
        assert params == {"person_id": 105}
        return _ScalarResult(self.assignment_ids)


def test_employee_detail_active_assignment_id_for_single_active_assignment():
    value = directory_service._get_single_active_assignment_id(
        _AssignmentConnection([107]),
        person_id=105,
    )
    assert value == 107


def test_employee_detail_active_assignment_id_is_null_without_active_assignment():
    value = directory_service._get_single_active_assignment_id(
        _AssignmentConnection([]),
        person_id=105,
    )
    assert value is None


def test_employee_detail_multiple_active_assignments_fail_closed():
    with pytest.raises(HTTPException) as caught:
        directory_service._get_single_active_assignment_id(
            _AssignmentConnection([107, 108]),
            person_id=105,
        )

    assert caught.value.status_code == 409
    assert caught.value.detail["code"] == "ACTIVE_ASSIGNMENT_CARDINALITY_INVALID"
