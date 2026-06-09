# tests/test_working_contacts_routes.py
from __future__ import annotations

import pytest

from tests.conftest import auth_headers


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


def test_list_working_contacts_returns_200(client, seed, privileged_headers):
    resp = client.get("/directory/working-contacts", headers=privileged_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert isinstance(body["items"], list)


def test_list_working_contacts_by_org_unit_returns_200(client, seed, privileged_headers):
    if seed.get("unit_id") is None:
        pytest.skip("unit table not available")

    resp = client.get(
        f"/directory/working-contacts?org_unit_id={seed['unit_id']}",
        headers=privileged_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("filter_org_unit_id") == seed["unit_id"]


def test_get_working_contact_returns_200(client, seed, privileged_headers):
    user_id = seed["initiator_user_id"]
    resp = client.get(f"/directory/working-contacts/{user_id}", headers=privileged_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user_id"] == user_id
    assert "unit_name" in body
    assert "unit_name_ru" in body
