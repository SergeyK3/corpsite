# tests/test_ops026_telegram_health_api.py
"""OPS-026.2 — Telegram health admin API."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.services.telegram_health_service import compute_health_status, get_telegram_health
from tests.conftest import auth_headers


@pytest.fixture
def admin_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    monkeypatch.setenv("BOT_TOKEN", "test-bot-token")
    monkeypatch.setenv("INTERNAL_API_TOKEN", "test-internal-token")
    monkeypatch.setenv("API_BASE_URL", "http://127.0.0.1:8000")
    monkeypatch.setenv("EVENTS_DELIVERY_CHANNEL", "telegram")
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def non_admin_headers(seed):
    return auth_headers(seed["executor_user_id"])


def test_telegram_health_forbidden_for_non_admin(client: TestClient, non_admin_headers) -> None:
    resp = client.get("/admin/system/telegram-health", headers=non_admin_headers)
    assert resp.status_code == 403


def test_telegram_health_admin_response_shape(client: TestClient, admin_headers) -> None:
    resp = client.get("/admin/system/telegram-health", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()

    assert body["status"] in {"GREEN", "YELLOW", "RED"}
    assert "checked_at" in body
    assert body["channel"] == "telegram"
    assert body["window_hours"] == 24

    assert set(body["queue"].keys()) >= {
        "pending_count",
        "sent_24h",
        "failed_24h",
        "oldest_pending_at",
        "oldest_pending_age_sec",
    }
    assert set(body["delivery"].keys()) >= {
        "last_sent_at",
        "last_failed_at",
        "last_error_code",
        "last_error_text",
    }
    assert set(body["bindings"].keys()) == {
        "active_users",
        "users_with_telegram",
        "coverage_percent",
    }
    cfg = body["bot_configuration"]
    assert cfg["bot_token_present"] is True
    assert cfg["internal_api_token_present"] is True
    assert "bot_token" not in cfg
    assert cfg["api_base_url"] == "http://127.0.0.1:8000"
    assert cfg["events_delivery_channel"] == "telegram"
    assert isinstance(body["unavailable_metrics"], list)
    assert len(body["unavailable_metrics"]) >= 1


def test_openapi_lists_telegram_health_route(client: TestClient) -> None:
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json().get("paths") or {}
    assert "/admin/system/telegram-health" in paths
    get_op = paths["/admin/system/telegram-health"]["get"]
    content = get_op["responses"]["200"]["content"]
    schema_ref = next(iter(content.values()))["schema"]["$ref"]
    assert schema_ref.endswith("/TelegramHealthResponse")


def test_compute_health_red_when_bot_token_missing() -> None:
    status, reasons = compute_health_status(
        queue={"pending_count": 0, "sent_24h": 0, "failed_24h": 0, "oldest_pending_age_sec": None},
        delivery={"last_sent_at": None, "last_error_code": None},
        bindings={"active_users": 1, "users_with_telegram": 1, "coverage_percent": 100.0},
        bot_configuration={
            "bot_token_present": False,
            "internal_api_token_present": True,
            "telegram_delivery_allowlist_configured": False,
        },
    )
    assert status == "RED"
    assert any("BOT_TOKEN" in r for r in reasons)


def test_compute_health_red_stale_pending_backlog() -> None:
    status, reasons = compute_health_status(
        queue={
            "pending_count": 3,
            "sent_24h": 0,
            "failed_24h": 0,
            "oldest_pending_age_sec": 3600.0,
        },
        delivery={"last_sent_at": None, "last_error_code": None},
        bindings={"active_users": 2, "users_with_telegram": 2, "coverage_percent": 100.0},
        bot_configuration={
            "bot_token_present": True,
            "internal_api_token_present": True,
            "telegram_delivery_allowlist_configured": False,
        },
    )
    assert status == "RED"
    assert reasons


def test_compute_health_green_recent_send() -> None:
    recent = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    status, reasons = compute_health_status(
        queue={"pending_count": 0, "sent_24h": 2, "failed_24h": 0, "oldest_pending_age_sec": None},
        delivery={"last_sent_at": recent, "last_error_code": None},
        bindings={"active_users": 2, "users_with_telegram": 2, "coverage_percent": 100.0},
        bot_configuration={
            "bot_token_present": True,
            "internal_api_token_present": True,
            "telegram_delivery_allowlist_configured": False,
        },
    )
    assert status == "GREEN"
    assert reasons


def test_compute_health_yellow_on_pending_drain() -> None:
    recent = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    status, reasons = compute_health_status(
        queue={"pending_count": 2, "sent_24h": 1, "failed_24h": 0, "oldest_pending_age_sec": 120.0},
        delivery={"last_sent_at": recent, "last_error_code": None},
        bindings={"active_users": 2, "users_with_telegram": 1, "coverage_percent": 50.0},
        bot_configuration={
            "bot_token_present": True,
            "internal_api_token_present": True,
            "telegram_delivery_allowlist_configured": False,
        },
    )
    assert status == "YELLOW"
    assert any("pending" in r.lower() for r in reasons)


def test_get_telegram_health_masks_error_text(monkeypatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "8123456789:AAHabcdefghijklmnopqrstuvwxyz123456")
    monkeypatch.setenv("INTERNAL_API_TOKEN", "secret")
    # Service reads DB; ensure call succeeds and never leaks raw token from env in response.
    payload = get_telegram_health()
    dumped = str(payload)
    assert "8123456789" not in dumped
    assert "AAHabcdefghijklmnopqrstuvwxyz123456" not in dumped
