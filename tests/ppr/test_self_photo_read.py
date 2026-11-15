"""ID-free photo read keeps the subject bound to the authenticated user."""
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api import ppr_self_router as self_api
from app.auth import get_current_user
from app.main import app


def test_self_photo_ignores_requested_person_id(monkeypatch):
    seen_person_ids: list[int] = []
    monkeypatch.setattr(self_api, "assert_ppr_read_path_activation_allowed", lambda: None)
    monkeypatch.setattr(
        self_api._self_access_service,
        "resolve_for_user",
        lambda user: SimpleNamespace(status="READY", composite=SimpleNamespace(person_id=99)),
    )
    monkeypatch.setattr(
        self_api,
        "load_verified_person_photo",
        lambda person_id: seen_person_ids.append(person_id) or b"verified-jpeg",
    )
    app.dependency_overrides[get_current_user] = lambda: {"user_id": 19}
    try:
        response = TestClient(app).get("/api/ppr/me/photo?person_id=100")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    assert response.content == b"verified-jpeg"
    assert response.headers["cache-control"] == "private, no-store"
    assert seen_person_ids == [99]


def test_self_photo_requires_resolved_active_person(monkeypatch):
    monkeypatch.setattr(self_api, "assert_ppr_read_path_activation_allowed", lambda: None)
    monkeypatch.setattr(
        self_api._self_access_service,
        "resolve_for_user",
        lambda user: SimpleNamespace(status="PERSON_NOT_LINKED", composite=None),
    )
    app.dependency_overrides[get_current_user] = lambda: {"user_id": 19}
    try:
        response = TestClient(app).get("/api/ppr/me/photo")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 404
