"""OO-SEC-001 — Leadership Workspace Read Policy tests."""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.security.admin_permissions import has_any_personnel_read_permission
from app.security.directory_scope import SYSTEM_ADMIN_ROLE_ID
from app.security.platform_role_classification import (
    CANONICAL_SEED_PLATFORM_ROLE_CODES,
    LEADERSHIP_PLATFORM_ROLE_CODES,
    OO_SEC_001_GRANT_REASON,
    find_potential_leadership_codes_missing_from_allowlist,
    is_approved_leadership_workspace_read_role,
    looks_like_leadership_platform_role,
)
from app.services.access_resolver_service import list_active_access_role_codes
from tests.conftest import auth_headers, create_role, create_user, table_exists
from tests.test_adr042_role_targeted_grants import (
    _create_user,
    _db_available,
    _get_access_role_id,
    _require_b2,
    _role_target_type_allowed,
)
from tests.test_adr045_hr_head_auth_me import _ensure_adr045_hr_head_role_grant

_OO_READ_PERMISSION = "OPERATIONAL_ORDERS_INTAKE_READ"
_LEGACY_OO_SEC_001_GRANT_REASON = "OO-SEC-001: approved leadership default read policy"


def _role_id_by_code(code: str) -> int | None:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT role_id FROM public.roles WHERE code = :code LIMIT 1"),
            {"code": code},
        ).first()
        return int(row[0]) if row else None


def _cleanup_ephemeral_user(created: dict) -> None:
    with engine.begin() as conn:
        if table_exists(conn, "access_grants") and created.get("user_id"):
            conn.execute(
                text("DELETE FROM public.access_grants WHERE target_type = 'USER' AND target_id = :id"),
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


def _create_ephemeral_user_for_role(seed, *, role_id: int) -> dict:
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        return _create_user(conn, seed, role_id=role_id, suffix=suffix)


def _ensure_oo_sec_001_role_grants() -> None:
    """Test precondition: OO-SEC-001 ROLE grants (idempotent, mirrors migration)."""
    codes_sql = ", ".join(f"'{code}'" for code in sorted(LEADERSHIP_PLATFORM_ROLE_CODES))
    reason = OO_SEC_001_GRANT_REASON.replace("'", "''")
    legacy_reason = _LEGACY_OO_SEC_001_GRANT_REASON.replace("'", "''")
    with engine.begin() as conn:
        if not table_exists(conn, "access_grants") or not table_exists(conn, "access_roles"):
            return
        conn.execute(
            text(
                f"""
                UPDATE public.access_grants g
                SET reason = '{reason}'
                FROM public.access_roles ar, public.roles r
                WHERE g.access_role_id = ar.access_role_id
                  AND g.target_type = 'ROLE'
                  AND g.target_id = r.role_id
                  AND ar.code = '{_OO_READ_PERMISSION}'
                  AND r.code IN ({codes_sql})
                  AND g.active_flag = TRUE
                  AND g.reason = '{legacy_reason}'
                """
            )
        )
        conn.execute(
            text(
                f"""
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
                    '{reason}'
                FROM public.access_roles ar
                CROSS JOIN public.roles r
                WHERE ar.code = '{_OO_READ_PERMISSION}'
                  AND ar.is_active = TRUE
                  AND r.code IN ({codes_sql})
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


def _count_active_oo_sec_grants_for_role(role_code: str) -> int:
    with engine.connect() as conn:
        return int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*)::int
                    FROM public.access_grants g
                    JOIN public.access_roles ar ON ar.access_role_id = g.access_role_id
                    JOIN public.roles r ON r.role_id = g.target_id
                    WHERE g.active_flag = TRUE
                      AND g.target_type = 'ROLE'
                      AND ar.code = :perm
                      AND r.code = :role_code
                      AND g.reason = :reason
                    """
                ),
                {
                    "perm": _OO_READ_PERMISSION,
                    "role_code": role_code,
                    "reason": OO_SEC_001_GRANT_REASON,
                },
            ).scalar_one()
        )


