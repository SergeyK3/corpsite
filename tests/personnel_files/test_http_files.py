"""Real synthetic bytes through the authenticated HTTP file workflow."""
import hashlib
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.personnel_files.router import router
from tests.personnel_files.test_policy_and_validation import image, pdf


@pytest.mark.parametrize('format', ['pdf','png','photo'])
def test_upload_preview_download_and_other_employee_denial(seeded, format):
    actors = seeded
    data = pdf() if format=='pdf' else image('PNG') if format=='png' else image()
    mime = {'pdf':'application/pdf','png':'image/png','photo':'image/jpeg'}[format]
    kind = 'photo' if format=='photo' else 'certificate'
    payload = {'kind':kind,'title':'FICTIONAL HTTP file test'}
    if kind=='certificate':
        payload['certificate'] = json.dumps({'entry_id':1,'specialty_name_at_issue':'FICTIONAL specialty A',
            'issued_at':'2025-01-01','valid_until':'2031-01-01'})
    app = FastAPI(); app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: actors[3]
    client = TestClient(app)
    uploaded = client.post('/api/personnel-files/persons/1',data=payload,
        files={'file':('fictional.'+('jpg' if format=='photo' else format),data,mime)})
    assert uploaded.status_code==201
    record = uploaded.json()
    path = '/api/personnel-files/versions/'+record['version_id']
    assert record['state']=='pending'
    assert 'storage_key' not in record
    preview = client.get(path+'/preview')
    assert preview.status_code==200 and preview.headers['content-type']=='image/png'
    assert preview.content.startswith(b'\x89PNG')
    original = client.get(path+'/download')
    assert original.status_code==200 and original.headers['content-type']==mime
    assert original.headers['cache-control']=='private, no-store'
    assert hashlib.sha256(original.content).digest()==hashlib.sha256(data).digest()
    decision = {'expected_revision':record['revision'],'action':'approve','reason':'FICTIONAL review'}
    if kind=='certificate':
        comparison = client.get(path+'/review-context')
        assert comparison.status_code==200
        decision['expected_certificate_context'] = comparison.json()['context_token']
    assert client.post(path+'/decision',json=decision).status_code==200
    app.dependency_overrides[get_current_user] = lambda: actors[1]
    assert client.get(path+'/preview').status_code==200
    owner_download = client.get(path+'/download')
    assert owner_download.status_code==(403 if kind=='photo' else 200)
    if kind=='certificate': assert owner_download.content==data
    app.dependency_overrides[get_current_user] = lambda: actors[2]
    for operation in ('preview','download'):
        denied = client.get(path+'/'+operation)
        assert denied.status_code==403
        assert denied.headers['content-type']=='application/json'
        assert not denied.content.startswith((b'%PDF-',b'\x89PNG',b'\xff\xd8'))
    app.dependency_overrides.clear()
    assert client.get(path+'/preview').status_code==401
    assert client.get(path+'/download').status_code==401
