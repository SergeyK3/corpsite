# tests/operational_orders/test_promotion.py
"""Promotion and document aggregate tests (OO-IMP-003)."""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.operational_orders.conftest import _grant_user_permission, cleanup_workspace, revoke_user_permission
from tests.operational_orders.test_helpers import (
    BASE,
    DOCUMENTS_BASE,
    WORKSPACES_BASE,
    confirm_block,
    create_editorial_ready_workspace,
    create_ready_workspace,
    promote_workspace,
)

def _force_editorial_ready_stage(conn, workspace_id: int) -> None:
    conn.execute(
        text(
            """
            UPDATE public.operational_order_draft_workspaces
            SET stage = 'EDITORIAL_PACKAGE_READY'
            WHERE workspace_id = :workspace_id
            """
        ),
        {"workspace_id": int(workspace_id)},
    )


pytestmark = pytest.mark.usefixtures("_require_oo_document_schema_fixture")


def test_promotion_creates_document_aggregate(client, oo_editorial_headers, seed):
    author_ref = str(seed["executor_user_id"])
    workspace_id, _ = create_editorial_ready_workspace(
        client, oo_editorial_headers, seed, author_ref=author_ref
    )
    try:
        resp = promote_workspace(client, oo_editorial_headers, workspace_id)
        assert resp.status_code == 200, resp.text
        payload = resp.json()
        assert payload["document"]["document"]["status"] == "CREATED"
        assert payload["document"]["current_version"]["version_number"] == 1
        assert payload["idempotent_replay"] is False

        document_id = payload["document"]["document"]["document_id"]
        loc_resp = client.get(f"{DOCUMENTS_BASE}/{document_id}/localizations", headers=oo_editorial_headers)
        assert loc_resp.status_code == 200
        assert len(loc_resp.json()["items"]) == 4
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_workspace_edit_after_promotion_does_not_change_aggregate(client, oo_editorial_headers, seed):
    author_ref = str(seed["executor_user_id"])
    workspace_id, detail = create_editorial_ready_workspace(
        client, oo_editorial_headers, seed, author_ref=author_ref
    )
    try:
        promoted = promote_workspace(client, oo_editorial_headers, workspace_id)
        assert promoted.json()["workspace_frozen"] is True
        workspace_detail = client.get(f"{BASE}/{workspace_id}", headers=oo_editorial_headers)
        assert workspace_detail.status_code == 200
        assert workspace_detail.json()["workspace"]["stage"] == "DOCUMENT_PROMOTED"

        body_block = next(b for b in detail["blocks"] if b["locale"] == "ru" and b["block_type"] == "BODY")
        patch_resp = client.patch(
            f"{BASE}/{workspace_id}/blocks/{body_block['block_id']}",
            json={"workspace_effective_text": "Changed after promotion body"},
            headers=oo_editorial_headers,
        )
        assert patch_resp.status_code == 409
        assert patch_resp.json()["detail"]["code"] == "OO_WORKSPACE_FROZEN"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_repeated_promotion_is_idempotent(client, oo_editorial_headers, seed):
    author_ref = str(seed["executor_user_id"])
    workspace_id, _ = create_editorial_ready_workspace(
        client, oo_editorial_headers, seed, author_ref=author_ref
    )
    try:
        first = promote_workspace(client, oo_editorial_headers, workspace_id)
        second = promote_workspace(client, oo_editorial_headers, workspace_id)
        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["idempotent_replay"] is True
        assert (
            first.json()["document"]["document"]["document_id"]
            == second.json()["document"]["document"]["document_id"]
        )
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_promotion_without_reconciliation_blocked(client, oo_editorial_headers, seed):
    author_ref = str(seed["executor_user_id"])
    workspace_id, detail = create_ready_workspace(
        client, oo_editorial_headers, seed, author_ref=author_ref, locales=("ru", "kk")
    )
    try:
        for block in detail["blocks"]:
            confirm_block(
                client,
                oo_editorial_headers,
                workspace_id,
                block,
                role="CONTENT_AUTHOR",
                confirmer_ref=author_ref,
            )
        with engine.begin() as conn:
            _force_editorial_ready_stage(conn, workspace_id)
        resp = promote_workspace(client, oo_editorial_headers, workspace_id)
        assert resp.status_code == 409
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_promotion_without_confirmations_blocked(client, oo_editorial_headers, seed):
    author_ref = str(seed["executor_user_id"])
    workspace_id, _ = create_ready_workspace(
        client, oo_editorial_headers, seed, author_ref=author_ref, locales=("ru", "kk")
    )
    try:
        with engine.begin() as conn:
            _force_editorial_ready_stage(conn, workspace_id)
        resp = promote_workspace(client, oo_editorial_headers, workspace_id)
        assert resp.status_code == 409
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_promotion_without_ru_blocked(client, oo_editorial_headers, seed):
    author_ref = str(seed["executor_user_id"])
    workspace_id, _ = create_ready_workspace(
        client, oo_editorial_headers, seed, author_ref=author_ref, locales=("kk",)
    )
    try:
        with engine.begin() as conn:
            _force_editorial_ready_stage(conn, workspace_id)
        resp = promote_workspace(client, oo_editorial_headers, workspace_id)
        assert resp.status_code == 409
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_promotion_without_kk_blocked(client, oo_editorial_headers, seed):
    author_ref = str(seed["executor_user_id"])
    workspace_id, _ = create_ready_workspace(
        client, oo_editorial_headers, seed, author_ref=author_ref, locales=("ru",)
    )
    try:
        with engine.begin() as conn:
            _force_editorial_ready_stage(conn, workspace_id)
        resp = promote_workspace(client, oo_editorial_headers, workspace_id)
        assert resp.status_code == 409
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_promotion_stale_workspace_version_conflict(client, oo_editorial_headers, seed):
    author_ref = str(seed["executor_user_id"])
    workspace_id, detail = create_editorial_ready_workspace(
        client, oo_editorial_headers, seed, author_ref=author_ref
    )
    try:
        stale_version = detail["workspace"]["version"] - 1
        resp = promote_workspace(
            client, oo_editorial_headers, workspace_id, expected_version=stale_version
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["code"] == "OO_PROMOTION_VERSION_CONFLICT"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_promotion_authorization_requires_permission(
    client, oo_editorial_headers, oo_regular_headers, seed
):
    author_ref = str(seed["executor_user_id"])
    workspace_id, _ = create_editorial_ready_workspace(
        client, oo_editorial_headers, seed, author_ref=author_ref
    )
    try:
        with engine.begin() as conn:
            revoke_user_permission(conn, int(seed["executor_user_id"]), "OPERATIONAL_ORDERS_PROMOTE")
            _grant_user_permission(conn, int(seed["executor_user_id"]), "OPERATIONAL_ORDERS_INTAKE_READ")
        resp = promote_workspace(client, oo_regular_headers, workspace_id)
        assert resp.status_code == 403
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_cross_document_substitution_blocked(client, oo_editorial_headers, seed):
    author_ref = str(seed["executor_user_id"])
    workspace_a, _ = create_editorial_ready_workspace(
        client, oo_editorial_headers, seed, author_ref=author_ref
    )
    workspace_b, _ = create_editorial_ready_workspace(
        client, oo_editorial_headers, seed, author_ref=author_ref
    )
    try:
        promoted_a = promote_workspace(client, oo_editorial_headers, workspace_a)
        document_a = promoted_a.json()["document"]["document"]["document_id"]
        detail_b = client.get(f"{BASE}/{workspace_b}", headers=oo_editorial_headers).json()
        resp = client.post(
            f"{WORKSPACES_BASE}/{workspace_b}/promote",
            json={"expected_version": detail_b["workspace"]["version"]},
            headers=oo_editorial_headers,
        )
        assert resp.status_code == 200
        document_b = resp.json()["document"]["document"]["document_id"]
        assert document_a != document_b

        wrong_doc = client.get(
            f"{DOCUMENTS_BASE}/{document_a}",
            headers=oo_editorial_headers,
        )
        assert wrong_doc.status_code == 200
        assert int(wrong_doc.json()["document"]["workspace_id"]) == workspace_a
        assert int(wrong_doc.json()["document"]["workspace_id"]) != workspace_b
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_a)
            cleanup_workspace(conn, workspace_b)


