# tests/operational_orders/test_lifecycle_readiness.py
"""Lifecycle readiness tests (OO-IMP-004)."""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.operational_orders.conftest import _grant_user_permission, cleanup_workspace, revoke_user_permission
from tests.operational_orders.test_helpers import (
    DOCUMENTS_BASE,
    assign_signing_authority,
    create_promoted_document,
    mark_ready_for_signature,
)

pytestmark = pytest.mark.usefixtures("_require_oo_lifecycle_schema_fixture")


def test_created_document_passes_readiness_with_authority(client, oo_lifecycle_headers, seed):
    workspace_id, document_id, promoted = create_promoted_document(client, oo_lifecycle_headers, seed)
    try:
        assign = assign_signing_authority(
            client,
            oo_lifecycle_headers,
            document_id,
            reference="signer-001",
            expected_version=promoted["document"]["document"]["version"],
        )
        assert assign.status_code == 200, assign.text

        validate = client.post(
            f"{DOCUMENTS_BASE}/{document_id}/validate-ready-for-signature",
            json={"expected_version": assign.json()["document"]["version"]},
            headers=oo_lifecycle_headers,
        )
        assert validate.status_code == 200, validate.text
        assert validate.json()["readiness_validation"]["is_valid"] is True
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_mark_ready_for_signature_transition(client, oo_lifecycle_headers, seed):
    workspace_id, document_id, promoted = create_promoted_document(client, oo_lifecycle_headers, seed)
    try:
        doc_version = promoted["document"]["document"]["version"]
        assign = assign_signing_authority(
            client,
            oo_lifecycle_headers,
            document_id,
            reference="signer-002",
            expected_version=doc_version,
        )
        doc_version = assign.json()["document"]["version"]
        ready = mark_ready_for_signature(
            client,
            oo_lifecycle_headers,
            document_id,
            expected_version=doc_version,
        )
        assert ready.status_code == 200, ready.text
        payload = ready.json()
        assert payload["document"]["document"]["status"] == "READY_FOR_SIGNATURE"
        assert payload["document"]["document"]["version"] == doc_version + 1
        assert payload["document"]["current_version"]["version_number"] == 1
        assert payload["idempotent_replay"] is False

        with engine.begin() as conn:
            audit_count = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM public.operational_order_lifecycle_audit
                    WHERE document_id = :document_id
                      AND action = 'DOCUMENT_READY_FOR_SIGNATURE'
                    """
                ),
                {"document_id": int(document_id)},
            ).scalar()
            assert int(audit_count) == 1
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_repeated_ready_call_is_idempotent(client, oo_lifecycle_headers, seed):
    workspace_id, document_id, promoted = create_promoted_document(client, oo_lifecycle_headers, seed)
    try:
        doc_version = promoted["document"]["document"]["version"]
        assign = assign_signing_authority(
            client, oo_lifecycle_headers, document_id, reference="signer-003", expected_version=doc_version
        )
        doc_version = assign.json()["document"]["version"]
        first = mark_ready_for_signature(
            client, oo_lifecycle_headers, document_id, expected_version=doc_version
        )
        second = mark_ready_for_signature(
            client,
            oo_lifecycle_headers,
            document_id,
            expected_version=first.json()["document"]["document"]["version"],
        )
        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["idempotent_replay"] is True
        assert (
            first.json()["document"]["document"]["version"]
            == second.json()["document"]["document"]["version"]
        )
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_stale_expected_document_version_returns_409(client, oo_lifecycle_headers, seed):
    workspace_id, document_id, promoted = create_promoted_document(client, oo_lifecycle_headers, seed)
    try:
        doc_version = promoted["document"]["document"]["version"]
        assign_signing_authority(
            client, oo_lifecycle_headers, document_id, reference="signer-004", expected_version=doc_version
        )
        ready = mark_ready_for_signature(
            client, oo_lifecycle_headers, document_id, expected_version=doc_version
        )
        assert ready.status_code == 409
        assert ready.json()["detail"]["code"] == "OO_DOCUMENT_VERSION_CONFLICT"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_missing_authority_blocks_ready(client, oo_lifecycle_headers, seed):
    workspace_id, document_id, promoted = create_promoted_document(client, oo_lifecycle_headers, seed)
    try:
        ready = mark_ready_for_signature(
            client,
            oo_lifecycle_headers,
            document_id,
            expected_version=promoted["document"]["document"]["version"],
        )
        assert ready.status_code == 409
        assert ready.json()["detail"]["code"] == "OO_VALIDATION_BLOCKED"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_workspace_remains_document_promoted(client, oo_lifecycle_headers, seed):
    workspace_id, document_id, promoted = create_promoted_document(client, oo_lifecycle_headers, seed)
    try:
        doc_version = promoted["document"]["document"]["version"]
        assign = assign_signing_authority(
            client, oo_lifecycle_headers, document_id, reference="signer-005", expected_version=doc_version
        )
        mark_ready_for_signature(
            client,
            oo_lifecycle_headers,
            document_id,
            expected_version=assign.json()["document"]["version"],
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
            assert stage == "DOCUMENT_PROMOTED"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_read_only_user_cannot_mark_ready(client, oo_editorial_headers, seed):
    workspace_id, document_id, promoted = create_promoted_document(client, oo_editorial_headers, seed)
    try:
        with engine.begin() as conn:
            _grant_user_permission(conn, int(seed["executor_user_id"]), "OPERATIONAL_ORDERS_ASSIGN_SIGNING_AUTHORITY")
            _grant_user_permission(conn, int(seed["executor_user_id"]), "OPERATIONAL_ORDERS_SIGNATURE_READINESS_READ")
        doc_version = promoted["document"]["document"]["version"]
        assign_signing_authority(
            client, oo_editorial_headers, document_id, reference="signer-006", expected_version=doc_version
        )
        ready = mark_ready_for_signature(
            client,
            oo_editorial_headers,
            document_id,
            expected_version=doc_version,
        )
        assert ready.status_code == 403
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_privileged_user_can_mark_ready(client, oo_intake_headers, oo_lifecycle_headers, seed):
    workspace_id, document_id, promoted = create_promoted_document(client, oo_lifecycle_headers, seed)
    try:
        doc_version = promoted["document"]["document"]["version"]
        assign = assign_signing_authority(
            client, oo_lifecycle_headers, document_id, reference="signer-007", expected_version=doc_version
        )
        assert assign.status_code == 200, assign.text
        ready = mark_ready_for_signature(
            client,
            oo_intake_headers,
            document_id,
            expected_version=assign.json()["document"]["version"],
        )
        assert ready.status_code == 200, ready.text
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)
