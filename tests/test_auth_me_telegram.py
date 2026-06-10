# tests/test_auth_me_telegram.py
from __future__ import annotations

from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import auth_headers


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _set_user_telegram(
    user_id: int,
    *,
    telegram_id: Any = None,
    telegram_username: Any = None,
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE public.users
                SET telegram_id = :telegram_id,
                    telegram_username = :telegram_username
                WHERE user_id = :user_id
                """
            ),
            {
                "user_id": int(user_id),
                "telegram_id": telegram_id,
                "telegram_username": telegram_username,
            },
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_auth_me_telegram_unbound(client: TestClient, seed: Dict[str, Any]) -> None:
    user_id = int(seed["executor_user_id"])
    _set_user_telegram(user_id, telegram_id=None, telegram_username=None)

    resp = client.get("/auth/me", headers=auth_headers(user_id))
    assert resp.status_code == 200

    body = resp.json()
    assert body["user_id"] == user_id
    assert body["telegram_bound"] is False
    assert body["telegram_username"] is None


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_auth_me_telegram_bound_without_username(client: TestClient, seed: Dict[str, Any]) -> None:
    user_id = int(seed["executor_user_id"])
    _set_user_telegram(user_id, telegram_id="987654321", telegram_username=None)

    resp = client.get("/auth/me", headers=auth_headers(user_id))
    assert resp.status_code == 200

    body = resp.json()
    assert body["telegram_bound"] is True
    assert body["telegram_username"] is None


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_auth_me_telegram_bound_with_username(client: TestClient, seed: Dict[str, Any]) -> None:
    user_id = int(seed["initiator_user_id"])
    _set_user_telegram(user_id, telegram_id="123456789", telegram_username="pytest_user")

    resp = client.get("/auth/me", headers=auth_headers(user_id))
    assert resp.status_code == 200

    body = resp.json()
    assert body["telegram_bound"] is True
    assert body["telegram_username"] == "pytest_user"
