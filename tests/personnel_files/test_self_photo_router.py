"""Photo-only API with synthetic employee, reviewer, and foreign employee accounts."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.personnel_files import photo_router, service
from tests.personnel_files.test_policy_and_validation import image


def test_photo_return_retry_approve_and_owner_boundaries(seeded, monkeypatch):
    actors = seeded
    monkeypatch.setattr(photo_router, 'self_person', lambda user: {1: 1, 2: 2}[user['user_id']])
    app = FastAPI()
    app.include_router(photo_router.router)
    app.dependency_overrides[get_current_user] = lambda: actors[1]
    client = TestClient(app)
    url = '/api/personnel-files/me'
    first = client.post(url, data={'kind': 'photo', 'title': 'Fictional face photo'},
                        files={'file': ('first.jpg', image(), 'image/jpeg')})
    assert first.status_code == 201, first.text
    version = first.json()
    assert version['state'] == 'pending'
    assert service.active_photo(actors[1], 1) == (False, None)
    assert client.post(url, data={'kind': 'certificate', 'title': 'Not in this iteration'},
                       files={'file': ('other.jpg', image(), 'image/jpeg')}).status_code == 422
    app.dependency_overrides[get_current_user] = lambda: actors[2]
    assert client.get('/api/personnel-files/me').json()['items'] == []
    assert client.get(f"/api/personnel-files/versions/{version['version_id']}/preview").status_code == 403
    assert client.post(f"/api/personnel-files/versions/{version['version_id']}/decision",
                       json={'expected_revision': version['revision'], 'action': 'approve'}).status_code == 403
    app.dependency_overrides[get_current_user] = lambda: actors[3]
    queue = client.get('/api/personnel-files/review-queue')
    assert queue.status_code == 200 and queue.json()['items'][0]['version_id'] == version['version_id']
    decision_url = f"/api/personnel-files/versions/{version['version_id']}/decision"
    returned = client.post(decision_url, json={'expected_revision': version['revision'],
                                                 'action': 'return', 'reason': 'Face unclear'})
    assert returned.status_code == 200, returned.text
    assert returned.json()['state'] == 'returned' and returned.json()['reason'] == 'Face unclear'
    app.dependency_overrides[get_current_user] = lambda: actors[1]
    retried = client.post(url, data={'kind': 'photo', 'title': 'Fictional face photo',
                                     'set_id': version['set_id'], 'expected_revision': returned.json()['revision'],
                                     'expected_version_id': version['version_id']},
                          files={'file': ('second.jpg', image(), 'image/jpeg')})
    assert retried.status_code == 201, retried.text
    assert retried.json()['state'] == 'pending'
    assert service.active_photo(actors[1], 1) == (False, None)
    app.dependency_overrides[get_current_user] = lambda: actors[3]
    approved = client.post(f"/api/personnel-files/versions/{retried.json()['version_id']}/decision",
                           json={'expected_revision': retried.json()['revision'], 'action': 'approve'})
    assert approved.status_code == 200, approved.text
    assert approved.json()['state'] == 'approved'
    managed, content = service.active_photo(actors[1], 1)
    assert managed and content.startswith(b'\xff\xd8')
    current_url = '/api/personnel-files/persons/1/current-photo'
    assert client.get(current_url).content == content
    app.dependency_overrides[get_current_user] = lambda: actors[2]
    assert client.get(current_url).status_code == 403
    app.dependency_overrides[get_current_user] = lambda: actors[1]
    replacement = client.post(url, data={'kind': 'photo', 'title': 'Replacement',
                                         'set_id': version['set_id'], 'expected_revision': approved.json()['revision'],
                                         'expected_version_id': approved.json()['version_id']},
                              files={'file': ('third.jpg', image(), 'image/jpeg')})
    assert replacement.status_code == 201, replacement.text
    assert replacement.json()['state'] == 'pending'
    assert service.active_photo(actors[1], 1) == (True, content)
    app.dependency_overrides[get_current_user] = lambda: actors[3]
    returned_replacement = client.post(f"/api/personnel-files/versions/{replacement.json()['version_id']}/decision",
                                       json={'expected_revision': replacement.json()['revision'],
                                             'action': 'return', 'reason': 'Try again'})
    assert returned_replacement.status_code == 200
    assert service.active_photo(actors[1], 1) == (True, content)
