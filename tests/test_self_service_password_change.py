"""Integration tests for authenticated self-service password change."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.auth import verify_password
from app.db.engine import engine
from tests.test_adr042_phase_b5_auth_policy import PASSWORD, _db_available, login_user


def _login_token(client: TestClient, *, login: str, password: str) -> str:
    response = client.post("/auth/login", json={"login": login, "password": password})
    assert response.status_code == 200
    return str(response.json()["access_token"])


def _change(client: TestClient, token: str, **payload: str):
    return client.post(
        "/auth/password-change",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_password_change_updates_hash_revokes_old_jwt_and_writes_audit(client: TestClient, login_user):
    user_id = int(login_user["user_id"])
    new_password = "ChangedPass123"
    old_token = _login_token(client, login=login_user["login"], password=PASSWORD)

    changed = _change(
        client,
        old_token,
        current_password=PASSWORD,
        new_password=new_password,
        new_password_confirmation=new_password,
    )
    assert changed.status_code == 200
    assert "повторно" in changed.json()["message"].lower()

    assert client.get("/auth/me", headers={"Authorization": f"Bearer {old_token}"}).status_code == 401
    assert client.post("/auth/login", json={"login": login_user["login"], "password": PASSWORD}).status_code == 401
    assert _login_token(client, login=login_user["login"], password=new_password)

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT password_hash, token_version FROM public.users WHERE user_id = :user_id"),
            {"user_id": user_id},
        ).mappings().one()
        audit_count = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM public.security_audit_log
                    WHERE event_type = 'PASSWORD_CHANGED'
                      AND target_user_id = :user_id
                      AND success = TRUE
                      AND metadata->>'action' = 'self_service_password_change'
                    """
                ),
                {"user_id": user_id},
            ).scalar_one()
        )
    assert verify_password(new_password, str(row["password_hash"]))
    assert int(row["token_version"]) == 2
    assert audit_count == 1


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.parametrize(
    ("current_password", "new_password", "new_password_confirmation", "message"),
    [
        ("WrongPass123", "ChangedPass123", "ChangedPass123", "текущий пароль"),
        (PASSWORD, "ChangedPass123", "ChangedPass124", "подтверждение"),
        (PASSWORD, "short", "short", "от 8 до 200"),
        (PASSWORD, PASSWORD, PASSWORD, "отличаться"),
    ],
)
def test_password_change_rejects_invalid_input_without_changing_password(
    client: TestClient,
    login_user,
    current_password: str,
    new_password: str,
    new_password_confirmation: str,
    message: str,
):
    user_id = int(login_user["user_id"])
    token = _login_token(client, login=login_user["login"], password=PASSWORD)
    with engine.connect() as conn:
        before = conn.execute(
            text("SELECT password_hash, token_version FROM public.users WHERE user_id = :user_id"),
            {"user_id": user_id},
        ).mappings().one()

    response = _change(
        client,
        token,
        current_password=current_password,
        new_password=new_password,
        new_password_confirmation=new_password_confirmation,
    )
    assert response.status_code == 400
    assert message in response.json()["detail"].lower()

    with engine.connect() as conn:
        after = conn.execute(
            text("SELECT password_hash, token_version FROM public.users WHERE user_id = :user_id"),
            {"user_id": user_id},
        ).mappings().one()
    assert dict(after) == dict(before)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_password_change_has_no_role_or_grant_guard(client: TestClient, login_user):
    user_id = int(login_user["user_id"])
    with engine.begin() as conn:
        original_role_id = int(
            conn.execute(text("SELECT role_id FROM public.users WHERE user_id = :user_id"), {"user_id": user_id}).scalar_one()
        )
        employee_role_id = conn.execute(
            text("SELECT role_id FROM public.roles WHERE code = 'EMPLOYEE' AND is_active = TRUE")
        ).scalar_one_or_none()
        if employee_role_id is None:
            pytest.skip("EMPLOYEE role migration has not been applied")
        conn.execute(
            text("UPDATE public.users SET role_id = :role_id WHERE user_id = :user_id"),
            {"role_id": int(employee_role_id), "user_id": user_id},
        )
    try:
        token = _login_token(client, login=login_user["login"], password=PASSWORD)
        response = _change(
            client,
            token,
            current_password=PASSWORD,
            new_password="RoleFreePass123",
            new_password_confirmation="RoleFreePass123",
        )
        assert response.status_code == 200
    finally:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE public.users SET role_id = :role_id WHERE user_id = :user_id"),
                {"role_id": original_role_id, "user_id": user_id},
            )
