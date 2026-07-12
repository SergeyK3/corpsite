# tests/operational_orders/test_editorial_authorization.py
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import auth_headers
from tests.operational_orders.conftest import _grant_user_permission, cleanup_workspace, revoke_user_access_grants
from tests.operational_orders.test_helpers import BASE, create_ready_workspace

pytestmark = pytest.mark.usefixtures("_require_oo_schema_fixture")


def test_read_only_user_cannot_mutate(client, seed, oo_intake_headers):
    author_ref = str(seed["initiator_user_id"])
    workspace_id, detail = create_ready_workspace(
        client, oo_intake_headers, seed, author_ref=author_ref, locales=("ru", "kk")
    )
    try:
        with engine.begin() as conn:
            _grant_user_permission(conn, int(seed["executor_user_id"]), "OPERATIONAL_ORDERS_INTAKE_READ")
        read_headers = auth_headers(seed["executor_user_id"])
        resp = client.post(
            f"{BASE}/{workspace_id}/confirmations",
            json={
                "block_id": detail["blocks"][0]["block_id"],
                "confirmation_role": "CONTENT_AUTHOR",
                "confirmer": {"reference_type": "PERSON", "reference": author_ref},
            },
            headers=read_headers,
        )
        assert resp.status_code == 403
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)
            revoke_user_access_grants(conn, int(seed["executor_user_id"]))


def test_operator_cannot_impersonate_content_author(client, oo_editorial_headers, seed):
    author_ref = "real-author-999"
    workspace_id, detail = create_ready_workspace(
        client, oo_editorial_headers, seed, author_ref=author_ref, locales=("ru", "kk")
    )
    try:
        ru_block = next(b for b in detail["blocks"] if b["locale"] == "ru")
        resp = client.post(
            f"{BASE}/{workspace_id}/confirmations",
            json={
                "block_id": ru_block["block_id"],
                "confirmation_role": "CONTENT_AUTHOR",
                "confirmer": {
                    "reference_type": "PERSON",
                    "reference": str(seed["executor_user_id"]),
                },
            },
            headers=oo_editorial_headers,
        )
        assert resp.status_code == 403
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)
            revoke_user_access_grants(conn, int(seed["executor_user_id"]))
