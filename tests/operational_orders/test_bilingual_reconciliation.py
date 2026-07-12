# tests/operational_orders/test_bilingual_reconciliation.py
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.operational_orders.conftest import cleanup_workspace
from tests.operational_orders.test_helpers import BASE, confirm_block, create_ready_workspace

pytestmark = pytest.mark.usefixtures("_require_oo_schema_fixture")


def _confirm_all_blocks(client, headers, workspace_id, detail, author_ref):
    for block in detail["blocks"]:
        confirm_block(
            client,
            headers,
            workspace_id,
            block,
            role="CONTENT_AUTHOR",
            confirmer_ref=author_ref,
        )


def test_reconcile_current_ru_kk_pair(client, oo_editorial_headers, seed):
    author_ref = str(seed["executor_user_id"])
    workspace_id, detail = create_ready_workspace(
        client, oo_editorial_headers, seed, author_ref=author_ref, locales=("ru", "kk")
    )
    try:
        _confirm_all_blocks(client, oo_editorial_headers, workspace_id, detail, author_ref)
        ru_block = next(b for b in detail["blocks"] if b["locale"] == "ru" and b["block_type"] == "TITLE")
        kk_block = next(b for b in detail["blocks"] if b["locale"] == "kk" and b["block_type"] == "TITLE")
        resp = client.post(
            f"{BASE}/{workspace_id}/reconciliations",
            json={
                "ru_block_id": ru_block["block_id"],
                "kk_block_id": kk_block["block_id"],
                "ru_block_expected_version": ru_block["version"],
                "kk_block_expected_version": kk_block["version"],
            },
            headers=oo_editorial_headers,
        )
        assert resp.status_code == 200
        reconciled = [r for r in resp.json()["bilingual_reconciliations"] if r["status"] == "RECONCILED"]
        assert len(reconciled) >= 1
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_missing_confirmation_blocks_reconciliation(client, oo_editorial_headers, seed):
    author_ref = str(seed["executor_user_id"])
    workspace_id, detail = create_ready_workspace(
        client, oo_editorial_headers, seed, author_ref=author_ref, locales=("ru", "kk")
    )
    try:
        ru_block = next(b for b in detail["blocks"] if b["locale"] == "ru")
        kk_block = next(b for b in detail["blocks"] if b["locale"] == "kk")
        resp = client.post(
            f"{BASE}/{workspace_id}/reconciliations",
            json={"ru_block_id": ru_block["block_id"], "kk_block_id": kk_block["block_id"]},
            headers=oo_editorial_headers,
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["code"] == "OO_EDITORIAL_PACKAGE_NOT_READY"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_text_edit_invalidates_reconciliation(client, oo_editorial_headers, seed):
    author_ref = str(seed["executor_user_id"])
    workspace_id, detail = create_ready_workspace(
        client, oo_editorial_headers, seed, author_ref=author_ref, locales=("ru", "kk")
    )
    try:
        _confirm_all_blocks(client, oo_editorial_headers, workspace_id, detail, author_ref)
        ru_block = next(b for b in detail["blocks"] if b["locale"] == "ru")
        kk_block = next(b for b in detail["blocks"] if b["locale"] == "kk")
        rec_resp = client.post(
            f"{BASE}/{workspace_id}/reconciliations",
            json={"ru_block_id": ru_block["block_id"], "kk_block_id": kk_block["block_id"]},
            headers=oo_editorial_headers,
        )
        assert rec_resp.status_code == 200
        patch_resp = client.patch(
            f"{BASE}/{workspace_id}/blocks/{ru_block['block_id']}",
            json={"workspace_effective_text": "Changed RU text"},
            headers=oo_editorial_headers,
        )
        invalidated = [
            r for r in patch_resp.json()["bilingual_reconciliations"] if r["status"] == "INVALIDATED"
        ]
        assert len(invalidated) >= 1
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)
