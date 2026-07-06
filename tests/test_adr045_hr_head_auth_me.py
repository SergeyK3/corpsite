"""ADR-045 — HR head gets personnel admin flags via HR_HEAD ROLE grant."""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.security.admin_permissions import has_any_personnel_read_permission, has_hr_governance_permission
from app.security.auth_policy import fetch_user_auth_policy_row, is_user_locked
from app.services.access_resolver_service import list_active_access_role_codes
from tests.conftest import auth_headers, table_exists
from tests.test_adr042_role_targeted_grants import (
    _create_user,
    _db_available,
    _require_b2,
    _role_target_type_allowed,
)


def _hr_head_role_id() -> int | None:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT role_id FROM public.roles WHERE code = 'HR_HEAD' LIMIT 1")
        ).first()
        return int(row[0]) if row else None


def _cleanup_ephemeral_user(created: dict) -> None:
    """Remove pytest user/employee/person only — never delete ROLE grants on HR_HEAD."""
    with engine.begin() as conn:
        if table_exists(conn, "access_grants") and created.get("user_id"):
            conn.execute(
                text(
                    "DELETE FROM public.access_grants "
                    "WHERE target_type = 'USER' AND target_id = :id"
                ),
                {"id": created["user_id"]},
            )
        if created.get("user_id"):
            conn.execute(text("DELETE FROM public.users WHERE user_id = :id"), {"id": created["user_id"]})
        if created.get("employee_id"):
            conn.execute(
                text("DELETE FROM public.employee_assignment_links WHERE employee_id = :id"),
                {"id": created["employee_id"]},
            )
            conn.execute(text("DELETE FROM public.employees WHERE employee_id = :id"), {"id": created["employee_id"]})
        if created.get("person_id"):
            conn.execute(text("DELETE FROM public.persons WHERE person_id = :id"), {"id": created["person_id"]})


def _ensure_adr045_hr_head_role_grant() -> None:
    """Test precondition: ADR-045 ROLE grant on HR_HEAD (idempotent, mirrors migration)."""
    with engine.begin() as conn:
        if not table_exists(conn, "access_grants") or not table_exists(conn, "access_roles"):
            return
        conn.execute(
            text(
                """
                INSERT INTO public.access_grants (
                    access_role_id,
                    target_type,
                    target_id,
                    granted_by_user_id,
                    reason
                )
                SELECT
                    ar.access_role_id,
                    'ROLE',
                    r.role_id,
                    COALESCE(
                        (
                            SELECT u.user_id
                            FROM public.users u
                            WHERE lower(u.login) = 'admin'
                              AND u.is_active = TRUE
                            ORDER BY u.user_id
                            LIMIT 1
                        ),
                        1
                    ),
                    'ADR-045: HR head operational contour (HR_ENROLLMENT_MANAGER via HR_HEAD role)'
                FROM public.access_roles ar
                CROSS JOIN public.roles r
                WHERE ar.code = 'HR_ENROLLMENT_MANAGER'
                  AND r.code = 'HR_HEAD'
                  AND NOT EXISTS (
                      SELECT 1
                      FROM public.access_grants g
                      WHERE g.active_flag = TRUE
                        AND g.access_role_id = ar.access_role_id
                        AND g.target_type = 'ROLE'
                        AND g.target_id = r.role_id
                  )
                """
            )
        )


def _create_ephemeral_hr_head_user(seed) -> dict | None:
    """User on migrated HR_HEAD role; avoids seed demo user lock/brute_force state."""
    hr_head_role_id = _hr_head_role_id()
    if hr_head_role_id is None:
        return None

    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        return _create_user(conn, seed, role_id=hr_head_role_id, suffix=suffix)


def _assert_user_can_call_auth_me(uid: int) -> None:
    policy = fetch_user_auth_policy_row(uid)
    assert policy is not None, f"user_id={uid} not found"
    assert policy.get("is_active") is True, f"user_id={uid} is inactive"
    assert not is_user_locked(policy), (
        f"user_id={uid} is locked (locked_at={policy.get('locked_at')!r}, "
        f"reason={policy.get('locked_reason')!r})"
    )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_hr_head_auth_me_has_personnel_admin_via_role_grant(client: TestClient, seed):
    _require_b2()
    if not _role_target_type_allowed():
        pytest.skip("Migration i8j9k0l1m2n3 not applied (ROLE target_type unavailable)")

    _ensure_adr045_hr_head_role_grant()

    created = _create_ephemeral_hr_head_user(seed)
    if created is None:
        pytest.skip("HR_HEAD role missing in database")

    uid = int(created["user_id"])
    try:
        _assert_user_can_call_auth_me(uid)

        resp = client.get("/auth/me", headers=auth_headers(uid))
        assert resp.status_code == 200, resp.text
        body = resp.json()

        assert "HR_ENROLLMENT_MANAGER" in list_active_access_role_codes(uid)
        assert has_any_personnel_read_permission(uid) is True
        assert has_hr_governance_permission(uid) is True
        assert body.get("has_personnel_admin") is True
        assert body.get("has_hr_governance") is True
    finally:
        _cleanup_ephemeral_user(created)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_hr_head_can_list_personnel_events(client: TestClient, seed):
    _require_b2()
    if not _role_target_type_allowed():
        pytest.skip("Migration i8j9k0l1m2n3 not applied (ROLE target_type unavailable)")

    _ensure_adr045_hr_head_role_grant()

    created = _create_ephemeral_hr_head_user(seed)
    if created is None:
        pytest.skip("HR_HEAD role missing in database")

    uid = int(created["user_id"])
    try:
        _assert_user_can_call_auth_me(uid)

        resp = client.get("/directory/personnel-events", headers=auth_headers(uid))
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert isinstance(body.get("items"), list)
    finally:
        _cleanup_ephemeral_user(created)