class TestApprovedAllowlist:
    @pytest.mark.parametrize(
        "role_code",
        sorted(LEADERSHIP_PLATFORM_ROLE_CODES),
    )
    def test_approved_leadership_roles(self, role_code: str) -> None:
        assert is_approved_leadership_workspace_read_role(role_code) is True

    @pytest.mark.parametrize(
        "role_code",
        [
            "QM_HOSP",
            "QM_AMB",
            "ECON_1",
            "ECON_2",
            "ECON_3",
            "STAT_EROB_INPUT",
            "STAT_EROB_OUTPUT",
            "STAT_EROB_ANALYTICS",
            "QM_COMPLAINT_REG",
            "QM_COMPLAINT_PAT",
            "QM_TRAINING_EXPERT",
            "",
            "UNKNOWN_ROLE",
        ],
    )
    def test_non_leadership_roles_rejected(self, role_code: str) -> None:
        assert is_approved_leadership_workspace_read_role(role_code) is False

    def test_lab_head_fail_closed(self) -> None:
        assert is_approved_leadership_workspace_read_role("LAB_HEAD") is False
        assert looks_like_leadership_platform_role("LAB_HEAD") is True

    def test_admin_excluded_from_approved_allowlist(self) -> None:
        assert is_approved_leadership_workspace_read_role("ADMIN") is False
        assert is_approved_leadership_workspace_read_role("SYSTEM_ADMIN") is False
        assert "ADMIN" not in LEADERSHIP_PLATFORM_ROLE_CODES
        assert "SYSTEM_ADMIN" not in LEADERSHIP_PLATFORM_ROLE_CODES

    def test_canonical_seed_has_no_unreviewed_leadership_codes(self) -> None:
        missing = find_potential_leadership_codes_missing_from_allowlist(
            CANONICAL_SEED_PLATFORM_ROLE_CODES
        )
        assert missing == frozenset(), (
            "Canonical seed contains leadership-looking role codes not in approved allowlist: "
            f"{sorted(missing)}. Update allowlist via explicit policy review."
        )

    def test_migration_allowlist_matches_classifier(self) -> None:
        migration_codes = frozenset(
            {
                "DIRECTOR",
                "DEP_MED",
                "DEP_OUTPATIENT_AUDIT",
                "DEP_ADMIN",
                "DEP_STRATEGY",
                "STAT_HEAD",
                "STAT_HEAD_DEPUTY",
                "QM_HEAD",
                "HR_HEAD",
                "ACC_HEAD",
                "ECON_HEAD",
            }
        )
        assert migration_codes == LEADERSHIP_PLATFORM_ROLE_CODES


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
class TestMigrationAndProjection:
    def test_migration_idempotent_for_director(self) -> None:
        _require_b2()
        if not _role_target_type_allowed():
            pytest.skip("ROLE target_type unavailable")

        if _role_id_by_code("DIRECTOR") is None:
            pytest.skip("DIRECTOR role missing in database")

        _ensure_oo_sec_001_role_grants()
        first = _count_active_oo_sec_grants_for_role("DIRECTOR")
        assert first >= 1

        _ensure_oo_sec_001_role_grants()
        second = _count_active_oo_sec_grants_for_role("DIRECTOR")
        assert second == first

    def test_director_auth_me_has_operational_orders_read(self, client: TestClient, seed) -> None:
        _require_b2()
        if not _role_target_type_allowed():
            pytest.skip("ROLE target_type unavailable")

        _ensure_oo_sec_001_role_grants()
        role_id = _role_id_by_code("DIRECTOR")
        if role_id is None:
            pytest.skip("DIRECTOR role missing")

        created = _create_ephemeral_user_for_role(seed, role_id=role_id)
        uid = int(created["user_id"])
        try:
            assert _OO_READ_PERMISSION in list_active_access_role_codes(uid)
            resp = client.get("/auth/me", headers=auth_headers(uid))
            assert resp.status_code == 200, resp.text
            assert resp.json().get("has_operational_orders_read") is True
        finally:
            _cleanup_ephemeral_user(created)

    def test_qm_hosp_negative_projection(self, client: TestClient, seed) -> None:
        _require_b2()
        if not _role_target_type_allowed():
            pytest.skip("ROLE target_type unavailable")

        _ensure_oo_sec_001_role_grants()
        role_id = _role_id_by_code("QM_HOSP")
        if role_id is None:
            pytest.skip("QM_HOSP role missing")

        created = _create_ephemeral_user_for_role(seed, role_id=role_id)
        uid = int(created["user_id"])
        try:
            assert _OO_READ_PERMISSION not in list_active_access_role_codes(uid)
            resp = client.get("/auth/me", headers=auth_headers(uid))
            assert resp.status_code == 200, resp.text
            assert resp.json().get("has_operational_orders_read") is False
        finally:
            _cleanup_ephemeral_user(created)

    def test_hr_head_keeps_hr_and_gains_oo_read(self, client: TestClient, seed) -> None:
        _require_b2()
        if not _role_target_type_allowed():
            pytest.skip("ROLE target_type unavailable")

        _ensure_adr045_hr_head_role_grant()
        _ensure_oo_sec_001_role_grants()

        role_id = _role_id_by_code("HR_HEAD")
        if role_id is None:
            pytest.skip("HR_HEAD role missing")

        created = _create_ephemeral_user_for_role(seed, role_id=role_id)
        uid = int(created["user_id"])
        try:
            codes = set(list_active_access_role_codes(uid))
            assert "HR_ENROLLMENT_MANAGER" in codes
            assert _OO_READ_PERMISSION in codes
            assert has_any_personnel_read_permission(uid) is True

            resp = client.get("/auth/me", headers=auth_headers(uid))
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body.get("has_personnel_admin") is True
            assert body.get("has_operational_orders_read") is True
        finally:
            _cleanup_ephemeral_user(created)

    def test_hr_permission_alone_is_not_oo_bypass(self, client: TestClient, seed) -> None:
        _require_b2()
        if not _role_target_type_allowed():
            pytest.skip("ROLE target_type unavailable")

        _ensure_adr045_hr_head_role_grant()

        suffix = uuid4().hex[:8]
        with engine.begin() as conn:
            hr_role_id = _get_access_role_id(conn, "HR_ENROLLMENT_MANAGER")
            custom_role_id = create_role(conn, f"pytest_oo_sec_hr_only_{suffix}")
            conn.execute(
                text(
                    """
                    INSERT INTO public.access_grants (
                        access_role_id, target_type, target_id, granted_by_user_id, reason
                    )
                    VALUES (:arid, 'ROLE', :rid, 1, 'pytest OO-SEC-001 HR-only regression')
                    """
                ),
                {"arid": hr_role_id, "rid": custom_role_id},
            )
            created = _create_user(conn, seed, role_id=custom_role_id, suffix=suffix)

        uid = int(created["user_id"])
        try:
            assert "HR_ENROLLMENT_MANAGER" in list_active_access_role_codes(uid)
            assert _OO_READ_PERMISSION not in list_active_access_role_codes(uid)

            resp = client.get("/auth/me", headers=auth_headers(uid))
            assert resp.status_code == 200, resp.text
            assert resp.json().get("has_personnel_admin") is True
            assert resp.json().get("has_operational_orders_read") is False
        finally:
            _cleanup_ephemeral_user(created)
            with engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        DELETE FROM public.access_grants
                        WHERE target_type = 'ROLE'
                          AND target_id = :rid
                          AND reason = 'pytest OO-SEC-001 HR-only regression'
                        """
                    ),
                    {"rid": custom_role_id},
                )
                conn.execute(text("DELETE FROM public.roles WHERE role_id = :rid"), {"rid": custom_role_id})

    def test_system_admin_privileged_without_oo_sec_grant(self, client: TestClient, seed) -> None:
        _require_b2()

        _ensure_oo_sec_001_role_grants()

        with engine.connect() as conn:
            count = conn.execute(
                text(
                    """
                    SELECT COUNT(*)::int
                    FROM public.access_grants g
                    JOIN public.access_roles ar ON ar.access_role_id = g.access_role_id
                    WHERE g.active_flag = TRUE
                      AND g.target_type = 'ROLE'
                      AND g.target_id = :rid
                      AND ar.code = :perm
                      AND g.reason = :reason
                    """
                ),
                {
                    "rid": int(SYSTEM_ADMIN_ROLE_ID),
                    "perm": _OO_READ_PERMISSION,
                    "reason": OO_SEC_001_GRANT_REASON,
                },
            ).scalar_one()
        assert count == 0

        suffix = uuid4().hex[:8]
        with engine.begin() as conn:
            admin_uid = create_user(
                conn,
                full_name=f"Pytest OO SEC Sysadmin {suffix}",
                role_id=int(SYSTEM_ADMIN_ROLE_ID),
                unit_id=int(seed["unit_id"]),
            )

        try:
            resp = client.get("/auth/me", headers=auth_headers(admin_uid))
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body.get("is_privileged") is True
            assert body.get("has_operational_orders_read") is True
            assert _OO_READ_PERMISSION not in list_active_access_role_codes(admin_uid)
        finally:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM public.users WHERE user_id = :uid"), {"uid": admin_uid})
