# tests/operational_orders/test_content_confirmations.py
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.operational_orders.conftest import cleanup_workspace
from tests.operational_orders.test_helpers import BASE, confirm_block, create_ready_workspace

pytestmark = pytest.mark.usefixtures("_require_oo_schema_fixture")


def test_content_author_confirms_current_fingerprint(client, oo_editorial_headers, seed):
    author_ref = str(seed["executor_user_id"])
    workspace_id, detail = create_ready_workspace(
        client, oo_editorial_headers, seed, author_ref=author_ref, locales=("ru", "kk")
    )
    try:
        ru_block = next(b for b in detail["blocks"] if b["locale"] == "ru" and b["block_type"] == "TITLE")
        resp = confirm_block(
            client,
            oo_editorial_headers,
            workspace_id,
            ru_block,
            role="CONTENT_AUTHOR",
            confirmer_ref=author_ref,
        )
        assert resp.status_code == 200
        confirmations = resp.json()["content_confirmations"]
        assert any(c["confirmation_role"] == "CONTENT_AUTHOR" and c["status"] == "CONFIRMED" for c in confirmations)
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_wrong_user_cannot_confirm_as_content_author(client, oo_editorial_headers, seed):
    author_ref = "different-author-001"
    workspace_id, detail = create_ready_workspace(
        client, oo_editorial_headers, seed, author_ref=author_ref, locales=("ru", "kk")
    )
    try:
        ru_block = next(b for b in detail["blocks"] if b["locale"] == "ru")
        resp = confirm_block(
            client,
            oo_editorial_headers,
            workspace_id,
            ru_block,
            role="CONTENT_AUTHOR",
            confirmer_ref=str(seed["executor_user_id"]),
        )
        assert resp.status_code == 403
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_duplicate_confirmation_idempotent(client, oo_editorial_headers, seed):
    author_ref = str(seed["executor_user_id"])
    workspace_id, detail = create_ready_workspace(
        client, oo_editorial_headers, seed, author_ref=author_ref, locales=("ru", "kk")
    )
    try:
        ru_block = next(b for b in detail["blocks"] if b["locale"] == "ru")
        first = confirm_block(
            client, oo_editorial_headers, workspace_id, ru_block, role="CONTENT_AUTHOR", confirmer_ref=author_ref
        )
        second = confirm_block(
            client, oo_editorial_headers, workspace_id, ru_block, role="CONTENT_AUTHOR", confirmer_ref=author_ref
        )
        assert first.status_code == 200
        assert second.status_code == 200
        confirmed = [
            c
            for c in second.json()["content_confirmations"]
            if c["confirmation_role"] == "CONTENT_AUTHOR" and c["status"] == "CONFIRMED"
        ]
        assert len(confirmed) == 1
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_text_edit_supersedes_confirmation(client, oo_editorial_headers, seed):
    author_ref = str(seed["executor_user_id"])
    workspace_id, detail = create_ready_workspace(
        client, oo_editorial_headers, seed, author_ref=author_ref, locales=("ru", "kk")
    )
    try:
        ru_block = next(b for b in detail["blocks"] if b["locale"] == "ru")
        confirm_block(
            client, oo_editorial_headers, workspace_id, ru_block, role="CONTENT_AUTHOR", confirmer_ref=author_ref
        )
        patch_resp = client.patch(
            f"{BASE}/{workspace_id}/blocks/{ru_block['block_id']}",
            json={"workspace_effective_text": "Updated RU effective"},
            headers=oo_editorial_headers,
        )
        assert patch_resp.status_code == 200
        superseded = [
            c
            for c in patch_resp.json()["content_confirmations"]
            if c["status"] == "SUPERSEDED" and c["confirmation_role"] == "CONTENT_AUTHOR"
        ]
        assert len(superseded) >= 1
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)
