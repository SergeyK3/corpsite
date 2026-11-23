"""Training password checks use the live source verifier in corpsite_test."""
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.auth import hash_password
from app.db.engine import engine
from app.main import app


def test_linked_login_tracks_source_password_and_disable() -> None:
    suffix = uuid4().hex[:12]
    source_login = f"training_source_{suffix}"
    target_login = f"{source_login}_test"
    first_password = "Example-Training-Password-11"
    second_password = "Example-Training-Password-22"
    with engine.begin() as conn:
        role = conn.execute(text("SELECT role_id FROM public.roles WHERE code='EMPLOYEE'")).scalar_one()
        source_id = conn.execute(text("""
            INSERT INTO public.users(full_name, role_id, is_active, login, password_hash)
            VALUES ('Учебный источник', :role, TRUE, :login, :password_hash)
            RETURNING user_id
        """), {"role": role, "login": source_login,
               "password_hash": hash_password(first_password)}).scalar_one()
        target_id = conn.execute(text("""
            INSERT INTO public.users(full_name, role_id, is_active, login)
            VALUES ('Учебный участник', :role, TRUE, :login)
            RETURNING user_id
        """), {"role": role, "login": target_login}).scalar_one()
        conn.execute(text("""
            INSERT INTO public.training_identity_links(training_user_id, source_user_id, source_kind)
            VALUES (:target, :source, 'local')
        """), {"target": target_id, "source": source_id})

    client = TestClient(app)
    def login(name: str, password: str):
        return client.post("/auth/login", json={"login": name, "password": password})

    first = login(target_login, first_password)
    assert first.status_code == 200, first.text
    assert "password" not in first.text.lower()
    token = first.json()["access_token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200, me.text
    assert me.json()["training_linked"] is True
    assert "password_hash" not in me.text
    assert client.post("/auth/password-change", headers={"Authorization": f"Bearer {token}"},
                       json={"current_password": first_password, "new_password": second_password,
                             "new_password_confirmation": second_password}).status_code == 403

    changed = client.post("/auth/password-change", headers={
        "Authorization": f"Bearer {login(source_login, first_password).json()['access_token']}"
    }, json={"current_password": first_password, "new_password": second_password,
             "new_password_confirmation": second_password})
    assert changed.status_code == 200, changed.text
    assert login(target_login, first_password).status_code == 401
    assert login(target_login, second_password).status_code == 200
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401

    with engine.begin() as conn:
        conn.execute(text("UPDATE public.users SET login=:login WHERE user_id=:uid"),
                     {"uid": source_id, "login": f"{source_login}_renamed"})
    assert login(target_login, second_password).status_code == 401
    renamed_training_login = f"{source_login}_renamed_test"
    renamed_session = login(renamed_training_login, second_password)
    assert renamed_session.status_code == 200

    with engine.begin() as conn:
        conn.execute(text("UPDATE public.users SET is_active=FALSE WHERE user_id=:uid"), {"uid": source_id})
    assert login(renamed_training_login, second_password).status_code == 403
    assert client.get("/auth/me", headers={
        "Authorization": f"Bearer {renamed_session.json()['access_token']}"
    }).status_code == 403
