"""Employee and reviewer API contract on synthetic records in the isolated test DB."""
import importlib.util
from datetime import timedelta
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.auth import get_current_user
from app.api.relative_change_request_router import router
from app.services import relative_change_request_service as changes


@pytest.fixture
def relatives(seeded, database, monkeypatch):
    with database.begin() as conn:
        conn.execute(text("""CREATE TABLE IF NOT EXISTS person_relatives (
            relative_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            person_id bigint NOT NULL REFERENCES persons(person_id),
            relationship_type text NOT NULL, full_name text NOT NULL,
            birth_date date, birth_place text, organization_name text,
            residence_address text, notes text,
            lifecycle_status text NOT NULL DEFAULT 'active',
            updated_at timestamptz NOT NULL DEFAULT now())"""))
        exists = conn.execute(text("SELECT to_regclass('public.person_relative_change_requests')")).scalar_one()
        if exists is None:
            spec = importlib.util.spec_from_file_location(
                'relative_migration', Path('alembic/versions/selfrel001_relative_change_requests.py'))
            migration = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration)
            with Operations.context(MigrationContext.configure(conn)):
                migration.upgrade()
        conn.execute(text("""INSERT INTO person_relatives(person_id,relationship_type,full_name)
            VALUES (1,'spouse','Fictional spouse'),(2,'child','Other fictional relative')"""))
    monkeypatch.setattr(changes, 'engine', database)
    monkeypatch.setattr(changes, 'has_personnel_card_edit', lambda user: user['user_id'] == 3)
    monkeypatch.setattr(changes, '_self_person', lambda user: {1: 1, 2: 2}.get(user['user_id'])
                        or (_ for _ in ()).throw(HTTPException(403)))
    monkeypatch.setattr(changes, 'require_personnel_card_edit_for_person',
                        lambda user, person_id: None if user['user_id'] == 3 and person_id == 1
                        else (_ for _ in ()).throw(HTTPException(403)))

    class FakePprService:
        def __init__(self, **_):
            pass

        def supersede_relative(self, envelope):
            with database.begin() as conn:
                row = conn.execute(text("""UPDATE person_relatives SET lifecycle_status='superseded',
                    updated_at=now() WHERE relative_id=:rid AND person_id=:pid AND
                    lifecycle_status='active' AND updated_at=:expected RETURNING relative_id"""),
                    {'rid': envelope.payload['record_id'], 'pid': envelope.person_id,
                     'expected': envelope.payload['expected_updated_at']}).scalar_one_or_none()
                if row is None:
                    raise RuntimeError('stale relative')
                new_id = conn.execute(text("""INSERT INTO person_relatives
                    (person_id,relationship_type,full_name,birth_date,birth_place,organization_name,residence_address,notes)
                    VALUES (:pid,:relationship_type,:full_name,:birth_date,:birth_place,:organization_name,
                    :residence_address,:notes) RETURNING relative_id"""),
                    {'pid': envelope.person_id, **envelope.payload['replacement']}).scalar_one()
            return type('Result', (), {'section_record_id': new_id})()

    monkeypatch.setattr(changes, 'PprSectionApplicationService', FakePprService)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: seeded[1]
    return TestClient(app), app, seeded, database


def _original(database, relative_id=1):
    with database.connect() as conn:
        return conn.execute(text("SELECT updated_at FROM person_relatives WHERE relative_id=:rid"),
                            {'rid': relative_id}).scalar_one()


def _proposal(name='Corrected fictional spouse'):
    return {'relationship_type': 'spouse', 'full_name': name, 'birth_date': None,
            'birth_place': None, 'organization_name': None, 'residence_address': None, 'notes': None}


