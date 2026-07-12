# tests/operational_orders/test_oo_imp_004_r1_integrity.py
"""OO-IMP-004-R1 lifecycle integrity review tests."""
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


def _audit_count(conn, document_id: int, *, action: str | None = None) -> int:
    if action is None:
        row = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.operational_order_lifecycle_audit
                WHERE document_id = :document_id
                """
            ),
            {"document_id": int(document_id)},
        ).scalar()
    else:
        row = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.operational_order_lifecycle_audit
                WHERE document_id = :document_id AND action = :action
                """
            ),
            {"document_id": int(document_id), "action": action},
        ).scalar()
    return int(row or 0)


def _authority_count(conn, document_id: int) -> int:
    return int(
        conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.operational_order_signing_authority
                WHERE document_id = :document_id
                """
            ),
            {"document_id": int(document_id)},
        ).scalar()
        or 0
    )


def test_idempotent_ready_does_not_add_audit_or_bump_version(client, oo_lifecycle_headers, seed):
    workspace_id, document_id, promoted = create_promoted_document(client, oo_lifecycle_headers, seed)
    try:
        doc_version = promoted["document"]["document"]["version"]
        assign = assign_signing_authority(
            client, oo_lifecycle_headers, document_id, reference="r1-ready", expected_version=doc_version
        )
        doc_version = assign.json()["document"]["version"]
        first = mark_ready_for_signature(client, oo_lifecycle_headers, document_id, expected_version=doc_version)
        assert first.status_code == 200
        ready_version = first.json()["document"]["document"]["version"]

        with engine.begin() as conn:
            before_audit = _audit_count(conn, document_id)

        second = mark_ready_for_signature(
            client, oo_lifecycle_headers, document_id, expected_version=ready_version
        )
        assert second.status_code == 200
        assert second.json()["idempotent_replay"] is True
        assert second.json()["document"]["document"]["version"] == ready_version

        with engine.begin() as conn:
            assert _audit_count(conn, document_id) == before_audit
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_stale_ready_on_ready_document_returns_409_without_audit(client, oo_lifecycle_headers, seed):
    workspace_id, document_id, promoted = create_promoted_document(client, oo_lifecycle_headers, seed)
    try:
        doc_version = promoted["document"]["document"]["version"]
        assign = assign_signing_authority(
            client, oo_lifecycle_headers, document_id, reference="r1-stale-ready", expected_version=doc_version
        )
        ready = mark_ready_for_signature(
            client, oo_lifecycle_headers, document_id, expected_version=assign.json()["document"]["version"]
        )
        assert ready.status_code == 200
        stale_version = doc_version

        with engine.begin() as conn:
            before_audit = _audit_count(conn, document_id)

        stale = mark_ready_for_signature(
            client, oo_lifecycle_headers, document_id, expected_version=stale_version
        )
        assert stale.status_code == 409
        assert stale.json()["detail"]["code"] == "OO_DOCUMENT_VERSION_CONFLICT"

        with engine.begin() as conn:
            assert _audit_count(conn, document_id) == before_audit
            status = conn.execute(
                text("SELECT status FROM public.operational_order_documents WHERE id = :id"),
                {"id": int(document_id)},
            ).scalar()
            assert status == "READY_FOR_SIGNATURE"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_idempotent_assign_does_not_add_authority_row_or_audit(client, oo_lifecycle_headers, seed):
    workspace_id, document_id, promoted = create_promoted_document(client, oo_lifecycle_headers, seed)
    try:
        doc_version = promoted["document"]["document"]["version"]
        first = assign_signing_authority(
            client, oo_lifecycle_headers, document_id, reference="r1-assign", expected_version=doc_version
        )
        assert first.status_code == 200
        current_version = first.json()["document"]["version"]

        with engine.begin() as conn:
            before_rows = _authority_count(conn, document_id)
            before_audit = _audit_count(conn, document_id)

        second = assign_signing_authority(
            client,
            oo_lifecycle_headers,
            document_id,
            reference="r1-assign",
            expected_version=current_version,
        )
        assert second.status_code == 200
        assert second.json()["idempotent_replay"] is True

        with engine.begin() as conn:
            assert _authority_count(conn, document_id) == before_rows
            assert _audit_count(conn, document_id) == before_audit
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_stale_assign_returns_409_without_mutation(client, oo_lifecycle_headers, seed):
    workspace_id, document_id, promoted = create_promoted_document(client, oo_lifecycle_headers, seed)
    try:
        doc_version = promoted["document"]["document"]["version"]
        first = assign_signing_authority(
            client, oo_lifecycle_headers, document_id, reference="r1-stale-assign", expected_version=doc_version
        )
        assert first.status_code == 200

        with engine.begin() as conn:
            before_rows = _authority_count(conn, document_id)
            before_audit = _audit_count(conn, document_id)

        stale = assign_signing_authority(
            client,
            oo_lifecycle_headers,
            document_id,
            reference="r1-other",
            expected_version=doc_version,
        )
        assert stale.status_code == 409

        with engine.begin() as conn:
            assert _authority_count(conn, document_id) == before_rows
            assert _audit_count(conn, document_id) == before_audit
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_validate_endpoint_does_not_create_audit(client, oo_lifecycle_headers, seed):
    workspace_id, document_id, promoted = create_promoted_document(client, oo_lifecycle_headers, seed)
    try:
        with engine.begin() as conn:
            before = _audit_count(conn, document_id)

        resp = client.post(
            f"{DOCUMENTS_BASE}/{document_id}/validate-ready-for-signature",
            json={"expected_version": promoted["document"]["document"]["version"]},
            headers=oo_lifecycle_headers,
        )
        assert resp.status_code == 200

        with engine.begin() as conn:
            assert _audit_count(conn, document_id) == before
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_failed_mark_ready_does_not_create_audit(client, oo_lifecycle_headers, seed):
    workspace_id, document_id, promoted = create_promoted_document(client, oo_lifecycle_headers, seed)
    try:
        with engine.begin() as conn:
            before = _audit_count(conn, document_id)

        ready = mark_ready_for_signature(
            client,
            oo_lifecycle_headers,
            document_id,
            expected_version=promoted["document"]["document"]["version"],
        )
        assert ready.status_code == 409

        with engine.begin() as conn:
            assert _audit_count(conn, document_id) == before
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_return_clears_readiness_projection_fields(client, oo_lifecycle_headers, seed):
    workspace_id, document_id, promoted = create_promoted_document(client, oo_lifecycle_headers, seed)
    try:
        doc_version = promoted["document"]["document"]["version"]
        assign = assign_signing_authority(
            client, oo_lifecycle_headers, document_id, reference="r1-return", expected_version=doc_version
        )
        ready = mark_ready_for_signature(
            client, oo_lifecycle_headers, document_id, expected_version=assign.json()["document"]["version"]
        )
        ready_version = ready.json()["document"]["document"]["version"]
        assert ready.json()["document"]["document"]["ready_for_signature_at"] is not None

        returned = return_to_created(
            client,
            oo_lifecycle_headers,
            document_id,
            reason="Queue correction",
            expected_version=ready_version,
        )
        assert returned.status_code == 200
        doc = returned.json()["document"]["document"]
        assert doc["status"] == "CREATED"
        assert doc["ready_for_signature_at"] is None
        assert doc["ready_for_signature_by_user_id"] is None

        with engine.begin() as conn:
            returned_audit = conn.execute(
                text(
                    """
                    SELECT action, reason, document_version_before, document_version_after
                    FROM public.operational_order_lifecycle_audit
                    WHERE document_id = :document_id AND action = 'DOCUMENT_RETURNED_TO_CREATED'
                    """
                ),
                {"document_id": int(document_id)},
            ).fetchone()
            assert returned_audit is not None
            assert returned_audit[1] == "Queue correction"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_return_from_created_requires_current_version(client, oo_lifecycle_headers, seed):
    workspace_id, document_id, promoted = create_promoted_document(client, oo_lifecycle_headers, seed)
    try:
        initial_version = promoted["document"]["document"]["version"]
        assign = assign_signing_authority(
            client,
            oo_lifecycle_headers,
            document_id,
            reference="r1-return-version",
            expected_version=initial_version,
        )
        current_version = assign.json()["document"]["version"]
        ok = return_to_created(
            client,
            oo_lifecycle_headers,
            document_id,
            reason="noop",
            expected_version=current_version,
        )
        assert ok.status_code == 200
        assert ok.json()["idempotent_replay"] is True

        stale = return_to_created(
            client,
            oo_lifecycle_headers,
            document_id,
            reason="noop",
            expected_version=initial_version,
        )
        assert stale.status_code == 409
        assert stale.json()["detail"]["code"] == "OO_DOCUMENT_VERSION_CONFLICT"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_mark_ready_preserves_snapshot_and_localizations(client, oo_lifecycle_headers, seed):
    workspace_id, document_id, promoted = create_promoted_document(client, oo_lifecycle_headers, seed)
    try:
        with engine.begin() as conn:
            before_version = conn.execute(
                text(
                    """
                    SELECT snapshot_fingerprint, version_number
                    FROM public.operational_order_document_versions
                    WHERE document_id = :document_id AND is_current = TRUE
                    """
                ),
                {"document_id": int(document_id)},
            ).fetchone()
            before_locs = conn.execute(
                text(
                    """
                    SELECT locale, block_type, sequence, official_text, content_fingerprint
                    FROM public.operational_order_document_localizations
                    WHERE document_version_id IN (
                        SELECT id FROM public.operational_order_document_versions
                        WHERE document_id = :document_id AND is_current = TRUE
                    )
                    ORDER BY locale, block_type, sequence
                    """
                ),
                {"document_id": int(document_id)},
            ).fetchall()

        doc_version = promoted["document"]["document"]["version"]
        assign = assign_signing_authority(
            client, oo_lifecycle_headers, document_id, reference="r1-snap", expected_version=doc_version
        )
        mark_ready_for_signature(
            client, oo_lifecycle_headers, document_id, expected_version=assign.json()["document"]["version"]
        )

        with engine.begin() as conn:
            after_version = conn.execute(
                text(
                    """
                    SELECT snapshot_fingerprint, version_number
                    FROM public.operational_order_document_versions
                    WHERE document_id = :document_id AND is_current = TRUE
                    """
                ),
                {"document_id": int(document_id)},
            ).fetchone()
            after_locs = conn.execute(
                text(
                    """
                    SELECT locale, block_type, sequence, official_text, content_fingerprint
                    FROM public.operational_order_document_localizations
                    WHERE document_version_id IN (
                        SELECT id FROM public.operational_order_document_versions
                        WHERE document_id = :document_id AND is_current = TRUE
                    )
                    ORDER BY locale, block_type, sequence
                    """
                ),
                {"document_id": int(document_id)},
            ).fetchall()
            assert after_version == before_version
            assert after_locs == before_locs
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)
