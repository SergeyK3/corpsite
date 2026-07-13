# tests/operational_orders/test_oo_imp_005c_signing_command.py
"""Signing command tests (OO-IMP-005C)."""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.db.models.operational_orders import DOCUMENT_STATUS_SIGNED, WORKSPACE_STAGE_DOCUMENT_PROMOTED
from tests.conftest import auth_headers
from tests.operational_orders.conftest import (
    _grant_user_permission,
    cleanup_workspace,
    revoke_user_access_grants,
    revoke_user_permission,
)
from tests.operational_orders.test_helpers import (
    DOCUMENTS_BASE,
    assign_signing_authority,
    create_promoted_document,
    create_ready_to_sign_document,
    mark_ready_for_signature,
    return_to_created,
    sign_document,
)

pytestmark = pytest.mark.usefixtures("_require_oo_signing_schema_fixture")


def _audit_count(conn, document_id: int, action: str) -> int:
    return int(
        conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.operational_order_lifecycle_audit
                WHERE document_id = :document_id AND action = :action
                """
            ),
            {"document_id": int(document_id), "action": action},
        ).scalar_one()
    )


def test_sign_success_creates_attestation_and_audit(client, oo_signing_headers, seed):
    workspace_id, document_id, ready = create_ready_to_sign_document(client, oo_signing_headers, seed)
    key = f"sign-success-{uuid4().hex[:8]}"
    try:
        doc_version = ready["document"]["document"]["version"]
        resp = sign_document(
            client,
            oo_signing_headers,
            document_id,
            idempotency_key=key,
            expected_version=doc_version,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["document"]["document"]["status"] == DOCUMENT_STATUS_SIGNED
        assert body["document"]["document"]["signed_by_user_id"] == int(seed["executor_user_id"])
        assert body["document"]["document"]["signed_at"] is not None
        assert body["signing_attestation"]["privileged_override"] is False
        assert body["idempotent_replay"] is False

        with engine.begin() as conn:
            assert _audit_count(conn, document_id, "DOCUMENT_SIGNED") == 1
            stage = conn.execute(
                text(
                    """
                    SELECT stage FROM public.operational_order_draft_workspaces
                    WHERE workspace_id = :workspace_id
                    """
                ),
                {"workspace_id": int(workspace_id)},
            ).scalar_one()
            assert stage == WORKSPACE_STAGE_DOCUMENT_PROMOTED
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_sign_exact_replay_is_idempotent(client, oo_signing_headers, seed):
    workspace_id, document_id, ready = create_ready_to_sign_document(client, oo_signing_headers, seed)
    key = f"sign-replay-{uuid4().hex[:8]}"
    try:
        doc_version = ready["document"]["document"]["version"]
        first = sign_document(
            client,
            oo_signing_headers,
            document_id,
            idempotency_key=key,
            expected_version=doc_version,
        )
        assert first.status_code == 200
        signed_at = first.json()["document"]["document"]["signed_at"]
        second = sign_document(
            client,
            oo_signing_headers,
            document_id,
            idempotency_key=key,
            expected_version=first.json()["document"]["document"]["version"],
        )
        assert second.status_code == 200
        assert second.json()["idempotent_replay"] is True
        assert second.json()["document"]["document"]["signed_at"] == signed_at
        with engine.begin() as conn:
            assert _audit_count(conn, document_id, "DOCUMENT_SIGNED") == 1
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_sign_idempotency_conflict_on_different_payload(client, oo_signing_headers, seed):
    workspace_id, document_id, ready = create_ready_to_sign_document(client, oo_signing_headers, seed)
    key = f"sign-conflict-payload-{uuid4().hex[:8]}"
    try:
        doc_version = ready["document"]["document"]["version"]
        first = sign_document(
            client,
            oo_signing_headers,
            document_id,
            idempotency_key=key,
            expected_version=doc_version,
        )
        assert first.status_code == 200
        conflict = sign_document(
            client,
            oo_signing_headers,
            document_id,
            idempotency_key=key,
            override_reason="different",
            expected_version=first.json()["document"]["document"]["version"],
        )
        assert conflict.status_code == 409
        assert conflict.json()["detail"]["code"] == "OO_SIGN_IDEMPOTENCY_CONFLICT"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_intake_read_user_cannot_sign(client, oo_signing_headers, seed, monkeypatch):
    workspace_id, document_id, ready = create_ready_to_sign_document(client, oo_signing_headers, seed)
    intake_user_id = int(seed["initiator_user_id"])
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", "")
    with engine.begin() as conn:
        _grant_user_permission(conn, intake_user_id, "OPERATIONAL_ORDERS_INTAKE_READ")
    headers = auth_headers(intake_user_id)
    try:
        resp = sign_document(
            client,
            headers,
            document_id,
            idempotency_key=f"deny-read-{uuid4().hex[:8]}",
            expected_version=ready["document"]["document"]["version"],
        )
        assert resp.status_code == 403
    finally:
        with engine.begin() as conn:
            revoke_user_access_grants(conn, intake_user_id)
            cleanup_workspace(conn, workspace_id)


def test_sign_permission_without_authority_match_forbidden(client, oo_signing_headers, seed):
    workspace_id, document_id, promoted = create_promoted_document(client, oo_signing_headers, seed)
    try:
        doc_version = promoted["document"]["document"]["version"]
        assign = assign_signing_authority(
            client,
            oo_signing_headers,
            document_id,
            reference="not-the-executor",
            expected_version=doc_version,
        )
        assert assign.status_code == 200
        ready = mark_ready_for_signature(
            client,
            oo_signing_headers,
            document_id,
            expected_version=assign.json()["document"]["version"],
        )
        assert ready.status_code == 200
        resp = sign_document(
            client,
            oo_signing_headers,
            document_id,
            idempotency_key=f"mismatch-{uuid4().hex[:8]}",
            expected_version=ready.json()["document"]["document"]["version"],
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["code"] == "OO_SIGN_AUTHORITY_MISMATCH"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_privileged_override_requires_reason(client, oo_signing_headers, seed, monkeypatch):
    workspace_id, document_id, ready = create_ready_to_sign_document(client, oo_signing_headers, seed)
    privileged_id = int(seed["executor_user_id"])
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(privileged_id))
    try:
        with engine.begin() as conn:
            revoke_user_permission(conn, privileged_id, "OPERATIONAL_ORDERS_SIGN")
        headers = auth_headers(privileged_id)
        resp = sign_document(
            client,
            headers,
            document_id,
            idempotency_key=f"override-no-reason-{uuid4().hex[:8]}",
            expected_version=ready["document"]["document"]["version"],
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["code"] == "OO_SIGN_OVERRIDE_REASON_REQUIRED"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_privileged_override_signs_with_reason(client, oo_signing_headers, seed, monkeypatch):
    workspace_id, document_id, ready = create_ready_to_sign_document(
        client,
        oo_signing_headers,
        seed,
        authority_reference="someone-else",
    )
    privileged_id = int(seed["executor_user_id"])
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(privileged_id))
    try:
        with engine.begin() as conn:
            revoke_user_permission(conn, privileged_id, "OPERATIONAL_ORDERS_SIGN")
        headers = auth_headers(privileged_id)
        resp = sign_document(
            client,
            headers,
            document_id,
            idempotency_key=f"override-ok-{uuid4().hex[:8]}",
            override_reason="Emergency paper attestation recorded.",
            expected_version=ready["document"]["document"]["version"],
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["signing_attestation"]["privileged_override"] is True
        assert resp.json()["signing_attestation"]["override_reason"] == "Emergency paper attestation recorded."
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_created_document_cannot_be_signed(client, oo_signing_headers, seed):
    workspace_id, document_id, promoted = create_promoted_document(client, oo_signing_headers, seed)
    try:
        doc_version = promoted["document"]["document"]["version"]
        assign_signing_authority(
            client,
            oo_signing_headers,
            document_id,
            reference=str(seed["executor_user_id"]),
            expected_version=doc_version,
        )
        resp = sign_document(
            client,
            oo_signing_headers,
            document_id,
            idempotency_key=f"created-{uuid4().hex[:8]}",
            expected_version=doc_version,
        )
        assert resp.status_code == 409
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_missing_authority_blocks_signing(client, oo_signing_headers, seed):
    workspace_id, document_id, promoted = create_promoted_document(client, oo_signing_headers, seed)
    try:
        ready = mark_ready_for_signature(
            client,
            oo_signing_headers,
            document_id,
            expected_version=promoted["document"]["document"]["version"],
        )
        assert ready.status_code == 409
        resp = sign_document(
            client,
            oo_signing_headers,
            document_id,
            idempotency_key=f"no-authority-{uuid4().hex[:8]}",
            expected_version=promoted["document"]["document"]["version"],
        )
        assert resp.status_code == 409
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_already_signed_without_matching_idempotency_conflicts(client, oo_signing_headers, seed):
    workspace_id, document_id, ready = create_ready_to_sign_document(client, oo_signing_headers, seed)
    try:
        first = sign_document(
            client,
            oo_signing_headers,
            document_id,
            idempotency_key=f"signed-once-{uuid4().hex[:8]}",
            expected_version=ready["document"]["document"]["version"],
        )
        assert first.status_code == 200
        second = sign_document(
            client,
            oo_signing_headers,
            document_id,
            idempotency_key=f"different-key-{uuid4().hex[:8]}",
            expected_version=first.json()["document"]["document"]["version"],
        )
        assert second.status_code == 409
        assert second.json()["detail"]["code"] == "OO_DOCUMENT_ALREADY_SIGNED"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_mark_ready_and_return_still_work_after_signing_schema(client, oo_signing_headers, seed):
    workspace_id, document_id, ready = create_ready_to_sign_document(client, oo_signing_headers, seed)
    try:
        returned = return_to_created(
            client,
            oo_signing_headers,
            document_id,
            reason="Need revision before signing",
            expected_version=ready["document"]["document"]["version"],
        )
        assert returned.status_code == 200
        assert returned.json()["document"]["document"]["status"] == "CREATED"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_sign_idempotency_conflict_on_different_document(client, oo_signing_headers, seed):
    ws1, doc1, ready1 = create_ready_to_sign_document(client, oo_signing_headers, seed)
    ws2, doc2, ready2 = create_ready_to_sign_document(client, oo_signing_headers, seed)
    key = f"cross-doc-{uuid4().hex[:8]}"
    try:
        first = sign_document(
            client,
            oo_signing_headers,
            doc1,
            idempotency_key=key,
            expected_version=ready1["document"]["document"]["version"],
        )
        assert first.status_code == 200
        conflict = sign_document(
            client,
            oo_signing_headers,
            doc2,
            idempotency_key=key,
            expected_version=ready2["document"]["document"]["version"],
        )
        assert conflict.status_code == 409
        assert conflict.json()["detail"]["code"] == "OO_SIGN_IDEMPOTENCY_CONFLICT"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, ws1)
            cleanup_workspace(conn, ws2)


def test_authority_without_sign_permission_forbidden(client, oo_signing_headers, seed, monkeypatch):
    workspace_id, document_id, ready = create_ready_to_sign_document(
        client,
        oo_signing_headers,
        seed,
        authority_reference=str(seed["executor_user_id"]),
    )
    actor_id = int(seed["executor_user_id"])
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", "")
    try:
        with engine.begin() as conn:
            revoke_user_permission(conn, actor_id, "OPERATIONAL_ORDERS_SIGN")
        headers = auth_headers(actor_id)
        resp = sign_document(
            client,
            headers,
            document_id,
            idempotency_key=f"no-sign-perm-{uuid4().hex[:8]}",
            expected_version=ready["document"]["document"]["version"],
        )
        assert resp.status_code == 403
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


@pytest.mark.parametrize(
    ("blocked_status", "extra_updates"),
    [
        ("REGISTERED", {"signed_at": "NOW()", "registration_number": "'OO-TEST-1'", "registration_year": "2026", "registration_date": "'2026-01-01'", "registered_at": "NOW()"}),
        ("PUBLISHED", {"published_at": "NOW()", "published_by_user_id": ":actor_id"}),
        ("VOIDED", {}),
    ],
)
def test_non_ready_status_cannot_be_signed(client, oo_signing_headers, seed, blocked_status, extra_updates):
    workspace_id, document_id, ready = create_ready_to_sign_document(client, oo_signing_headers, seed)
    actor_id = int(seed["executor_user_id"])
    set_parts = ["status = :status"] + [f"{col} = {expr}" for col, expr in extra_updates.items()]
    sql = f"UPDATE public.operational_order_documents SET {', '.join(set_parts)} WHERE id = :document_id"
    params = {"status": blocked_status, "document_id": int(document_id), "actor_id": actor_id}
    try:
        with engine.begin() as conn:
            conn.execute(text(sql), params)
        resp = sign_document(
            client,
            oo_signing_headers,
            document_id,
            idempotency_key=f"blocked-{blocked_status}-{uuid4().hex[:8]}",
            expected_version=ready["document"]["document"]["version"],
        )
        assert resp.status_code == 409
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_sign_preserves_immutable_document_version(client, oo_signing_headers, seed):
    workspace_id, document_id, ready = create_ready_to_sign_document(client, oo_signing_headers, seed)
    try:
        with engine.begin() as conn:
            version_count_before = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM public.operational_order_document_versions
                    WHERE document_id = :document_id
                    """
                ),
                {"document_id": int(document_id)},
            ).scalar_one()
            current_version = conn.execute(
                text(
                    """
                    SELECT id, snapshot_fingerprint
                    FROM public.operational_order_document_versions
                    WHERE document_id = :document_id AND is_current = TRUE
                    LIMIT 1
                    """
                ),
                {"document_id": int(document_id)},
            ).mappings().one()
        resp = sign_document(
            client,
            oo_signing_headers,
            document_id,
            idempotency_key=f"version-stable-{uuid4().hex[:8]}",
            expected_version=ready["document"]["document"]["version"],
        )
        assert resp.status_code == 200
        with engine.begin() as conn:
            version_count_after = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM public.operational_order_document_versions
                    WHERE document_id = :document_id
                    """
                ),
                {"document_id": int(document_id)},
            ).scalar_one()
            current_version_after = conn.execute(
                text(
                    """
                    SELECT id, snapshot_fingerprint
                    FROM public.operational_order_document_versions
                    WHERE document_id = :document_id AND is_current = TRUE
                    LIMIT 1
                    """
                ),
                {"document_id": int(document_id)},
            ).mappings().one()
        assert version_count_after == version_count_before
        assert current_version_after["id"] == current_version["id"]
        assert current_version_after["snapshot_fingerprint"] == current_version["snapshot_fingerprint"]
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_attestation_snapshot_survives_authority_mutation(client, oo_signing_headers, seed):
    workspace_id, document_id, ready = create_ready_to_sign_document(client, oo_signing_headers, seed)
    try:
        resp = sign_document(
            client,
            oo_signing_headers,
            document_id,
            idempotency_key=f"snapshot-{uuid4().hex[:8]}",
            expected_version=ready["document"]["document"]["version"],
        )
        assert resp.status_code == 200
        snapshot_name = resp.json()["signing_attestation"]["assigned_authority_display_name"]
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE public.operational_order_signing_authority
                    SET authority_display_name = :name
                    WHERE document_id = :document_id
                    """
                ),
                {"name": "Mutated After Signing", "document_id": int(document_id)},
            )
            row = conn.execute(
                text(
                    """
                    SELECT assigned_authority_display_name
                    FROM public.operational_order_signing_attestations
                    WHERE document_id = :document_id
                    """
                ),
                {"document_id": int(document_id)},
            ).scalar_one()
        assert row == snapshot_name
        assert row != "Mutated After Signing"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_concurrent_sign_requests_do_not_double_sign(client, oo_signing_headers, seed):
    from concurrent.futures import ThreadPoolExecutor

    workspace_id, document_id, ready = create_ready_to_sign_document(client, oo_signing_headers, seed)
    key = f"concurrent-{uuid4().hex[:8]}"
    doc_version = ready["document"]["document"]["version"]

    def _call():
        return sign_document(
            client,
            oo_signing_headers,
            document_id,
            idempotency_key=key,
            expected_version=doc_version,
        )

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: _call(), range(2)))
        status_codes = sorted(r.status_code for r in results)
        assert status_codes in ([200, 200], [200, 409])
        success = next(r for r in results if r.status_code == 200)
        assert success.json()["document"]["document"]["status"] == DOCUMENT_STATUS_SIGNED
        with engine.begin() as conn:
            assert _audit_count(conn, document_id, "DOCUMENT_SIGNED") == 1
            attestation_count = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM public.operational_order_signing_attestations
                    WHERE document_id = :document_id
                    """
                ),
                {"document_id": int(document_id)},
            ).scalar_one()
        assert attestation_count == 1
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


# --- OO-IMP-005C-R1 verification tests ---


def _document_signing_state(conn, document_id: int) -> dict:
    return dict(
        conn.execute(
            text(
                """
                SELECT status, signed_at, signed_by_user_id
                FROM public.operational_order_documents
                WHERE id = :document_id
                """
            ),
            {"document_id": int(document_id)},
        ).mappings().one()
    )


def test_sign_transaction_rolls_back_when_audit_insert_fails(
    client, oo_signing_headers, seed, monkeypatch
):
    from app.operational_orders.services import lifecycle_service as lifecycle_svc

    workspace_id, document_id, ready = create_ready_to_sign_document(client, oo_signing_headers, seed)
    original_audit = lifecycle_svc._append_lifecycle_audit

    def _fail_signed_audit(conn, **kwargs):
        if kwargs.get("action") == "DOCUMENT_SIGNED":
            raise RuntimeError("injected audit failure")
        return original_audit(conn, **kwargs)

    monkeypatch.setattr(lifecycle_svc, "_append_lifecycle_audit", _fail_signed_audit)
    actor = {"user_id": int(seed["executor_user_id"])}
    try:
        with pytest.raises(RuntimeError, match="injected audit failure"):
            lifecycle_svc.sign_document(
                document_id=int(document_id),
                actor_user=actor,
                idempotency_key=f"audit-fail-{uuid4().hex[:8]}",
                expected_document_version=ready["document"]["document"]["version"],
            )
        with engine.begin() as conn:
            state = _document_signing_state(conn, document_id)
            assert state["status"] == "READY_FOR_SIGNATURE"
            assert state["signed_at"] is None
            assert state["signed_by_user_id"] is None
            assert (
                conn.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM public.operational_order_signing_attestations
                        WHERE document_id = :document_id
                        """
                    ),
                    {"document_id": int(document_id)},
                ).scalar_one()
                == 0
            )
            assert (
                conn.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM public.operational_order_lifecycle_command_idempotency
                        WHERE document_id = :document_id
                        """
                    ),
                    {"document_id": int(document_id)},
                ).scalar_one()
                == 0
            )
            assert _audit_count(conn, document_id, "DOCUMENT_SIGNED") == 0
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_exact_replay_rejects_corrupted_document_state(client, oo_signing_headers, seed):
    workspace_id, document_id, ready = create_ready_to_sign_document(client, oo_signing_headers, seed)
    key = f"corrupt-replay-{uuid4().hex[:8]}"
    try:
        first = sign_document(
            client,
            oo_signing_headers,
            document_id,
            idempotency_key=key,
            expected_version=ready["document"]["document"]["version"],
        )
        assert first.status_code == 200
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE public.operational_order_documents
                    SET status = 'READY_FOR_SIGNATURE',
                        signed_at = NULL,
                        signed_by_user_id = NULL
                    WHERE id = :document_id
                    """
                ),
                {"document_id": int(document_id)},
            )
        replay = sign_document(
            client,
            oo_signing_headers,
            document_id,
            idempotency_key=key,
            expected_version=ready["document"]["document"]["version"],
        )
        assert replay.status_code == 409
        assert replay.json()["detail"]["code"] == "OO_SIGN_IDEMPOTENCY_CONFLICT"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_signing_uses_active_authority_not_header_mirror(client, oo_signing_headers, seed):
    workspace_id, document_id, ready = create_ready_to_sign_document(client, oo_signing_headers, seed)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE public.operational_order_documents
                    SET signatory_display_name = 'Header Mirror Should Not Win',
                        signatory_party_reference = 'fake-reference',
                        signatory_position = 'Fake Position'
                    WHERE id = :document_id
                    """
                ),
                {"document_id": int(document_id)},
            )
        resp = sign_document(
            client,
            oo_signing_headers,
            document_id,
            idempotency_key=f"authority-source-{uuid4().hex[:8]}",
            expected_version=ready["document"]["document"]["version"],
        )
        assert resp.status_code == 200
        attestation = resp.json()["signing_attestation"]
        assert attestation["assigned_authority_display_name"] == "Signer"
        assert attestation["assigned_authority_party_reference"] == str(seed["executor_user_id"])
        assert attestation["assigned_authority_display_name"] != "Header Mirror Should Not Win"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_permission_migration_upgrade_creates_no_grants():
    from pathlib import Path

    migration_path = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "d4e5f6a7b8c9_oo_imp_005c_signing_command.py"
    )
    source = migration_path.read_text(encoding="utf-8")
    upgrade_source = source.split("def downgrade")[0]
    assert "INSERT INTO public.access_grants" not in upgrade_source
    assert "INSERT INTO public.access_roles" in upgrade_source
    assert "OPERATIONAL_ORDERS_SIGN" in upgrade_source


def test_attestation_table_has_no_update_path_in_service():
    from pathlib import Path

    service_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "operational_orders"
        / "services"
        / "lifecycle_service.py"
    )
    source = service_path.read_text(encoding="utf-8")
    assert "UPDATE public.operational_order_signing_attestations" not in source
    assert "ON CONFLICT" not in source or "operational_order_signing_attestations" not in source
