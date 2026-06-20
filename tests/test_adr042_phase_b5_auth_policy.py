# tests/test_adr042_phase_b5_auth_policy.py
"""Tests for ADR-042 Phase B5 auth policy (lockout, token_version, must_change_password)."""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.auth import create_access_token, hash_password
from app.db.engine import engine
from app.services.admin_password_reset_service import issue_temporary_password
from app.services.security_audit_service import sanitize_metadata, write_security_event
from tests.conftest import auth_headers, get_columns, table_exists

PASSWORD = "SecretPass1"


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _users_policy_columns_available() -> bool:
    with engine.connect() as conn:
        if not table_exists(conn, "users"):
            return False
        cols = get_columns(conn, "users")
    needed = {"login", "password_hash", "locked_at", "failed_login_count", "token_version"}
    return needed.issubset(cols)


def _set_user_login_password(user_id: int, login: str, password: str) -> None:
    ph = hash_password(password)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE public.users
                SET login = :login,
                    password_hash = :ph,
                    locked_at = NULL,
                    locked_reason = NULL,
                    locked_until = NULL,
                    failed_login_count = 0,
                    must_change_password = FALSE
                WHERE user_id = :uid
                """
            ),
            {"login": login, "ph": ph, "uid": int(user_id)},
        )


def _get_failed_login_count(user_id: int) -> int:
    with engine.connect() as conn:
        return int(
            conn.execute(
                text("SELECT COALESCE(failed_login_count, 0) FROM public.users WHERE user_id = :uid"),
                {"uid": int(user_id)},
            ).scalar_one()
        )


def _cleanup_login_audit(user_id: int) -> None:
    with engine.begin() as conn:
        if table_exists(conn, "security_audit_log"):
            conn.execute(
                text(
                    """
                    DELETE FROM public.security_audit_log
                    WHERE target_user_id = :uid
                       OR actor_user_id = :uid
                    """
                ),
                {"uid": int(user_id)},
            )


@pytest.fixture
def login_user(seed):
    if not _users_policy_columns_available():
        pytest.skip("users auth policy columns missing")
    suffix = uuid4().hex[:8]
    login = f"b5_auth_{suffix}"
    user_id = int(seed["executor_user_id"])
    _set_user_login_password(user_id, login, PASSWORD)
    yield {"user_id": user_id, "login": login}
    _set_user_login_password(user_id, f"reset_{suffix}@pytest.local", PASSWORD)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE public.users
                SET locked_at = NULL,
                    locked_reason = NULL,
                    failed_login_count = 0,
                    must_change_password = FALSE,
                    token_version = 1
                WHERE user_id = :uid
                """
            ),
            {"uid": user_id},
        )
    _cleanup_login_audit(user_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_locked_user_cannot_login(client: TestClient, login_user):
    user_id = int(login_user["user_id"])
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE public.users
                    SET locked_at = now(), locked_reason = 'admin', failed_login_count = 0
                    WHERE user_id = :uid
                    """
                ),
                {"uid": user_id},
            )

        resp = client.post(
            "/auth/login",
            json={"login": login_user["login"], "password": PASSWORD},
        )
        assert resp.status_code == 403
        assert "locked" in resp.json()["detail"].lower()
    finally:
        _cleanup_login_audit(user_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_failed_login_increments_failed_login_count(client: TestClient, login_user):
    user_id = int(login_user["user_id"])
    before = _get_failed_login_count(user_id)
    try:
        resp = client.post(
            "/auth/login",
            json={"login": login_user["login"], "password": "wrong-password"},
        )
        assert resp.status_code == 401
        after = _get_failed_login_count(user_id)
        assert after == before + 1
    finally:
        _cleanup_login_audit(user_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_lockout_after_threshold(client: TestClient, login_user, monkeypatch):
    user_id = int(login_user["user_id"])
    monkeypatch.setenv("ADR042_LOGIN_MAX_FAILED_ATTEMPTS", "3")
    try:
        for _ in range(3):
            resp = client.post(
                "/auth/login",
                json={"login": login_user["login"], "password": "wrong-password"},
            )
            assert resp.status_code == 401

        with engine.connect() as conn:
            locked_at = conn.execute(
                text("SELECT locked_at FROM public.users WHERE user_id = :uid"),
                {"uid": user_id},
            ).scalar_one()
        assert locked_at is not None

        blocked = client.post(
            "/auth/login",
            json={"login": login_user["login"], "password": PASSWORD},
        )
        assert blocked.status_code == 403
    finally:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE public.users
                    SET locked_at = NULL,
                        locked_reason = NULL,
                        failed_login_count = 0
                    WHERE user_id = :uid
                    """
                ),
                {"uid": user_id},
            )
        _cleanup_login_audit(user_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_successful_login_resets_failed_count(client: TestClient, login_user):
    user_id = int(login_user["user_id"])
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE public.users
                    SET failed_login_count = 2
                    WHERE user_id = :uid
                    """
                ),
                {"uid": user_id},
            )

        resp = client.post(
            "/auth/login",
            json={"login": login_user["login"], "password": PASSWORD},
        )
        assert resp.status_code == 200
        assert _get_failed_login_count(user_id) == 0
    finally:
        _cleanup_login_audit(user_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_token_version_mismatch_rejected_only_when_flag_enabled(client: TestClient, seed, monkeypatch):
    user_id = int(seed["executor_user_id"])
    monkeypatch.delenv("ADR042_TOKEN_VERSION_ENFORCEMENT", raising=False)

    stale_token = create_access_token(user_id, token_version=1)
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE public.users SET token_version = 2 WHERE user_id = :uid"),
            {"uid": user_id},
        )

    try:
        ok = client.get("/auth/me", headers={"Authorization": f"Bearer {stale_token}"})
        assert ok.status_code == 200

        monkeypatch.setenv("ADR042_TOKEN_VERSION_ENFORCEMENT", "true")
        bad = client.get("/auth/me", headers={"Authorization": f"Bearer {stale_token}"})
        assert bad.status_code == 401
    finally:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE public.users SET token_version = 1 WHERE user_id = :uid"),
                {"uid": user_id},
            )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_must_change_password_enforcement_only_when_flag_enabled(client: TestClient, seed, monkeypatch):
    user_id = int(seed["executor_user_id"])
    token = create_access_token(user_id, token_version=1)
    headers = {"Authorization": f"Bearer {token}"}

    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE public.users
                    SET must_change_password = TRUE
                    WHERE user_id = :uid
                    """
                ),
                {"uid": user_id},
            )

        monkeypatch.delenv("ADR042_MUST_CHANGE_PASSWORD_ENFORCEMENT", raising=False)
        allowed = client.get("/auth/me", headers=headers)
        assert allowed.status_code == 200

        monkeypatch.setenv("ADR042_MUST_CHANGE_PASSWORD_ENFORCEMENT", "true")
        blocked = client.get("/auth/me", headers=headers)
        assert blocked.status_code == 403

        password_change = client.post(
            "/auth/password-change",
            headers=headers,
            json={"current_password": "x", "new_password": "NewPass123"},
        )
        assert password_change.status_code == 501
    finally:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE public.users
                    SET must_change_password = FALSE
                    WHERE user_id = :uid
                    """
                ),
                {"uid": user_id},
            )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_audit_metadata_sanitizer_blocks_sensitive_keys():
    with pytest.raises(ValueError):
        sanitize_metadata({"password": "secret"})

    with pytest.raises(ValueError):
        sanitize_metadata({"note": "ok", "access_token": "abc"})

    with pytest.raises(ValueError):
        sanitize_metadata({"password_hash": "abc"})

    clean = sanitize_metadata({"grant_id": 1, "action": "test"})
    assert clean == {"grant_id": 1, "action": "test"}


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_admin_password_reset_stub_not_implemented(seed):
    with pytest.raises(NotImplementedError):
        issue_temporary_password(
            user_id=int(seed["executor_user_id"]),
            actor_user_id=int(seed["initiator_user_id"]),
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_write_security_event_rejects_password_metadata(seed):
    with engine.connect() as conn:
        if not table_exists(conn, "security_audit_log"):
            pytest.skip("security_audit_log missing")
    with pytest.raises(ValueError):
        write_security_event(
            event_type="LOGIN_FAILED",
            actor_user_id=int(seed["executor_user_id"]),
            metadata={"password": "must-not-persist"},
        )
