# tests/operational_orders/test_editorial_invalidation.py
"""Invalidation and history retention tests for OO-IMP-002."""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.operational_orders.conftest import cleanup_workspace
from tests.operational_orders.test_helpers import BASE, confirm_block, create_ready_workspace

pytestmark = pytest.mark.usefixtures("_require_oo_schema_fixture")


def _audit_actions(conn, workspace_id: int, action: str) -> int:
    return int(
        conn.execute(
            text(
                """
                SELECT COUNT(1)
                FROM public.operational_order_draft_audit
                WHERE workspace_id = :workspace_id AND action = :action
                """
            ),
            {"workspace_id": int(workspace_id), "action": action},
        ).scalar()
        or 0
    )


def test_source_edit_supersedes_completed_assignment(client, oo_editorial_headers, seed):
    author_ref = str(seed["executor_user_id"])
    workspace_id, _ = create_ready_workspace(
        client, oo_editorial_headers, seed, author_ref=author_ref, locales=("ru",)
    )
    try:
        create_resp = client.post(
            f"{BASE}/{workspace_id}/translation-assignments",
            json={
                "target_locale": "kk",
                "assigned_to": {"reference_type": "PERSON", "reference": author_ref, "display_name": "Translator"},
            },
            headers=oo_editorial_headers,
        )
        assignment_id = create_resp.json()["translation_assignments"][0]["id"]
        client.post(
            f"{BASE}/{workspace_id}/translation-assignments/{assignment_id}/accept",
            json={},
            headers=oo_editorial_headers,
        )
        client.post(
            f"{BASE}/{workspace_id}/blocks",
            json={
                "locale": "kk",
                "block_type": "TITLE",
                "submitted_text": "KK title",
                "source_type": "IMPORTED",
                "sequence": 1,
            },
            headers=oo_editorial_headers,
        )
        client.post(
            f"{BASE}/{workspace_id}/translation-assignments/{assignment_id}/start",
            json={},
            headers=oo_editorial_headers,
        )
        detail = client.get(f"{BASE}/{workspace_id}", headers=oo_editorial_headers).json()
        kk_block = next(b for b in detail["blocks"] if b["locale"] == "kk")
        client.post(
            f"{BASE}/{workspace_id}/translation-assignments/{assignment_id}/complete",
            json={"target_block_id": kk_block["block_id"]},
            headers=oo_editorial_headers,
        )

        ru_block = next(b for b in detail["blocks"] if b["locale"] == "ru" and b["block_type"] == "BODY")
        client.patch(
            f"{BASE}/{workspace_id}/blocks/{ru_block['block_id']}",
            json={"workspace_effective_text": "Updated source RU body"},
            headers=oo_editorial_headers,
        )

        after = client.get(f"{BASE}/{workspace_id}", headers=oo_editorial_headers).json()
        superseded = [a for a in after["translation_assignments"] if a["status"] == "SUPERSEDED"]
        assert len(after["translation_assignments"]) == 1
        assert len(superseded) == 1
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_new_assignment_allowed_after_cancelled(client, oo_editorial_headers, seed):
    author_ref = str(seed["executor_user_id"])
    workspace_id, _ = create_ready_workspace(
        client, oo_editorial_headers, seed, author_ref=author_ref, locales=("ru",)
    )
    try:
        payload = {
            "target_locale": "kk",
            "assigned_to": {"reference_type": "PERSON", "reference": author_ref, "display_name": "Translator"},
        }
        first = client.post(
            f"{BASE}/{workspace_id}/translation-assignments",
            json=payload,
            headers=oo_editorial_headers,
        )
        assignment_id = first.json()["translation_assignments"][0]["id"]
        client.post(
            f"{BASE}/{workspace_id}/translation-assignments/{assignment_id}/cancel",
            json={},
            headers=oo_editorial_headers,
        )
        second = client.post(
            f"{BASE}/{workspace_id}/translation-assignments",
            json=payload,
            headers=oo_editorial_headers,
        )
        assert second.status_code == 200
        active = [
            a
            for a in second.json()["translation_assignments"]
            if a["status"] in {"REQUESTED", "ACCEPTED", "IN_PROGRESS"}
        ]
        cancelled = [a for a in second.json()["translation_assignments"] if a["status"] == "CANCELLED"]
        assert len(active) == 1
        assert len(cancelled) == 1
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_repeated_source_edit_does_not_duplicate_invalidation_audit(client, oo_editorial_headers, seed):
    author_ref = str(seed["executor_user_id"])
    workspace_id, detail = create_ready_workspace(
        client, oo_editorial_headers, seed, author_ref=author_ref, locales=("ru", "kk")
    )
    try:
        ru_block = next(b for b in detail["blocks"] if b["locale"] == "ru")
        kk_block = next(b for b in detail["blocks"] if b["locale"] == "kk")
        confirm_block(
            client, oo_editorial_headers, workspace_id, ru_block, role="CONTENT_AUTHOR", confirmer_ref=author_ref
        )
        confirm_block(
            client, oo_editorial_headers, workspace_id, kk_block, role="CONTENT_AUTHOR", confirmer_ref=author_ref
        )
        client.post(
            f"{BASE}/{workspace_id}/reconciliations",
            json={"ru_block_id": ru_block["block_id"], "kk_block_id": kk_block["block_id"]},
            headers=oo_editorial_headers,
        )

        with engine.begin() as conn:
            before = _audit_actions(conn, workspace_id, "RECONCILIATION_INVALIDATED")

        client.patch(
            f"{BASE}/{workspace_id}/blocks/{ru_block['block_id']}",
            json={"workspace_effective_text": "First RU change"},
            headers=oo_editorial_headers,
        )
        client.patch(
            f"{BASE}/{workspace_id}/blocks/{ru_block['block_id']}",
            json={"workspace_effective_text": "Second RU change"},
            headers=oo_editorial_headers,
        )

        with engine.begin() as conn:
            after = _audit_actions(conn, workspace_id, "RECONCILIATION_INVALIDATED")
            invalidated = conn.execute(
                text(
                    """
                    SELECT COUNT(1)
                    FROM public.operational_order_bilingual_reconciliations
                    WHERE workspace_id = :workspace_id AND status = 'INVALIDATED'
                    """
                ),
                {"workspace_id": int(workspace_id)},
            ).scalar()

        assert after - before == 1
        assert int(invalidated or 0) >= 1
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_historical_confirmations_retained_after_supersede(client, oo_editorial_headers, seed):
    author_ref = str(seed["executor_user_id"])
    workspace_id, detail = create_ready_workspace(
        client, oo_editorial_headers, seed, author_ref=author_ref, locales=("ru", "kk")
    )
    try:
        ru_block = next(b for b in detail["blocks"] if b["locale"] == "ru")
        confirm_block(
            client, oo_editorial_headers, workspace_id, ru_block, role="CONTENT_AUTHOR", confirmer_ref=author_ref
        )
        client.patch(
            f"{BASE}/{workspace_id}/blocks/{ru_block['block_id']}",
            json={"workspace_effective_text": "Changed RU"},
            headers=oo_editorial_headers,
        )
        with engine.begin() as conn:
            total = conn.execute(
                text(
                    """
                    SELECT COUNT(1)
                    FROM public.operational_order_content_confirmations
                    WHERE workspace_id = :workspace_id
                    """
                ),
                {"workspace_id": int(workspace_id)},
            ).scalar()
            superseded = conn.execute(
                text(
                    """
                    SELECT COUNT(1)
                    FROM public.operational_order_content_confirmations
                    WHERE workspace_id = :workspace_id AND status = 'SUPERSEDED'
                    """
                ),
                {"workspace_id": int(workspace_id)},
            ).scalar()
        assert int(total or 0) >= 1
        assert int(superseded or 0) >= 1
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)
