# tests/test_wp_po_edit_002_editorial_api.py
"""API tests for WP-PO-EDIT-002 editorial persistence endpoints."""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import auth_headers
from tests.test_wp_po_003_personnel_orders_schema import (
    _pick_employee_id,
    _require_schema as _require_po_003_schema,
)
from tests.test_wp_po_edit_002_migration import _require_schema as _require_edit_002_schema

pytestmark = pytest.mark.usefixtures("_require_wp_po_edit_002_schema")


@pytest.fixture(scope="module", autouse=True)
def _require_wp_po_edit_002_schema():
    _require_po_003_schema()
    _require_edit_002_schema()


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


def _cleanup_order(order_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM public.employee_events WHERE order_id = :order_id"),
            {"order_id": order_id},
        )
        conn.execute(
            text(
                """
                DELETE FROM public.personnel_order_item_editorial_blocks
                WHERE order_item_id IN (
                    SELECT item_id FROM public.personnel_order_items WHERE order_id = :order_id
                )
                """
            ),
            {"order_id": order_id},
        )
        conn.execute(
            text(
                """
                DELETE FROM public.personnel_order_item_bases
                WHERE order_item_id IN (
                    SELECT item_id FROM public.personnel_order_items WHERE order_id = :order_id
                )
                """
            ),
            {"order_id": order_id},
        )
        conn.execute(
            text("DELETE FROM public.personnel_order_editorial_blocks WHERE order_id = :order_id"),
            {"order_id": order_id},
        )
        conn.execute(
            text("DELETE FROM public.personnel_order_localized_texts WHERE order_id = :order_id"),
            {"order_id": order_id},
        )
        conn.execute(
            text("DELETE FROM public.personnel_order_items WHERE order_id = :order_id"),
            {"order_id": order_id},
        )
        conn.execute(
            text("DELETE FROM public.personnel_orders WHERE order_id = :order_id"),
            {"order_id": order_id},
        )


