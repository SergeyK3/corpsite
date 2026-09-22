# tests/test_tg_bind_jwt_auth.py
from __future__ import annotations

from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.auth import create_access_token
from app.db.engine import engine
from app.security.directory_scope import legacy_x_user_id_enabled, require_uid, user_id_from_authorization
from app.tg_bind import _hash_code
from tests.conftest import auth_headers


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def test_user_id_from_authorization_resolves_jwt() -> None:
    user_id = 4242
    token = create_access_token(user_id)
    assert user_id_from_authorization(f"Bearer {token}") == user_id


def test_user_id_from_authorization_rejects_missing_bearer() -> None:
    assert user_id_from_authorization(None) is None
    assert user_id_from_authorization("") is None
    assert user_id_from_authorization("Basic abc") is None


def test_require_uid_jwt_first_when_legacy_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_LEGACY_X_USER_ID", "0")
    monkeypatch.setenv("APP_ENV", "prod")

    assert legacy_x_user_id_enabled() is False

    token = create_access_token(77)
    assert require_uid(authorization=f"Bearer {token}", x_user_id="999") == 77


def test_require_uid_legacy_x_user_id_blocked_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_LEGACY_X_USER_ID", "0")
    monkeypatch.setenv("APP_ENV", "prod")

    with pytest.raises(Exception) as exc_info:
        require_uid(authorization=None, x_user_id="123")

    assert getattr(exc_info.value, "status_code", None) == 401


