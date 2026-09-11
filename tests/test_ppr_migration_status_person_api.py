"""WP-PPR-MIG-005E safe exact-person endpoint contracts."""
from fastapi.testclient import TestClient
from app.api import ppr_migration_status_router as route
from app.auth import get_current_user
from app.main import app

def setup(monkeypatch, allowed=True):
    app.dependency_overrides[get_current_user] = lambda: {"user_id": 7}
    monkeypatch.setattr(route, "has_admin_permission", lambda *_: allowed)
    monkeypatch.setattr(route, "compute_scope", lambda *_a, **_k: {"privileged": True,"scope_unit_ids":None})
    monkeypatch.setattr(route, "require_personnel_visibility_or_403", lambda *_: None)

def test_person_status_auth_and_safe_cells(monkeypatch):
    app.dependency_overrides.clear(); client=TestClient(app)
    assert client.get("/directory/personnel/migration-status/persons/1",params={"universe_id":1}).status_code==401
    setup(monkeypatch, False); assert client.get("/directory/personnel/migration-status/persons/1",params={"universe_id":1}).status_code==403
    setup(monkeypatch, True)
    monkeypatch.setattr(route,"person_cells",lambda *_a,**_k:{"universe_id":1,"cells":{s:{"status_code":"ACCEPTED","status_label":"Согласовано","reason_code":"RUN_PARTICIPANT_ACCEPTED","reason_label":"Подтверждено","calculated_at":"2026-01-01"} for s in ("general","education","training")}})
    body=client.get("/directory/personnel/migration-status/persons/1",params={"universe_id":1}).json()
    assert set(body["cells"])=={"general","education","training"}
    assert not any(x in str(body).lower() for x in ("iin","fingerprint","raw_payload","document"))
    app.dependency_overrides.clear()

def test_person_status_unknown_or_out_of_scope_is_404(monkeypatch):
    setup(monkeypatch, True); monkeypatch.setattr(route,"person_cells",lambda *_a,**_k:None)
    response=TestClient(app).get("/directory/personnel/migration-status/persons/999",params={"universe_id":999})
    assert response.status_code==404
    app.dependency_overrides.clear()
