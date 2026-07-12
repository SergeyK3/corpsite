# tests/operational_orders/test_return_to_created.py
"""Return to CREATED lifecycle transition tests (OO-IMP-004)."""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.operational_orders.conftest import cleanup_workspace
from tests.operational_orders.test_helpers import (
    DOCUMENTS_BASE,
    assign_signing_authority,
    create_promoted_document,
    mark_ready_for_signature,
    return_to_created,
)

pytestmark = pytest.mark.usefixtures("_require_oo_lifecycle_schema_fixture")


def _return_to_created(client, headers, document_id, *, reason: str, expected_version: int):
    return client.post(
        f"{DOCUMENTS_BASE}/{document_id}/return-to-created",
        json={"reason": reason, "expected_version": expected_version},
        headers=headers,
    )


def test_ready_for_signature_returns_to_created(client, oo_lifecycle_headers, seed):
    workspace_id, document_id, promoted = create_promoted_document(client, oo_lifecycle_headers, seed)
    try:
        doc_version = promoted["document"]["document"]["version"]
        assign = assign_signing_authority(
            client, oo_lifecycle_headers, document_id, reference="return-signer", expected_version=doc_version
        )
        ready = mark_ready_for_signature(
            client, oo_lifecycle_headers, document_id, expected_version=assign.json()["document"]["version"]
        )
        ready_version = ready.json()["document"]["document"]["version"]

        returned = _return_to_created(
            client,
            oo_lifecycle_headers,
            document_id,
            reason="Needs queue correction",
            expected_version=ready_version,
        )
        assert returned.status_code == 200, returned.text
        assert returned.json()["document"]["document"]["status"] == "CREATED"
        assert returned.json()["idempotent_replay"] is False

        with engine.begin() as conn:
            audit = conn.execute(
                text(
                    """
                    SELECT action, transition_from, transition_to
                    FROM public.operational_order_lifecycle_audit
                    WHERE document_id = :document_id AND action = 'DOCUMENT_RETURNED_TO_CREATED'
                    """
                ),
                {"document_id": int(document_id)},
            ).fetchone()
            assert audit is not None
            assert audit[1] == "READY_FOR_SIGNATURE"
            assert audit[2] == "CREATED"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_return_requires_reason(client, oo_lifecycle_headers, seed):
    workspace_id, document_id, promoted = create_promoted_document(client, oo_lifecycle_headers, seed)
    try:
        doc_version = promoted["document"]["document"]["version"]
        assign = assign_signing_authority(
            client, oo_lifecycle_headers, document_id, reference="reason-signer", expected_version=doc_version
        )
        ready = mark_ready_for_signature(
            client, oo_lifecycle_headers, document_id, expected_version=assign.json()["document"]["version"]
        )
        ready_version = ready.json()["document"]["document"]["version"]
        resp = client.post(
            f"{DOCUMENTS_BASE}/{document_id}/return-to-created",
            json={"reason": "   ", "expected_version": ready_version},
            headers=oo_lifecycle_headers,
        )
        assert resp.status_code == 422
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_return_from_created_is_idempotent_with_current_version(client, oo_lifecycle_headers, seed):
    workspace_id, document_id, promoted = create_promoted_document(client, oo_lifecycle_headers, seed)
    try:
        current_version = promoted["document"]["document"]["version"]
        returned = return_to_created(
            client,
            oo_lifecycle_headers,
            document_id,
            reason="Not applicable",
            expected_version=current_version,
        )
        assert returned.status_code == 200
        assert returned.json()["idempotent_replay"] is True
        assert returned.json()["document"]["document"]["status"] == "CREATED"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_workspace_remains_frozen_after_return(client, oo_lifecycle_headers, seed):
    workspace_id, document_id, promoted = create_promoted_document(client, oo_lifecycle_headers, seed)
    try:
        doc_version = promoted["document"]["document"]["version"]
        assign = assign_signing_authority(
            client, oo_lifecycle_headers, document_id, reference="frozen-signer", expected_version=doc_version
        )
        ready = mark_ready_for_signature(
            client, oo_lifecycle_headers, document_id, expected_version=assign.json()["document"]["version"]
        )
        _return_to_created(
            client,
            oo_lifecycle_headers,
            document_id,
            reason="Return without unfreeze",
            expected_version=ready.json()["document"]["document"]["version"],
        )
        with engine.begin() as conn:
            stage = conn.execute(
                text(
                    """
                    SELECT stage FROM public.operational_order_draft_workspaces
                    WHERE workspace_id = :workspace_id
                    """
                ),
                {"workspace_id": int(workspace_id)},
            ).scalar()
            version_number = conn.execute(
                text(
                    """
                    SELECT version_number FROM public.operational_order_document_versions
                    WHERE document_id = :document_id AND is_current = TRUE
                    """
                ),
                {"document_id": int(document_id)},
            ).scalar()
            assert stage == "DOCUMENT_PROMOTED"
            assert int(version_number) == 1
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)
