"""ADR-045 — HR head gets personnel admin flags via HR_HEAD ROLE grant."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.security.admin_permissions import has_any_personnel_read_permission, has_hr_governance_permission
from app.services.access_resolver_service import list_active_access_role_codes
from tests.conftest import auth_headers
from tests.test_adr042_role_targeted_grants import _db_available, _require_b2, _role_target_type_allowed


def _hr_head_user_id() -> int | None:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT u.user_id
                FROM public.users u
                JOIN public.roles r ON r.role_id = u.role_id
                WHERE r.code = 'HR_HEAD'
                  AND u.is_active = TRUE
                ORDER BY u.user_id
                LIMIT 1
                """
            )
        ).first()
        return int(row[0]) if row else None


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_hr_head_auth_me_has_personnel_admin_via_role_grant(client: TestClient):
    _require_b2()
    if not _role_target_type_allowed():
        pytest.skip("Migration i8j9k0l1m2n3 not applied (ROLE target_type unavailable)")

    uid = _hr_head_user_id()
    if uid is None:
        pytest.skip("No active HR_HEAD user in database")

    resp = client.get("/auth/me", headers=auth_headers(uid))
    assert resp.status_code == 200
    body = resp.json()

    assert "HR_ENROLLMENT_MANAGER" in list_active_access_role_codes(uid)
    assert has_any_personnel_read_permission(uid) is True
    assert has_hr_governance_permission(uid) is True
    assert body.get("has_personnel_admin") is True
    assert body.get("has_hr_governance") is True
