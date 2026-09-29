from __future__ import annotations
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.api import admin_router
from app.security.admin_guard import require_sysadmin_api
from app.services.personnel_order_template_draft_service import TemplateDraftError

PATH="/admin/personnel-order-templates/TERMINATION/draft/publish"
PUBLISHED_PATH="/admin/personnel-order-templates/TERMINATION/published"
OUT={"template_version_id":7,"item_type_code":"TERMINATION","version_number":4,"status":"PUBLISHED","revision":3,"based_on_built_in":False,"title_ru":"ru","title_kk":"kk","preamble_ru":"ru","preamble_kk":"kk","body_template_ru":"ru","body_template_kk":"kk","basis_template_ru":"ru","basis_template_kk":"kk","created_at":datetime.now(timezone.utc),"updated_at":datetime.now(timezone.utc),"published_at":datetime.now(timezone.utc),"published_by_user_id":42}

@pytest.fixture
def client(monkeypatch):
    calls=[]
    monkeypatch.setattr(admin_router,"publish_draft",lambda code, revision, actor: calls.append((code,revision,actor)) or OUT)
    app.dependency_overrides[require_sysadmin_api]=lambda:{"user_id":42,"role_id":1}
    yield TestClient(app),calls
    app.dependency_overrides.clear()

def test_sysadmin_publish_passes_server_actor_and_returns_metadata(client):
    c,calls=client; r=c.post(PATH,json={"expected_revision":3})
    assert r.status_code==200 and calls==[("TERMINATION",3,42)]
    assert r.json()["status"]=="PUBLISHED" and r.json()["published_by_user_id"]==42 and r.json()["published_at"]

def test_client_actor_is_ignored_and_never_reaches_service(client):
    c,calls=client; r=c.post(PATH,json={"expected_revision":3,"published_by_user_id":999,"actor":999})
    assert r.status_code==200 and calls==[("TERMINATION",3,42)]

def test_stale_revision_is_http_409(client,monkeypatch):
    c,_=client
    monkeypatch.setattr(admin_router,"publish_draft",lambda *_: (_ for _ in ()).throw(TemplateDraftError("TEMPLATE_REVISION_CONFLICT","Черновик изменён",conflict=True)))
    r=c.post(PATH,json={"expected_revision":3}); assert r.status_code==409 and r.json()["detail"]["code"]=="TEMPLATE_REVISION_CONFLICT"

def test_domain_validation_error_is_http_400(client,monkeypatch):
    c,_=client
    monkeypatch.setattr(admin_router,"publish_draft",lambda *_: (_ for _ in ()).throw(TemplateDraftError("TEMPLATE_DRAFT_NOT_FOUND","Черновик отсутствует")))
    assert c.post(PATH,json={"expected_revision":3}).status_code==400

def test_rbac_rejects_without_calling_service(monkeypatch):
    calls=[]; monkeypatch.setattr(admin_router,"publish_draft",lambda *_: calls.append(1) or OUT)
    app.dependency_overrides[require_sysadmin_api]=lambda: (_ for _ in ()).throw(__import__('fastapi').HTTPException(status_code=403,detail="forbidden"))
    try:
        assert TestClient(app).post(PATH,json={"expected_revision":3}).status_code==403 and not calls
    finally: app.dependency_overrides.clear()


def test_published_snapshot_is_read_only_get(monkeypatch):
    calls=[]
    monkeypatch.setattr(admin_router,"get_published",lambda code: calls.append(code) or OUT)
    app.dependency_overrides[require_sysadmin_api]=lambda:{"user_id":42,"role_id":1}
    try:
        response=TestClient(app).get(PUBLISHED_PATH)
        assert response.status_code==200
        assert response.json()["status"]=="PUBLISHED"
        assert calls==["TERMINATION"]
    finally:
        app.dependency_overrides.clear()


def test_first_save_passes_only_snapshot_and_server_actor(monkeypatch):
    calls=[]
    values={key: "text" for key in ("title_ru", "title_kk", "preamble_ru", "preamble_kk", "body_template_ru", "body_template_kk", "basis_template_ru", "basis_template_kk")}
    monkeypatch.setattr(admin_router, "create_draft_from_working_copy", lambda code, source, base_id, base_revision, payload, actor: calls.append((code, base_id, base_revision, payload, actor)) or {**OUT, **values, "status": "DRAFT"})
    app.dependency_overrides[require_sysadmin_api]=lambda:{"user_id":42,"role_id":1}
    try:
        response=TestClient(app).post("/admin/personnel-order-templates/TERMINATION/draft", json={**values, "base_source":"PUBLISHED", "base_published_template_version_id":9, "base_published_revision":3, "actor":999})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert calls == [("TERMINATION", 9, 3, values, 42)]
