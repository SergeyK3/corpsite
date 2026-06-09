# tests/test_directory_contacts_positions_routes.py
from __future__ import annotations

import pytest

from tests.conftest import auth_headers


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


def test_list_contacts_returns_200(client, privileged_headers):
    resp = client.get("/directory/contacts", headers=privileged_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert isinstance(body["items"], list)


def test_list_positions_returns_200(client, privileged_headers):
    resp = client.get("/directory/positions", headers=privileged_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert isinstance(body["items"], list)
