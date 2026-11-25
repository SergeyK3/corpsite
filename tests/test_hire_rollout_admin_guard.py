import pytest
from fastapi import HTTPException

from app.api.admin_hire_approval_routes import require_hire_rollout_admin
from app.directory import electronic_hire_routes


def test_rollout_requires_system_admin_role() -> None:
    assert require_hire_rollout_admin({"user_id": 7, "role_id": 2})["user_id"] == 7
    for role_id, role_code in ((1, "HR_HEAD"), (4, "ADMIN"), (5, "EMPLOYEE")):
        with pytest.raises(HTTPException) as denied:
            require_hire_rollout_admin({"user_id": 8, "role_id": role_id, "role_code": role_code})
        assert denied.value.status_code == 403


def test_statement_uses_approval_visibility_before_reading_document(monkeypatch) -> None:
    monkeypatch.setattr(electronic_hire_routes, "list_head_electronic_hire_approvals",
                        lambda **_: {"items": [{"application_id": 54}]})
    with pytest.raises(HTTPException) as denied:
        electronic_hire_routes.get_head_electronic_hire_statement(55, {"user_id": 6})
    assert denied.value.status_code == 404
