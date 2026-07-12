# tests/operational_orders/test_signing_authority.py
"""Signing authority assignment tests (OO-IMP-004)."""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.operational_orders.conftest import _grant_user_permission, cleanup_workspace, revoke_user_permission
from tests.operational_orders.test_helpers import (
    DOCUMENTS_BASE,
    assign_signing_authority,
    create_promoted_document,
)

pytestmark = pytest.mark.usefixtures("_require_oo_lifecycle_schema_fixture")


def test_assign_and_retrieve_active_authority(client, oo_lifecycle_headers, seed):
    workspace_id, document_id, promoted = create_promoted_document(client, oo_lifecycle_headers, seed)
    try:
        assign = assign_signing_authority(
            client,
            oo_lifecycle_headers,
            document_id,
            reference="authority-001",
            expected_version=promoted["document"]["document"]["version"],
        )
        assert assign.status_code == 200, assign.text
        assert assign.json()["signing_authority"]["status"] == "ACTIVE"

        get_resp = client.get(
            f"{DOCUMENTS_BASE}/{document_id}/signing-authority",
            headers=oo_lifecycle_headers,
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["signing_authority"]["authority_party_reference"] == "authority-001"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_reassign_supersedes_previous(client, oo_lifecycle_headers, seed):
    workspace_id, document_id, promoted = create_promoted_document(client, oo_lifecycle_headers, seed)
    try:
        doc_version = promoted["document"]["document"]["version"]
        first = assign_signing_authority(
            client, oo_lifecycle_headers, document_id, reference="authority-a", expected_version=doc_version
        )
        second = assign_signing_authority(
            client,
            oo_lifecycle_headers,
            document_id,
            reference="authority-b",
            expected_version=first.json()["document"]["version"],
        )
        assert second.status_code == 200
        assert second.json()["signing_authority"]["authority_party_reference"] == "authority-b"

        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT status, authority_party_reference
                    FROM public.operational_order_signing_authority
                    WHERE document_id = :document_id
                    ORDER BY id
                    """
                ),
                {"document_id": int(document_id)},
            ).fetchall()
            assert len(rows) == 2
            assert rows[0][0] == "SUPERSEDED"
            assert rows[1][0] == "ACTIVE"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_duplicate_identical_assignment_is_idempotent(client, oo_lifecycle_headers, seed):
    workspace_id, document_id, promoted = create_promoted_document(client, oo_lifecycle_headers, seed)
    try:
        doc_version = promoted["document"]["document"]["version"]
        first = assign_signing_authority(
            client, oo_lifecycle_headers, document_id, reference="authority-same", expected_version=doc_version
        )
        second = assign_signing_authority(
            client,
            oo_lifecycle_headers,
            document_id,
            reference="authority-same",
            expected_version=first.json()["document"]["version"],
        )
        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["idempotent_replay"] is True
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_wrong_permission_rejected(client, oo_editorial_headers, seed):
    workspace_id, document_id, promoted = create_promoted_document(client, oo_editorial_headers, seed)
    try:
        assign = assign_signing_authority(
            client,
            oo_editorial_headers,
            document_id,
            reference="authority-denied",
            expected_version=promoted["document"]["document"]["version"],
        )
        assert assign.status_code == 403
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_stale_version_rejected(client, oo_lifecycle_headers, seed):
    workspace_id, document_id, promoted = create_promoted_document(client, oo_lifecycle_headers, seed)
    try:
        first = assign_signing_authority(
            client,
            oo_lifecycle_headers,
            document_id,
            reference="authority-stale",
            expected_version=promoted["document"]["document"]["version"],
        )
        assert first.status_code == 200
        stale = assign_signing_authority(
            client,
            oo_lifecycle_headers,
            document_id,
            reference="authority-new",
            expected_version=promoted["document"]["document"]["version"],
        )
        assert stale.status_code == 409
        assert stale.json()["detail"]["code"] == "OO_DOCUMENT_VERSION_CONFLICT"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_cross_document_authority_substitution_rejected(client, oo_lifecycle_headers, seed):
    ws1, doc1, promoted1 = create_promoted_document(client, oo_lifecycle_headers, seed)
    ws2, doc2, promoted2 = create_promoted_document(client, oo_lifecycle_headers, seed)
    try:
        assign1 = assign_signing_authority(
            client,
            oo_lifecycle_headers,
            doc1,
            reference="doc1-signer",
            expected_version=promoted1["document"]["document"]["version"],
        )
        assert assign1.status_code == 200
        authority_id = assign1.json()["signing_authority"]["id"]

        with engine.begin() as conn:
            tampered = conn.execute(
                text(
                    """
                    UPDATE public.operational_order_signing_authority
                    SET document_id = :other_document_id
                    WHERE id = :authority_id
                    """
                ),
                {"other_document_id": int(doc2), "authority_id": int(authority_id)},
            )
            assert tampered.rowcount == 1

        ready = client.post(
            f"{DOCUMENTS_BASE}/{doc2}/validate-ready-for-signature",
            json={"expected_version": promoted2["document"]["document"]["version"]},
            headers=oo_lifecycle_headers,
        )
        assert ready.status_code == 200
        codes = [issue["code"] for issue in ready.json()["readiness_validation"]["issues"]]
        assert "OO408" in codes or "OO409" in codes
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, ws1)
            cleanup_workspace(conn, ws2)
