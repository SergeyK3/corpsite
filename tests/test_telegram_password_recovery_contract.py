"""Focused contract checks for anonymous Telegram password recovery."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_recovery_request_has_identical_response_for_unknown_and_unavailable(monkeypatch):
    from app import auth

    client = TestClient(app)
    monkeypatch.setattr(auth, "request_recovery", lambda _login: {"message": "same"})
    unknown = client.post("/auth/password-recovery/telegram/request", json={"login": "unknown"})
    unavailable = client.post("/auth/password-recovery/telegram/request", json={"login": "without.telegram"})
    assert unknown.status_code == unavailable.status_code == 200
    assert unknown.json() == unavailable.json() == {"message": "same"}


def test_completion_maps_expired_and_reused_codes_without_exposing_credentials(monkeypatch):
    from app import auth

    client = TestClient(app)
    monkeypatch.setattr(auth, "complete_recovery", lambda **_kwargs: (_ for _ in ()).throw(ValueError("CODE_EXPIRED")))
    expired = client.post("/auth/password-recovery/telegram/complete", json={"login": "u", "code": "12345678", "new_password": "new-password", "new_password_confirmation": "new-password"})
    assert expired.status_code == 400
    assert "парол" not in expired.text.lower() or "Новый пароль" not in expired.text
    monkeypatch.setattr(auth, "complete_recovery", lambda **_kwargs: (_ for _ in ()).throw(ValueError("CODE_INVALID")))
    reused = client.post("/auth/password-recovery/telegram/complete", json={"login": "u", "code": "12345678", "new_password": "new-password", "new_password_confirmation": "new-password"})
    assert reused.status_code == 400
    assert "Код недействителен" in reused.json()["detail"]