@pytest.fixture
def oo_promote_headers(seed):
    user_id = int(seed["executor_user_id"])
    perms = (
        "OPERATIONAL_ORDERS_INTAKE_CREATE",
        "OPERATIONAL_ORDERS_INTAKE_READ",
        "OPERATIONAL_ORDERS_INTAKE_OPERATE",
        "OPERATIONAL_ORDERS_TRANSLATION_ASSIGN",
        "OPERATIONAL_ORDERS_TRANSLATION_WORK",
        "OPERATIONAL_ORDERS_CONTENT_CONFIRM",
        "OPERATIONAL_ORDERS_RECONCILE",
        "OPERATIONAL_ORDERS_EDITORIAL_READY",
        "OPERATIONAL_ORDERS_PROMOTE",
    )
    with engine.begin() as conn:
        for perm in perms:
            _grant_user_permission(conn, user_id, perm)
    from tests.conftest import auth_headers

    try:
        yield auth_headers(user_id)
    finally:
        from tests.operational_orders.conftest import revoke_user_access_grants

        with engine.begin() as conn:
            revoke_user_access_grants(conn, user_id)


def test_promotion_with_promote_permission(client, oo_promote_headers, seed):
    author_ref = str(seed["executor_user_id"])
    workspace_id, _ = create_editorial_ready_workspace(
        client, oo_promote_headers, seed, author_ref=author_ref
    )
    try:
        resp = promote_workspace(client, oo_promote_headers, workspace_id)
        assert resp.status_code == 200
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)
