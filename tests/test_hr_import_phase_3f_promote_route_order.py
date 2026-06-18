"""Regression: POST .../normalized-records/promote must not shadow PATCH .../{record_id}."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import auth_headers


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_post_promote_route_not_matched_as_patch_record_id(
    client: TestClient,
    privileged_headers,
):
    """POST /promote must hit the promote handler, not PATCH /{record_id} (405 Allow: PATCH)."""
    resp = client.post(
        "/directory/personnel/import/normalized-records/promote",
        headers={**privileged_headers, "Content-Type": "application/json"},
        json={"dry_run": True, "batch_id": 1},
    )
    assert resp.status_code != 405, (
        f"POST promote was routed to PATCH handler: {resp.status_code} {resp.text!r} "
        f"Allow={resp.headers.get('allow')}"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["dry_run"] is True
    assert "requested" in body
    assert "would_promote" in body


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_patch_review_route_unchanged_after_promote_route_order_fix(
    client: TestClient,
    privileged_headers,
):
    resp = client.patch(
        "/directory/personnel/import/normalized-records/999999999",
        headers={**privileged_headers, "Content-Type": "application/json"},
        json={"review_status": "approved"},
    )
    assert resp.status_code != 405, resp.text
    assert resp.status_code == 404, resp.text