def test_relative_submit_return_resubmit_approve_and_audit(relatives):
    client, app, actors, database = relatives
    original = _original(database)
    body = {'expected_updated_at': original.isoformat(), 'proposed': _proposal()}
    created = client.post('/api/ppr/me/relatives/1/change-requests', json=body)
    assert created.status_code == 201, created.text
    request = created.json()
    assert request['status'] == 'pending'
    assert client.get('/api/ppr/me/relative-change-requests').json()['items'][0]['request_id'] == request['request_id']
    with database.connect() as conn:
        assert conn.execute(text("SELECT full_name FROM person_relatives WHERE relative_id=1")).scalar_one() == 'Fictional spouse'
    app.dependency_overrides[get_current_user] = lambda: actors[3]
    queue = client.get('/api/ppr/relative-change-requests/review-queue')
    assert queue.status_code == 200
    assert queue.json()['items'][0]['current']['full_name'] == 'Fictional spouse'
    assert queue.json()['items'][0]['proposed']['full_name'] == 'Corrected fictional spouse'
    path = f"/api/ppr/relative-change-requests/{request['request_id']}/decision"
    returned = client.post(path, json={'expected_revision': 1, 'action': 'return', 'reason': 'Clarify spelling'})
    assert returned.status_code == 200, returned.text
    assert returned.json()['status'] == 'returned' and returned.json()['reason'] == 'Clarify spelling'
    app.dependency_overrides[get_current_user] = lambda: actors[1]
    retry = client.post(f"/api/ppr/me/relative-change-requests/{request['request_id']}/resubmit",
                        json={'expected_revision': 2, 'expected_updated_at': original.isoformat(),
                              'proposed': _proposal('Revised fictional spouse')})
    assert retry.status_code == 200, retry.text
    assert retry.json()['status'] == 'pending' and retry.json()['revision'] == 3
    app.dependency_overrides[get_current_user] = lambda: actors[3]
    approved = client.post(path, json={'expected_revision': 3, 'action': 'approve'})
    assert approved.status_code == 200, approved.text
    assert approved.json()['status'] == 'approved' and approved.json()['approved_relative_id'] != 1
    with database.connect() as conn:
        assert conn.execute(text("SELECT lifecycle_status FROM person_relatives WHERE relative_id=1")).scalar_one() == 'superseded'
        assert conn.execute(text("SELECT full_name FROM person_relatives WHERE relative_id=:rid"),
                            {'rid': approved.json()['approved_relative_id']}).scalar_one() == 'Revised fictional spouse'
        events = conn.execute(text("SELECT action FROM person_relative_change_events ORDER BY event_id")).scalars().all()
        assert events == ['submitted', 'return', 'resubmitted', 'approve']


def test_relative_ownership_permission_and_stale_conflict(relatives):
    client, app, actors, database = relatives
    original = _original(database)
    body = {'expected_updated_at': original.isoformat(), 'proposed': _proposal()}
    assert client.post('/api/ppr/me/relatives/2/change-requests', json=body).status_code == 404
    request = client.post('/api/ppr/me/relatives/1/change-requests', json=body).json()
    app.dependency_overrides[get_current_user] = lambda: actors[2]
    assert client.get('/api/ppr/me/relative-change-requests').json()['items'] == []
    assert client.get('/api/ppr/relative-change-requests/review-queue').status_code == 403
    assert client.post(f"/api/ppr/me/relative-change-requests/{request['request_id']}/resubmit",
                       json={'expected_revision': 1, **body}).status_code == 404
    path = f"/api/ppr/relative-change-requests/{request['request_id']}/decision"
    assert client.post(path, json={'expected_revision': 1, 'action': 'approve'}).status_code == 403
    app.dependency_overrides[get_current_user] = lambda: actors[3]
    with database.begin() as conn:
        conn.execute(text("UPDATE person_relatives SET updated_at=updated_at + interval '1 minute' WHERE relative_id=1"))
    assert client.post(path, json={'expected_revision': 1, 'action': 'approve'}).status_code == 409
    with database.connect() as conn:
        assert conn.execute(text("SELECT lifecycle_status FROM person_relatives WHERE relative_id=1")).scalar_one() == 'active'
        assert conn.execute(text("SELECT status FROM person_relative_change_requests WHERE request_id=:rid"),
                            {'rid': request['request_id']}).scalar_one() == 'pending'
    returned = client.post(path, json={'expected_revision': 1, 'action': 'return',
                                       'reason': 'The source record changed; review the new values'})
    assert returned.status_code == 200 and returned.json()['status'] == 'returned'
