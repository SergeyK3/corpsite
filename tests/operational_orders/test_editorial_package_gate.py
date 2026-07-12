# tests/operational_orders/test_editorial_package_gate.py
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.operational_orders.conftest import cleanup_workspace
from tests.operational_orders.test_helpers import BASE, confirm_block, create_ready_workspace

pytestmark = pytest.mark.usefixtures("_require_oo_schema_fixture")


def _blocks_by_locale(detail, locale):
    return [b for b in detail["blocks"] if b["locale"] == locale]


def test_missing_kk_blocked(client, oo_editorial_headers, seed):
    author_ref = str(seed["executor_user_id"])
    workspace_id, _ = create_ready_workspace(
        client, oo_editorial_headers, seed, author_ref=author_ref, locales=("ru",)
    )
    try:
        resp = client.post(
            f"{BASE}/{workspace_id}/validate-editorial-package",
            json={},
            headers=oo_editorial_headers,
        )
        assert resp.status_code == 200
        codes = {issue["code"] for issue in resp.json()["validation"]["issues"]}
        assert "OO202" in codes
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_complete_valid_package_reaches_editorial_ready(client, oo_editorial_headers, seed):
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
        fresh = client.get(f"{BASE}/{workspace_id}", headers=oo_editorial_headers).json()
        for ru_block in _blocks_by_locale(fresh, "ru"):
            kk_block = next(
                b
                for b in _blocks_by_locale(fresh, "kk")
                if b["block_type"] == ru_block["block_type"] and b["sequence"] == ru_block["sequence"]
            )
            client.post(
                f"{BASE}/{workspace_id}/reconciliations",
                json={"ru_block_id": ru_block["block_id"], "kk_block_id": kk_block["block_id"]},
                headers=oo_editorial_headers,
            )
        ready_detail = client.get(f"{BASE}/{workspace_id}", headers=oo_editorial_headers).json()
        ready_resp = client.post(
            f"{BASE}/{workspace_id}/editorial-package-ready",
            json={"expected_version": ready_detail["workspace"]["version"]},
            headers=oo_editorial_headers,
        )
        assert ready_resp.status_code == 200, ready_resp.text
        assert ready_resp.json()["workspace"]["stage"] == "EDITORIAL_PACKAGE_READY"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_repeated_gate_call_idempotent(client, oo_editorial_headers, seed):
    author_ref = str(seed["executor_user_id"])
    workspace_id, detail = create_ready_workspace(
        client, oo_editorial_headers, seed, author_ref=author_ref, locales=("ru", "kk")
    )
    try:
        for block in detail["blocks"]:
            confirm_block(
                client, oo_editorial_headers, workspace_id, block, role="CONTENT_AUTHOR", confirmer_ref=author_ref
            )
        fresh = client.get(f"{BASE}/{workspace_id}", headers=oo_editorial_headers).json()
        for ru_block in _blocks_by_locale(fresh, "ru"):
            kk_block = next(
                b
                for b in _blocks_by_locale(fresh, "kk")
                if b["block_type"] == ru_block["block_type"] and b["sequence"] == ru_block["sequence"]
            )
            client.post(
                f"{BASE}/{workspace_id}/reconciliations",
                json={"ru_block_id": ru_block["block_id"], "kk_block_id": kk_block["block_id"]},
                headers=oo_editorial_headers,
            )
        detail2 = client.get(f"{BASE}/{workspace_id}", headers=oo_editorial_headers).json()
        first = client.post(
            f"{BASE}/{workspace_id}/editorial-package-ready",
            json={"expected_version": detail2["workspace"]["version"]},
            headers=oo_editorial_headers,
        )
        second = client.post(
            f"{BASE}/{workspace_id}/editorial-package-ready",
            json={},
            headers=oo_editorial_headers,
        )
        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["workspace"]["stage"] == "EDITORIAL_PACKAGE_READY"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)
