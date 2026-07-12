# tests/operational_orders/test_draft_intake_api.py
"""API tests for Operational Orders draft intake."""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.operational_orders.conftest import cleanup_workspace

pytestmark = pytest.mark.usefixtures("_require_oo_schema_fixture")

BASE = "/api/operational-orders/draft-workspaces"


def _payload(*, author_ref: str = "author-api-001", locales: tuple[str, ...] = ("ru",)):
    blocks = []
    for idx, locale in enumerate(locales, start=1):
        blocks.append(
            {
                "locale": locale,
                "block_type": "TITLE" if idx == 1 else "BODY",
                "submitted_text": f"{locale.upper()} submitted text",
                "source_type": "SUBMITTED",
                "sequence": idx,
            }
        )
    return {
        "initiator": {"reference_type": "PERSON", "reference": "init-api-001", "display_name": "Initiator"},
        "content_author": {"reference_type": "PERSON", "reference": author_ref, "display_name": "Author"},
        "submitting_org_unit_id": None,
        "blocks": blocks,
    }


@pytest.fixture
def api_payload(seed):
    body = _payload(locales=("ru", "kk"))
    body["submitting_org_unit_id"] = int(seed["unit_id"])
    return body


def test_create_list_detail(client, oo_intake_headers, api_payload, seed):
    create_resp = client.post(BASE, json=api_payload, headers=oo_intake_headers)
    assert create_resp.status_code == 200, create_resp.text
    workspace_id = create_resp.json()["workspace"]["workspace_id"]
    try:
        list_resp = client.get(BASE, headers=oo_intake_headers)
        assert list_resp.status_code == 200
        assert list_resp.json()["total"] >= 1

        detail_resp = client.get(f"{BASE}/{workspace_id}", headers=oo_intake_headers)
        assert detail_resp.status_code == 200
        body = detail_resp.json()
        assert body["workspace"]["workspace_id"] == workspace_id
        assert len(body["blocks"]) == 2
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_accept_and_validate(client, oo_intake_headers, api_payload):
    create_resp = client.post(BASE, json=api_payload, headers=oo_intake_headers)
    workspace_id = create_resp.json()["workspace"]["workspace_id"]
    try:
        accept_resp = client.post(
            f"{BASE}/{workspace_id}/accept",
            json={},
            headers=oo_intake_headers,
        )
        assert accept_resp.status_code == 200
        assert accept_resp.json()["workspace"]["stage"] == "ACCEPTED"

        validate_resp = client.post(
            f"{BASE}/{workspace_id}/validate",
            json={},
            headers=oo_intake_headers,
        )
        assert validate_resp.status_code == 200
        assert "validation" in validate_resp.json()
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_add_block_and_edit_effective(client, oo_intake_headers, api_payload):
    create_resp = client.post(BASE, json=api_payload, headers=oo_intake_headers)
    workspace_id = create_resp.json()["workspace"]["workspace_id"]
    try:
        client.post(f"{BASE}/{workspace_id}/accept", json={}, headers=oo_intake_headers)
        add_resp = client.post(
            f"{BASE}/{workspace_id}/blocks",
            json={
                "locale": "ru",
                "block_type": "PREAMBLE",
                "submitted_text": "New preamble",
                "source_type": "SUBMITTED",
                "sequence": 1,
            },
            headers=oo_intake_headers,
        )
        assert add_resp.status_code == 200

        ru_block = next(b for b in add_resp.json()["blocks"] if b["locale"] == "ru" and b["block_type"] == "TITLE")
        patch_resp = client.patch(
            f"{BASE}/{workspace_id}/blocks/{ru_block['block_id']}",
            json={"workspace_effective_text": "Effective RU title"},
            headers=oo_intake_headers,
        )
        assert patch_resp.status_code == 200
        patched = next(
            b for b in patch_resp.json()["blocks"] if b["block_id"] == ru_block["block_id"]
        )
        assert patched["workspace_effective_text"] == "Effective RU title"
        assert patched["submitted_text"] != patched["workspace_effective_text"]
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_ready_for_editorial(client, oo_intake_headers, api_payload):
    create_resp = client.post(BASE, json=api_payload, headers=oo_intake_headers)
    workspace_id = create_resp.json()["workspace"]["workspace_id"]
    try:
        client.post(f"{BASE}/{workspace_id}/accept", json={}, headers=oo_intake_headers)
        ready_resp = client.post(
            f"{BASE}/{workspace_id}/ready-for-editorial",
            json={},
            headers=oo_intake_headers,
        )
        assert ready_resp.status_code == 200
        assert ready_resp.json()["workspace"]["stage"] == "READY_FOR_EDITORIAL"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_unauthorized(client, api_payload):
    resp = client.post(BASE, json=api_payload)
    assert resp.status_code in {401, 403}


def test_forbidden_without_permission(client, seed, api_payload):
    from tests.conftest import auth_headers

    headers = auth_headers(seed["executor_user_id"])
    resp = client.post(BASE, json=api_payload, headers=headers)
    assert resp.status_code == 403
    body = resp.json()
    assert body["detail"]["code"] == "OO_FORBIDDEN"


def test_error_shape_not_found(client, oo_intake_headers):
    resp = client.get(f"{BASE}/999999999", headers=oo_intake_headers)
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "OO_WORKSPACE_NOT_FOUND"


def test_concurrency_conflict(client, oo_intake_headers, api_payload):
    create_resp = client.post(BASE, json=api_payload, headers=oo_intake_headers)
    workspace_id = create_resp.json()["workspace"]["workspace_id"]
    version = create_resp.json()["workspace"]["version"]
    try:
        client.post(
            f"{BASE}/{workspace_id}/accept",
            json={"expected_version": version},
            headers=oo_intake_headers,
        )
        conflict_resp = client.post(
            f"{BASE}/{workspace_id}/accept",
            json={"expected_version": version},
            headers=oo_intake_headers,
        )
        assert conflict_resp.status_code == 409
        assert conflict_resp.json()["detail"]["code"] == "OO_WORKSPACE_VERSION_CONFLICT"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)
