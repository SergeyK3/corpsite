"""Isolated API + persistence tests; never connect to the application database.

Run with --noconftest -o addopts= (this file supplies its own SQLite database).
"""
import importlib.util
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import ProgrammingError
from types import SimpleNamespace

from app.api import personnel_settings_router as routes
from app.auth import get_current_user


@pytest.fixture
def settings_api(tmp_path, monkeypatch):
    database = str(tmp_path / "settings.sqlite")
    isolated_engine = create_engine("sqlite://", connect_args={"check_same_thread": False})

    @event.listens_for(isolated_engine, "connect")
    def attach_public(connection, _record):
        connection.execute("ATTACH DATABASE ? AS public", (database,))

    path = Path(__file__).resolve().parents[1] / "alembic/versions/hrlang001_personnel_section_language.py"
    spec = importlib.util.spec_from_file_location("language_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with isolated_engine.begin() as conn:
        monkeypatch.setattr(migration.op, "execute", lambda sql: conn.execute(text(sql)))
        migration.upgrade()
        for table in ("personnel_orders", "personnel_order_templates", "employee_events"):
            conn.execute(text(f"CREATE TABLE public.{table} (id INTEGER PRIMARY KEY, data TEXT)"))
            conn.execute(text(f"INSERT INTO public.{table} VALUES (1, 'Original RU / KK text')"))
    monkeypatch.setattr(routes, "engine", isolated_engine)
    app = FastAPI()
    app.include_router(routes.router)
    user = {"user_id": 10, "role_code": "HR_HEAD"}
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as client:
        yield client, user, isolated_engine
    isolated_engine.dispose()


def test_shared_default_persistence_and_other_user_without_document_changes(settings_api):
    client, user, db = settings_api
    assert client.get("/personnel/settings").json() == {"language": "kk", "can_edit": True}
    with db.connect() as conn:
        before = {table: conn.execute(text(f"SELECT * FROM public.{table}")).all()
                  for table in ("personnel_orders", "personnel_order_templates", "employee_events")}
    assert client.put("/personnel/settings", json={"language": "ru"}).json()["language"] == "ru"
    db.dispose()  # Persistence survives a new database connection and another user.
    user.update(user_id=20, role_code="HR_REG")
    response = client.get("/personnel/settings")
    assert response.json() == {"language": "ru", "can_edit": False}
    assert response.headers["cache-control"] == "no-store"
    with db.connect() as conn:
        assert before == {table: conn.execute(text(f"SELECT * FROM public.{table}")).all() for table in before}


@pytest.mark.parametrize("role,allowed", [("HR_HEAD", True), ("ADMIN", True), ("HR_REG", False), ("ACCESS_ADMIN", False), ("DIRECTOR", False), (None, False)])
def test_only_requested_roles_can_write(settings_api, role, allowed):
    client, user, _db = settings_api
    user.update(role_code=role, is_privileged=True, has_personnel_admin=True, has_sysadmin_api=True)
    response = client.put("/personnel/settings", json={"language": "ru"})
    assert response.status_code == (200 if allowed else 403)
    assert client.get("/personnel/settings").json()["language"] == ("ru" if allowed else "kk")


def test_invalid_language_and_unauthenticated_request(settings_api):
    client, _user, _db = settings_api
    assert client.put("/personnel/settings", json={"language": "en"}).status_code == 422
    assert client.get("/personnel/settings").json()["language"] == "kk"
    client.app.dependency_overrides.clear()
    assert client.get("/personnel/settings").status_code == 401
    assert client.put("/personnel/settings", json={"language": "ru"}).status_code == 401


def test_missing_postgres_settings_table_is_reported_and_does_not_bypass_roles(settings_api, monkeypatch):
    client, user, db = settings_api
    def missing_table():
        raise ProgrammingError("settings query", {}, SimpleNamespace(pgcode="42P01"))
    monkeypatch.setattr(db, "connect", missing_table)
    monkeypatch.setattr(db, "begin", missing_table)
    response = client.get("/personnel/settings")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "PERSONNEL_SETTINGS_SCHEMA_REQUIRED"
    assert client.put("/personnel/settings", json={"language": "ru"}).status_code == 503
    user["role_code"] = "HR_REG"
    assert client.put("/personnel/settings", json={"language": "ru"}).status_code == 403
