"""Focused contract tests for the Person-rooted foreign-languages command."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.auth import get_current_user
from app.db.engine import engine
from app.main import app
from tests.ppr.conftest import cleanup_person_graph, insert_person, ppr_db_available, require_ppr_schema


@pytest.fixture
def case(monkeypatch):
    require_ppr_schema()
    with engine.begin() as conn:
        person_id = insert_person(conn, full_name=f"Languages {uuid4().hex}")
        conn.execute(text("INSERT INTO personnel_record_metadata(person_id,additional_profile) VALUES(:p,CAST(:v AS jsonb))"), {"p":person_id,"v":'{"awards":[{"name":"keep"}],"foreign_languages":[{"language":"English","proficiency":"B1"}]}'})
    app.dependency_overrides[get_current_user] = lambda: {"user_id": 1}
    monkeypatch.setattr("app.api.ppr_card_command_router.require_personnel_card_edit_for_person", lambda _u, _p: None)
    yield person_id
    app.dependency_overrides.pop(get_current_user, None)
    with engine.begin() as conn: cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[])


def payload(**extra):
    return {"command_id":f"lang-{uuid4().hex}","foreign_languages":[{"language":"German","proficiency":"B2"}], **extra}


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL unavailable")
def test_save_preserves_other_profile_keys_and_audits(case):
    response=TestClient(app).put(f"/api/ppr/persons/{case}/foreign-languages",json=payload())
    assert response.status_code==200
    with engine.connect() as conn:
        profile=conn.execute(text("SELECT additional_profile FROM personnel_record_metadata WHERE person_id=:p"),{"p":case}).scalar_one()
        event=conn.execute(text("SELECT event_payload FROM personnel_record_events WHERE person_id=:p AND event_type='PPR_FOREIGN_LANGUAGES_HR_CORRECTED'"),{"p":case}).scalar_one()
    assert profile["awards"]==[{"name":"keep"}] and profile["foreign_languages"][0]["language"]=="German"
    assert event["before"][0]["language"]=="English" and event["after"][0]["proficiency"]=="B2"

@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL unavailable")
def test_validation_conflict_and_idempotency(case):
    client=TestClient(app); body=payload(); assert client.put(f"/api/ppr/persons/{case}/foreign-languages",json=body).status_code==200
    assert client.put(f"/api/ppr/persons/{case}/foreign-languages",json=body).json()["idempotent"] is True
    assert client.put(f"/api/ppr/persons/{case}/foreign-languages",json=payload(foreign_languages=[{"language":"","proficiency":"B2"}])).status_code==422
    assert client.put(f"/api/ppr/persons/{case}/foreign-languages",json=payload(foreign_languages=[{"language":"French","proficiency":"A1"},{"language":"french","proficiency":"B1"}])).status_code==422
    assert client.put(f"/api/ppr/persons/{case}/foreign-languages",json=payload(expected_updated_at=(datetime.now(UTC)-timedelta(days=1)).isoformat())).status_code==409

def test_permission_denial_and_route_person_id(case, monkeypatch):
    monkeypatch.setattr("app.api.ppr_card_command_router.require_personnel_card_edit_for_person", lambda *_: (_ for _ in ()).throw(HTTPException(403,"Forbidden")))
    client=TestClient(app)
    assert client.put(f"/api/ppr/persons/{case}/foreign-languages",json=payload()).status_code==403
    assert client.put(f"/api/ppr/persons/{case}/foreign-languages",json=payload(person_id=999)).status_code==422
