# tests/test_ops007a_telegram_bot_internal.py
from __future__ import annotations

from typing import Any, Dict

import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from tests.test_auth_me_telegram import _db_available, _set_user_telegram

INTERNAL_TOKEN = "ops007a-test-internal-token"
TG_USER_ID = 900_007_001
TG_UNKNOWN = 900_007_999


@pytest.fixture(autouse=True)
def _internal_token_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERNAL_API_TOKEN", INTERNAL_TOKEN)


def _bot_headers(tg_user_id: int, token: str = INTERNAL_TOKEN) -> Dict[str, str]:
    return {
        "X-Internal-Api-Token": token,
        "X-Telegram-User-Id": str(int(tg_user_id)),
    }


def _load_bindings_module():
    bindings_path = (
        Path(__file__).resolve().parents[1]
        / "corpsite-bot"
        / "src"
        / "bot"
        / "storage"
        / "bindings.py"
    )
    spec = importlib.util.spec_from_file_location("bot_bindings_test_mod", bindings_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_tg_resolve_returns_bound_user(client: TestClient, seed: Dict[str, Any]) -> None:
    user_id = int(seed["executor_user_id"])
    _set_user_telegram(user_id, telegram_id=str(TG_USER_ID))

    resp = client.post("/internal/bot/tg/resolve", headers=_bot_headers(TG_USER_ID))
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == user_id
    assert body["telegram_bound"] is True


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_tg_resolve_unknown_rejected(client: TestClient, seed: Dict[str, Any]) -> None:
    _ = seed
    resp = client.post("/internal/bot/tg/resolve", headers=_bot_headers(TG_UNKNOWN))
    assert resp.status_code == 404


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_internal_calls_rejected_without_token(client: TestClient, seed: Dict[str, Any]) -> None:
    _ = seed
    resp = client.post(
        "/internal/bot/tg/resolve",
        headers={"X-Telegram-User-Id": str(TG_USER_ID)},
    )
    assert resp.status_code == 403


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_unbind_clears_telegram_id(client: TestClient, seed: Dict[str, Any]) -> None:
    user_id = int(seed["executor_user_id"])
    _set_user_telegram(user_id, telegram_id=str(TG_USER_ID))

    resp = client.post("/internal/bot/tg/unbind", headers=_bot_headers(TG_USER_ID))
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == user_id
    assert body["applied"] is True
    assert body["telegram_bound"] is False

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT telegram_id FROM public.users WHERE user_id = :uid"),
            {"uid": user_id},
        ).mappings().first()
    assert row is not None
    assert row["telegram_id"] is None


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_unbind_idempotent_when_not_bound(client: TestClient, seed: Dict[str, Any]) -> None:
    _ = seed
    resp = client.post("/internal/bot/tg/unbind", headers=_bot_headers(TG_UNKNOWN))
    assert resp.status_code == 200
    body = resp.json()
    assert body["applied"] is False
    assert body["telegram_bound"] is False


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_unbind_preserves_employee_id(client: TestClient, seed: Dict[str, Any]) -> None:
    user_id = int(seed["executor_user_id"])
    _set_user_telegram(user_id, telegram_id=str(TG_USER_ID))

    with engine.begin() as conn:
        before = conn.execute(
            text("SELECT employee_id FROM public.users WHERE user_id = :uid"),
            {"uid": user_id},
        ).scalar_one()

    resp = client.post("/internal/bot/tg/unbind", headers=_bot_headers(TG_USER_ID))
    assert resp.status_code == 200
    assert resp.json()["employee_id"] == before

    with engine.connect() as conn:
        after = conn.execute(
            text("SELECT employee_id FROM public.users WHERE user_id = :uid"),
            {"uid": user_id},
        ).scalar_one()
    assert after == before


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_service_account_blocked_for_bot_tasks(client: TestClient, seed: Dict[str, Any]) -> None:
    user_id = int(seed["executor_user_id"])
    _set_user_telegram(user_id, telegram_id=str(TG_USER_ID))

    with engine.begin() as conn:
        conn.execute(
            text("UPDATE public.users SET login = :login WHERE user_id = :uid"),
            {"login": "bot_service_account", "uid": user_id},
        )

    resp = client.get("/internal/bot/tasks", headers=_bot_headers(TG_USER_ID))
    assert resp.status_code == 403


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_task_list_via_internal_bot_api(client: TestClient, seed: Dict[str, Any]) -> None:
    user_id = int(seed["executor_user_id"])
    _set_user_telegram(user_id, telegram_id=str(TG_USER_ID))

    with engine.begin() as conn:
        conn.execute(
            text("UPDATE public.users SET login = :login WHERE user_id = :uid"),
            {"login": f"tg_user_{user_id}", "uid": user_id},
        )

    resp = client.get("/internal/bot/tasks?limit=5", headers=_bot_headers(TG_USER_ID))
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body


def test_legacy_json_bindings_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TELEGRAM_LEGACY_JSON_BINDINGS", raising=False)
    mod = _load_bindings_module()
    assert mod.legacy_json_bindings_enabled() is False
    assert mod.get_binding(12345) is None


def test_legacy_json_bindings_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_LEGACY_JSON_BINDINGS", "1")
    mod = _load_bindings_module()
    assert mod.legacy_json_bindings_enabled() is True