def _create_draft_with_item(client, headers, *, order_type: str = "HIRE") -> tuple[int, int]:
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        employee_id = _pick_employee_id(conn)

    create_resp = client.post(
        "/directory/personnel-orders",
        json={
            "order_number": f"WPEDIT2-{suffix}",
            "order_date": "2026-07-07",
            "order_type_code": order_type,
            "source_mode": "PAPER",
            "legal_basis_article": "33",
        },
        headers=headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    order_id = create_resp.json()["order"]["order_id"]

    item_resp = client.post(
        f"/directory/personnel-orders/{order_id}/items",
        json={
            "item_type_code": order_type,
            "employee_id": employee_id,
            "effective_date": "2026-07-07",
            "payload": {
                "employment_rate": 1.0,
                "org_unit_name": "Отдел кадров",
                "position_name": "Специалист",
            },
        },
        headers=headers,
    )
    assert item_resp.status_code == 200, item_resp.text
    item_id = item_resp.json()["items"][0]["item_id"]
    return order_id, item_id


def _find_block(state: dict, *, block_type: str, locale: str = "kk", item_id: int | None = None):
    if item_id is None:
        for block in state["order_blocks"]:
            if block["block_type"] == block_type and block["locale"] == locale:
                return block
    else:
        for group in state["items"]:
            if group["order_item_id"] != item_id:
                continue
            for block in group["blocks"]:
                if block["block_type"] == block_type and block["locale"] == locale:
                    return block
    raise AssertionError(f"block not found: {block_type}/{locale}/item={item_id}")


def test_generate_patch_regenerate_keeps_override_reset_and_ready_gate(
    client, privileged_headers
):
    order_id, item_id = _create_draft_with_item(client, privileged_headers)
    try:
        gen_resp = client.post(
            f"/directory/personnel-orders/{order_id}/editorial/generate",
            json={},
            headers=privileged_headers,
        )
        assert gen_resp.status_code == 200, gen_resp.text
        state = gen_resp.json()
        assert state["editable"] is True
        assert len(state["order_blocks"]) >= 6  # title/preamble/closing × kk/ru
        assert len(state["items"]) == 1
        assert len(state["items"][0]["blocks"]) >= 4  # body/basis × kk/ru

        title = _find_block(state, block_type="title", locale="kk")
        assert title["effective_text"]
        assert title["review_status"] == "CURRENT"
        original_generated = title["generated_text"]

        patch_resp = client.patch(
            f"/directory/personnel-orders/{order_id}/editorial/blocks/{title['block_id']}",
            json={"override_text": "Қолмен жазылған тақырып"},
            headers=privileged_headers,
        )
        assert patch_resp.status_code == 200, patch_resp.text
        patched = _find_block(patch_resp.json(), block_type="title", locale="kk")
        assert patched["override_text"] == "Қолмен жазылған тақырып"
        assert patched["effective_text"] == "Қолмен жазылған тақырып"
        assert patched["generated_text"] == original_generated

        # Change structured field then regenerate — override kept, REVIEW_REQUIRED.
        client.patch(
            f"/directory/personnel-orders/{order_id}",
            json={"legal_basis_article": "49"},
            headers=privileged_headers,
        )
        # Title fingerprint does not include legal_basis; change order type via item body path:
        # regenerate title after changing order_type_code.
        client.patch(
            f"/directory/personnel-orders/{order_id}",
            json={"order_type_code": "TRANSFER"},
            headers=privileged_headers,
        )
        regen = client.post(
            f"/directory/personnel-orders/{order_id}/editorial/generate",
            json={"block_type": "title", "locale": "kk"},
            headers=privileged_headers,
        )
        assert regen.status_code == 200, regen.text
        regenerated = _find_block(regen.json(), block_type="title", locale="kk")
        assert regenerated["override_text"] == "Қолмен жазылған тақырып"
        assert regenerated["review_status"] == "REVIEW_REQUIRED"
        assert regenerated["generated_text"] != original_generated

        reset_resp = client.post(
            f"/directory/personnel-orders/{order_id}/editorial/blocks/"
            f"{regenerated['block_id']}/reset-to-generated",
            headers=privileged_headers,
        )
        assert reset_resp.status_code == 200, reset_resp.text
        reset_block = _find_block(reset_resp.json(), block_type="title", locale="kk")
        assert reset_block["override_text"] is None
        assert reset_block["review_status"] == "CURRENT"
        assert reset_block["effective_text"] == reset_block["generated_text"]

        # Full regenerate to clear REVIEW_REQUIRED on other blocks, then ready.
        full = client.post(
            f"/directory/personnel-orders/{order_id}/editorial/generate",
            json={},
            headers=privileged_headers,
        )
        assert full.status_code == 200, full.text

        # Restore HIRE item type for consistency with header after earlier TRANSFER patch.
        client.patch(
            f"/directory/personnel-orders/{order_id}",
            json={"order_type_code": "HIRE"},
            headers=privileged_headers,
        )
        client.patch(
            f"/directory/personnel-orders/{order_id}/items/{item_id}",
            json={"item_type_code": "HIRE"},
            headers=privileged_headers,
        )
        client.post(
            f"/directory/personnel-orders/{order_id}/editorial/generate",
            json={},
            headers=privileged_headers,
        )

        ready = client.post(
            f"/directory/personnel-orders/{order_id}/ready-for-signature",
            headers=privileged_headers,
        )
        assert ready.status_code == 200, ready.text
        assert ready.json()["order"]["status"] == "READY_FOR_SIGNATURE"

        # READY rejects editorial writes.
        write_resp = client.post(
            f"/directory/personnel-orders/{order_id}/editorial/generate",
            json={},
            headers=privileged_headers,
        )
        assert write_resp.status_code == 409
    finally:
        _cleanup_order(order_id)


def test_ready_gate_rejects_without_generate(client, privileged_headers):
    order_id, _item_id = _create_draft_with_item(client, privileged_headers)
    try:
        ready = client.post(
            f"/directory/personnel-orders/{order_id}/ready-for-signature",
            headers=privileged_headers,
        )
        assert ready.status_code == 422, ready.text
        detail = ready.json()["detail"]
        assert detail["code"] == "READY_GATE_FAILED"
        assert isinstance(detail["problems"], list)
        assert any(p.get("code") == "MISSING_TITLE" for p in detail["problems"])
        codes_blob = " ".join(str(p) for p in detail["problems"])
        assert "Жұмысқа" not in codes_blob  # no full document prose
    finally:
        _cleanup_order(order_id)


def test_draft_only_patch_on_get_state(client, privileged_headers):
    order_id, _item_id = _create_draft_with_item(client, privileged_headers)
    try:
        client.post(
            f"/directory/personnel-orders/{order_id}/editorial/generate",
            json={},
            headers=privileged_headers,
        )
        get_resp = client.get(
            f"/directory/personnel-orders/{order_id}/editorial",
            headers=privileged_headers,
        )
        assert get_resp.status_code == 200, get_resp.text
        assert get_resp.json()["editable"] is True
        assert get_resp.json()["order_blocks"]
    finally:
        _cleanup_order(order_id)