@pytest.fixture(autouse=True)
def _clear_bind_codes() -> None:
    if not _db_available():
        yield
        return
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM public.telegram_bind_codes"))
    yield
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM public.telegram_bind_codes"))


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_tg_bind_code_succeeds_for_jwt_authenticated_user(
    client: TestClient,
    seed: Dict[str, Any],
) -> None:
    user_id = int(seed["executor_user_id"])
    resp = client.post("/me/tg-bind-code", headers=auth_headers(user_id))
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert isinstance(body.get("code"), str) and body["code"].strip()
    assert body.get("expires_at")


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_tg_bind_code_forbidden_without_authorization(client: TestClient) -> None:
    resp = client.post("/me/tg-bind-code")
    assert resp.status_code == 403, resp.text

    assert _response_error_code(resp.json()) == "TGBIND_FORBIDDEN_NOT_AUTH"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_tg_bind_code_legacy_x_user_id_blocked_when_disabled(
    client: TestClient,
    seed: Dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENABLE_LEGACY_X_USER_ID", "0")
    monkeypatch.setenv("APP_ENV", "prod")

    user_id = int(seed["executor_user_id"])
    resp = client.post("/me/tg-bind-code", headers={"X-User-Id": str(user_id)})
    assert resp.status_code == 403, resp.text
    assert _response_error_code(resp.json()) == "TGBIND_FORBIDDEN_NOT_AUTH"


def _response_error_code(body: dict[str, Any]) -> str | None:
    code = body.get("code")
    if isinstance(code, str) and code.strip():
        return code.strip()
    detail = body.get("detail")
    if isinstance(detail, dict):
        nested = detail.get("code")
        if isinstance(nested, str) and nested.strip():
            return nested.strip()
    return None


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_tg_bind_code_regenerate_invalidates_previous_code(
    client: TestClient,
    seed: Dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.tg_bind.BOT_BIND_TOKEN", "test-bot-bind-token")

    user_id = int(seed["executor_user_id"])
    headers = auth_headers(user_id)
    tg_user_id = 9_000_000_001

    resp1 = client.post("/me/tg-bind-code", headers=headers)
    assert resp1.status_code == 200, resp1.text
    code1 = str(resp1.json().get("code") or "").strip()
    assert code1

    resp2 = client.post("/me/tg-bind-code", headers=headers)
    assert resp2.status_code == 200, resp2.text
    code2 = str(resp2.json().get("code") or "").strip()
    assert code2
    assert code2 != code1

    consume_headers = {"X-Bot-Bind-Token": "test-bot-bind-token"}

    stale = client.post(
        "/tg/bind/consume",
        headers=consume_headers,
        json={"code": code1, "tg_user_id": tg_user_id},
    )
    assert stale.status_code == 409, stale.text
    assert _response_error_code(stale.json()) == "TGBIND_CONFLICT_CODE_INVALID"

    fresh = client.post(
        "/tg/bind/consume",
        headers=consume_headers,
        json={"code": code2, "tg_user_id": tg_user_id},
    )
    assert fresh.status_code == 200, fresh.text
    assert int(fresh.json().get("user_id") or 0) == user_id

    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE public.users SET telegram_id = NULL, telegram_username = NULL, "
                "telegram_bound_at = NULL WHERE user_id = :uid"
            ),
            {"uid": user_id},
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_tg_bind_code_survives_new_db_session_and_is_consumed_once(
    client: TestClient,
    seed: Dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.tg_bind.BOT_BIND_TOKEN", "test-bot-bind-token")

    user_id = int(seed["executor_user_id"])
    issued = client.post("/me/tg-bind-code", headers=auth_headers(user_id))
    assert issued.status_code == 200, issued.text
    code = str(issued.json()["code"])

    # This is a fresh DB session after the issuing endpoint committed and closed.
    with engine.connect() as conn:
        persisted = conn.execute(
            text(
                "SELECT user_id, code_hash, created_at, expires_at, used_at, invalidated_at "
                "FROM public.telegram_bind_codes WHERE code_hash = :code_hash"
            ),
            {"code_hash": _hash_code(code)},
        ).mappings().one()
    assert int(persisted["user_id"]) == user_id
    assert persisted["code_hash"] != code
    assert persisted["created_at"] is not None
    assert persisted["expires_at"] is not None
    assert persisted["used_at"] is None
    assert persisted["invalidated_at"] is None

    consumed = client.post(
        "/tg/bind/consume",
        headers={"X-Bot-Bind-Token": "test-bot-bind-token"},
        json={
            "code": code,
            "tg_user_id": 9_000_000_002,
            "telegram_username": "bind_session_test",
        },
    )
    assert consumed.status_code == 200, consumed.text
    assert int(consumed.json()["user_id"]) == user_id

    with engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT u.telegram_id, u.telegram_username, u.telegram_bound_at, c.used_at "
                "FROM public.users u JOIN public.telegram_bind_codes c ON c.user_id = u.user_id "
                "WHERE c.code_hash = :code_hash"
            ),
            {"code_hash": _hash_code(code)},
        ).mappings().one()
    assert str(result["telegram_id"]) == "9000000002"
    assert result["telegram_username"] == "bind_session_test"
    assert result["telegram_bound_at"] is not None
    assert result["used_at"] is not None

    replay = client.post(
        "/tg/bind/consume",
        headers={"X-Bot-Bind-Token": "test-bot-bind-token"},
        json={"code": code, "tg_user_id": 9_000_000_002},
    )
    assert replay.status_code == 409, replay.text
    assert _response_error_code(replay.json()) == "TGBIND_CONFLICT_CODE_INVALID"

    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE public.users SET telegram_id = NULL, telegram_username = NULL, "
                "telegram_bound_at = NULL WHERE user_id = :user_id"
            ),
            {"user_id": user_id},
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_tg_bind_code_non_privileged_role_does_not_need_allowlist(
    client: TestClient,
    seed: Dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regular executor (e.g. DEP_ADMIN-like) must not require privileged allowlist."""
    monkeypatch.delenv("DIRECTORY_PRIVILEGED_USER_IDS", raising=False)
    monkeypatch.delenv("DIRECTORY_PRIVILEGED_IDS", raising=False)
    monkeypatch.setenv("ENABLE_LEGACY_X_USER_ID", "0")
    monkeypatch.setenv("APP_ENV", "prod")

    user_id = int(seed["executor_user_id"])
    resp = client.post("/me/tg-bind-code", headers=auth_headers(user_id))
    assert resp.status_code == 200, resp.text
    assert resp.json().get("code")
