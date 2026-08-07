"""HR_HEAD gets a separate Incoming Information registration ROLE grant."""
from __future__ import annotations

import runpy
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.incoming_information.permissions import (
    can_control,
    can_execute,
    can_read,
    can_register,
    can_resolve,
    can_restricted_bypass,
)
from app.services.access_resolver_service import list_active_access_role_codes
from tests.conftest import auth_headers
from tests.test_adr042_role_targeted_grants import (
    _create_user,
    _db_available,
    _require_b2,
    _role_target_type_allowed,
)
from tests.test_adr045_hr_head_auth_me import (
    _assert_user_can_call_auth_me,
    _cleanup_ephemeral_user,
)
from tests.test_hr_head_incoming_information_read import (
    _ROLE_CODE,
    _ROLE_NAME,
    _cleanup_test_role_grant,
    _ensure_test_role_grant,
    hr_head_role_not_14,
)

_READ_PERMISSION_CODE = "INCOMING_INFO_READ"
_REGISTER_PERMISSION_CODE = "INCOMING_INFO_REGISTER"
_PROHIBITED_WORKFLOW_OR_BYPASS_CODES = {
    "INCOMING_INFO_RESOLVE",
    "INCOMING_INFO_EXECUTE",
    "INCOMING_INFO_CONTROL",
    "INCOMING_INFO_RESTRICTED_BYPASS",
}


def _load_migration() -> dict:
    return runpy.run_path(
        str(
            Path(__file__).resolve().parents[1]
            / "alembic"
            / "versions"
            / "i6j7k8l9m0n1_hr_head_incoming_info_register_grant.py"
        )
    )


def _delete_registration_grant() -> None:
    migration = _load_migration()
    with engine.begin() as conn:
        conn.execute(
            text(
                "DELETE FROM public.access_grants "
                "WHERE target_type = 'ROLE' AND reason = :reason"
            ),
            {"reason": migration["_GRANT_REASON"]},
        )


def test_registration_migration_uses_only_canonical_role_and_permission(
    monkeypatch,
) -> None:
    migration = _load_migration()
    statements: list[str] = []
    monkeypatch.setattr(migration["op"], "execute", statements.append)

    migration["upgrade"]()

    assert migration["down_revision"] == "h5c6d7e8f9a0"
    assert migration["_ROLE_CODE"] == "HR_HEAD"
    assert migration["_PERMISSION_CODE"] == _REGISTER_PERMISSION_CODE
    assert len(statements) == 1
    statement = statements[0]
    assert "WHERE code = 'HR_HEAD'" in statement
    assert "WHERE code = 'INCOMING_INFO_REGISTER'" in statement
    assert "QM_HEAD" not in statement
    assert "role_id = 14" not in statement
    assert "user_id = 8" not in statement
    assert "employee_id" not in statement
    assert "Макибаева" not in statement
    assert "Өсерова" not in statement


def test_registration_migration_is_fail_closed(monkeypatch) -> None:
    migration = _load_migration()
    statements: list[str] = []
    monkeypatch.setattr(migration["op"], "execute", statements.append)

    migration["upgrade"]()

    statement = statements[0]
    assert "v_role_count <> 1" in statement
    assert "v_permission_count <> 1" in statement
    assert "v_permission_active IS DISTINCT FROM TRUE" in statement
    assert "RAISE EXCEPTION" in statement
    assert "g.active_flag = TRUE" in statement
    assert "g.starts_at <= statement_timestamp()" in statement


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_registration_migration_grants_actual_hr_head_not_role_14(
    monkeypatch,
    hr_head_role_not_14: int,
) -> None:
    migration = _load_migration()
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            monkeypatch.setattr(
                migration["op"],
                "execute",
                lambda statement: conn.execute(text(statement)),
            )
            migration["upgrade"]()
            migration["upgrade"]()

            rows = conn.execute(
                text(
                    "SELECT g.target_id, r.code AS role_code, ar.code AS permission_code "
                    "FROM public.access_grants g "
                    "JOIN public.roles r ON r.role_id = g.target_id "
                    "JOIN public.access_roles ar ON ar.access_role_id = g.access_role_id "
                    "WHERE g.target_type = 'ROLE' AND g.reason = :reason"
                ),
                {"reason": migration["_GRANT_REASON"]},
            ).mappings().all()
            assert [dict(row) for row in rows] == [
                {
                    "target_id": hr_head_role_not_14,
                    "role_code": _ROLE_CODE,
                    "permission_code": _REGISTER_PERMISSION_CODE,
                }
            ]

            migration["downgrade"]()
            assert conn.execute(
                text("SELECT COUNT(*) FROM public.access_grants WHERE reason = :reason"),
                {"reason": migration["_GRANT_REASON"]},
            ).scalar_one() == 0
        finally:
            transaction.rollback()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_hr_head_auth_me_has_separate_read_and_register_permissions(
    client: TestClient,
    seed,
    monkeypatch,
    hr_head_role_not_14: int,
) -> None:
    _require_b2()
    if not _role_target_type_allowed():
        pytest.skip("ROLE target_type is unavailable")

    migration = _load_migration()
    created = None
    try:
        _ensure_test_role_grant(hr_head_role_not_14, int(seed["initiator_user_id"]))
        with engine.begin() as conn:
            monkeypatch.setattr(
                migration["op"],
                "execute",
                lambda statement: conn.execute(text(statement)),
            )
            migration["upgrade"]()
            created = _create_user(
                conn,
                seed,
                role_id=hr_head_role_not_14,
                suffix=uuid4().hex[:8],
            )

        uid = int(created["user_id"])
        user_ctx = {
            "user_id": uid,
            "role_id": hr_head_role_not_14,
            "role_code": _ROLE_CODE,
            "unit_id": int(seed["unit_id"]),
        }
        _assert_user_can_call_auth_me(uid)

        active_codes = set(list_active_access_role_codes(uid))
        assert {_READ_PERMISSION_CODE, _REGISTER_PERMISSION_CODE}.issubset(active_codes)
        assert active_codes.isdisjoint(_PROHIBITED_WORKFLOW_OR_BYPASS_CODES)

        response = client.get("/auth/me", headers=auth_headers(uid))
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["user_id"] == uid
        assert body["role_id"] == hr_head_role_not_14
        assert body["role_code"] == _ROLE_CODE
        assert body["role_name_ru"] == _ROLE_NAME
        assert body["incoming_information_permissions"] == {
            "register": True,
            "read": True,
            "resolve": False,
            "execute": False,
            "control": False,
            "restricted_bypass": False,
        }
        assert body["has_incoming_information_read"] is True

        assert can_read(user_ctx) is True
        assert can_register(user_ctx) is True
        assert can_resolve(user_ctx) is False
        assert can_execute(user_ctx) is False
        assert can_control(user_ctx) is False
        assert can_restricted_bypass(user_ctx) is False
    finally:
        if created is not None:
            _cleanup_ephemeral_user(created)
        _delete_registration_grant()
        _cleanup_test_role_grant(hr_head_role_not_14)
