# tests/operational_orders/test_submitted_text_immutable_api.py
"""API-level submitted text immutability tests."""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.operational_orders.conftest import cleanup_workspace

pytestmark = pytest.mark.usefixtures("_require_oo_schema_fixture")

BASE = "/api/operational-orders/draft-workspaces"


@pytest.fixture
def api_payload(seed):
    return {
        "initiator": {"reference_type": "PERSON", "reference": "init-api-001", "display_name": "Initiator"},
        "content_author": {"reference_type": "PERSON", "reference": "author-api-001", "display_name": "Author"},
        "submitting_org_unit_id": int(seed["unit_id"]),
        "blocks": [
            {
                "locale": "ru",
                "block_type": "TITLE",
                "submitted_text": "RU submitted text",
                "source_type": "SUBMITTED",
                "sequence": 1,
            },
            {
                "locale": "kk",
                "block_type": "TITLE",
                "submitted_text": "KK submitted text",
                "source_type": "SUBMITTED",
                "sequence": 1,
            },
        ],
    }


def test_patch_effective_text_does_not_change_submitted_text(client, oo_intake_headers, api_payload):
    create_resp = client.post(BASE, json=api_payload, headers=oo_intake_headers)
    workspace_id = create_resp.json()["workspace"]["workspace_id"]
    original_submitted = create_resp.json()["blocks"][0]["submitted_text"]
    block_id = create_resp.json()["blocks"][0]["block_id"]
    try:
        patch_resp = client.patch(
            f"{BASE}/{workspace_id}/blocks/{block_id}",
            json={"workspace_effective_text": "Edited effective only"},
            headers=oo_intake_headers,
        )
        assert patch_resp.status_code == 200
        patched_block = next(b for b in patch_resp.json()["blocks"] if b["block_id"] == block_id)
        assert patched_block["submitted_text"] == original_submitted
        assert patched_block["workspace_effective_text"] == "Edited effective only"

        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT submitted_text, workspace_effective_text
                    FROM public.operational_order_draft_blocks
                    WHERE block_id = :block_id
                    """
                ),
                {"block_id": int(block_id)},
            ).mappings().one()
        assert row["submitted_text"] == original_submitted
        assert row["workspace_effective_text"] == "Edited effective only"

        provenance = patch_resp.json()["provenance"]
        submission_rows = [p for p in provenance if p["action"] == "SUBMISSION"]
        assert submission_rows
        assert all(p["content_fingerprint"] for p in provenance)
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_effective_patch_schema_has_no_submitted_text_field():
    from app.operational_orders.schemas.draft_workspace import DraftBlockEffectivePatchIn

    fields = set(DraftBlockEffectivePatchIn.model_fields)
    assert "workspace_effective_text" in fields
    assert "submitted_text" not in fields
