# tests/operational_orders/test_workspace_freeze.py
"""Workspace freeze, drift detection and promotion replay tests (OO-IMP-003B)."""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.operational_orders.conftest import cleanup_workspace
from tests.operational_orders.test_helpers import (
    BASE,
    DOCUMENTS_BASE,
    confirm_block,
    create_editorial_ready_workspace,
    promote_workspace,
)

pytestmark = [
    pytest.mark.usefixtures("_require_oo_schema_fixture", "_require_oo_document_schema_fixture"),
]


def _promote_editorial_workspace(client, headers, seed):
    author_ref = str(seed["executor_user_id"])
    workspace_id, detail = create_editorial_ready_workspace(
        client, headers, seed, author_ref=author_ref
    )
    promoted = promote_workspace(client, headers, workspace_id)
    assert promoted.status_code == 200, promoted.text
    payload = promoted.json()
    assert payload["workspace_frozen"] is True
    return workspace_id, detail, payload


def test_promotion_freezes_workspace(client, oo_editorial_headers, seed):
    workspace_id, _, promoted = _promote_editorial_workspace(client, oo_editorial_headers, seed)
    try:
        detail = client.get(f"{BASE}/{workspace_id}", headers=oo_editorial_headers).json()
        assert detail["workspace"]["stage"] == "DOCUMENT_PROMOTED"
        assert promoted["idempotent_replay"] is False
        assert promoted["workspace_drift_detected"] is False
        assert promoted["revision_recommended"] is False
        assert promoted["document_id"] == promoted["document"]["document"]["document_id"]
        assert promoted["promotion_id"] == promoted["document"]["promotion"]["id"]
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_frozen_workspace_edit_blocked(client, oo_editorial_headers, seed):
    workspace_id, detail, _ = _promote_editorial_workspace(client, oo_editorial_headers, seed)
    try:
        body_block = next(b for b in detail["blocks"] if b["locale"] == "ru" and b["block_type"] == "BODY")
        resp = client.patch(
            f"{BASE}/{workspace_id}/blocks/{body_block['block_id']}",
            json={"workspace_effective_text": "Blocked edit"},
            headers=oo_editorial_headers,
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["code"] == "OO_WORKSPACE_FROZEN"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_frozen_workspace_translation_blocked(client, oo_editorial_headers, seed):
    author_ref = str(seed["executor_user_id"])
    workspace_id, _, _ = _promote_editorial_workspace(client, oo_editorial_headers, seed)
    try:
        resp = client.post(
            f"{BASE}/{workspace_id}/translation-assignments",
            json={
                "target_locale": "kk",
                "assigned_to": {"reference_type": "PERSON", "reference": author_ref, "display_name": "Translator"},
            },
            headers=oo_editorial_headers,
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["code"] == "OO_WORKSPACE_FROZEN"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_frozen_workspace_confirmation_blocked(client, oo_editorial_headers, seed):
    workspace_id, detail, _ = _promote_editorial_workspace(client, oo_editorial_headers, seed)
    try:
        block = next(b for b in detail["blocks"] if b["locale"] == "ru")
        resp = confirm_block(
            client,
            oo_editorial_headers,
            workspace_id,
            block,
            role="CONTENT_AUTHOR",
            confirmer_ref=str(seed["executor_user_id"]),
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["code"] == "OO_WORKSPACE_FROZEN"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_frozen_workspace_reconciliation_blocked(client, oo_editorial_headers, seed):
    workspace_id, detail, _ = _promote_editorial_workspace(client, oo_editorial_headers, seed)
    try:
        fresh = client.get(f"{BASE}/{workspace_id}", headers=oo_editorial_headers).json()
        ru_block = next(b for b in fresh["blocks"] if b["locale"] == "ru" and b["block_type"] == "TITLE")
        kk_block = next(
            b
            for b in fresh["blocks"]
            if b["locale"] == "kk" and b["block_type"] == "TITLE" and b["sequence"] == ru_block["sequence"]
        )
        resp = client.post(
            f"{BASE}/{workspace_id}/reconciliations",
            json={"ru_block_id": ru_block["block_id"], "kk_block_id": kk_block["block_id"]},
            headers=oo_editorial_headers,
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["code"] == "OO_WORKSPACE_FROZEN"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_frozen_workspace_clarification_resolve_blocked(client, oo_editorial_headers, seed):
    workspace_id, _, _ = _promote_editorial_workspace(client, oo_editorial_headers, seed)
    try:
        with engine.begin() as conn:
            clar_id = conn.execute(
                text(
                    """
                    INSERT INTO public.operational_order_clarifications (
                        workspace_id, code, severity, category, message, status, requested_by
                    ) VALUES (
                        :workspace_id, 'OI999', 'WARNING', 'Test', 'Test clarification', 'OPEN', :requested_by
                    )
                    RETURNING clarification_id
                    """
                ),
                {
                    "workspace_id": int(workspace_id),
                    "requested_by": int(seed["executor_user_id"]),
                },
            ).scalar_one()
        resp = client.post(
            f"{BASE}/{workspace_id}/clarifications/{clar_id}/resolve",
            json={"resolution_note": "Attempted resolve"},
            headers=oo_editorial_headers,
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["code"] == "OO_WORKSPACE_FROZEN"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_repromote_without_drift_is_idempotent_replay(client, oo_editorial_headers, seed):
    workspace_id, _, first = _promote_editorial_workspace(client, oo_editorial_headers, seed)
    try:
        second = promote_workspace(client, oo_editorial_headers, workspace_id)
        assert second.status_code == 200
        payload = second.json()
        assert payload["idempotent_replay"] is True
        assert payload["workspace_frozen"] is True
        assert payload["workspace_drift_detected"] is False
        assert payload["revision_recommended"] is False
        assert payload["document_id"] == first["document_id"]
        assert payload["promotion_id"] == first["promotion_id"]
        codes = {issue["code"] for issue in payload["validation"]["issues"]}
        assert "OO314" in codes
        assert "OO315" in codes
        assert "OO311" not in codes
        assert "OO313" not in codes
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_repromote_with_drift_returns_revision_advisory(client, oo_editorial_headers, seed):
    workspace_id, _, first = _promote_editorial_workspace(client, oo_editorial_headers, seed)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE public.operational_order_draft_blocks
                    SET workspace_effective_text = 'Drifted body text after promotion'
                    WHERE workspace_id = :workspace_id
                      AND locale = 'ru'
                      AND block_type = 'BODY'
                    """
                ),
                {"workspace_id": int(workspace_id)},
            )
        second = promote_workspace(client, oo_editorial_headers, workspace_id)
        assert second.status_code == 200
        payload = second.json()
        assert payload["idempotent_replay"] is True
        assert payload["workspace_drift_detected"] is True
        assert payload["revision_recommended"] is True
        assert payload["document_id"] == first["document_id"]
        codes = {issue["code"] for issue in payload["validation"]["issues"]}
        assert "OO311" in codes
        assert "OO313" in codes
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_read_still_works_after_freeze(client, oo_editorial_headers, seed):
    workspace_id, _, promoted = _promote_editorial_workspace(client, oo_editorial_headers, seed)
    document_id = promoted["document_id"]
    try:
        workspace_resp = client.get(f"{BASE}/{workspace_id}", headers=oo_editorial_headers)
        document_resp = client.get(f"{DOCUMENTS_BASE}/{document_id}", headers=oo_editorial_headers)
        localizations_resp = client.get(
            f"{DOCUMENTS_BASE}/{document_id}/localizations",
            headers=oo_editorial_headers,
        )
        assert workspace_resp.status_code == 200
        assert document_resp.status_code == 200
        assert localizations_resp.status_code == 200
        assert workspace_resp.json()["workspace"]["stage"] == "DOCUMENT_PROMOTED"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)
