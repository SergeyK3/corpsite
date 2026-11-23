"""The compatibility photo endpoint submits for review, never directly activates a photo."""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app.api import ppr_router as api
from app.auth import get_current_user
from app.personnel_files import service


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(api, 'assert_ppr_read_path_activation_allowed', lambda: None)
    monkeypatch.setattr(api, 'require_personnel_card_edit_for_person', lambda user, person_id: None)
    monkeypatch.setattr(api._query_service, 'load_summary', lambda *, person_id: SimpleNamespace(person_id=person_id))
    app=FastAPI(); app.include_router(api.router)
    app.dependency_overrides[get_current_user]=lambda: {'user_id':19}
    return TestClient(app)


def test_upload_submits_exact_route_subject_for_review(client,monkeypatch):
    seen={}; vid=str(uuid4())
    def submit(user,person_id,**kwargs):
        seen.update(person_id=person_id,user=user,**kwargs)
        return {'version_id':vid,'state':'pending'}
    monkeypatch.setattr(service,'submit',submit)
    response=client.post('/api/ppr/persons/99/photo',files={'file':('person-100.jpg',b'synthetic delegated bytes','image/jpeg')})
    assert response.status_code==200
    assert response.json()=={'person_id':99,'version_id':vid,'status':'pending'}
    assert seen['person_id']==99
    assert seen['kind']=='photo'


def test_upload_is_forbidden_without_card_permission(client,monkeypatch):
    def deny(*_): raise HTTPException(403,'Forbidden')
    monkeypatch.setattr(api,'require_personnel_card_edit_for_person',deny)
    response=client.post('/api/ppr/persons/99/photo',files={'file':('test.jpg',b'test','image/jpeg')})
    assert response.status_code==403


def test_upload_rejects_non_jpeg_before_storage(client,monkeypatch):
    def unexpected(*args,**kwargs): raise AssertionError('Must not reach storage')
    monkeypatch.setattr(service,'submit',unexpected)
    response=client.post('/api/ppr/persons/99/photo',files={'file':('test.png',b'test','image/png')})
    assert response.status_code==422


def test_legacy_replacement_does_not_bypass_version_conflict(client,monkeypatch):
    def conflict(*args,**kwargs): raise HTTPException(409,'Use exact version for replacement')
    monkeypatch.setattr(service,'submit',conflict)
    response=client.post('/api/ppr/persons/99/photo',files={'file':('test.jpg',b'test','image/jpeg')})
    assert response.status_code==409
