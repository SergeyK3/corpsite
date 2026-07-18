# tests/personnel_orders/characterization/test_personnel_orders_characterization_localization.py
"""Characterization: Personnel Orders RU/KK effective text behavior (UDE-007)."""
from __future__ import annotations

import pytest

from tests.personnel_orders.characterization._helpers import (
    cleanup_order_with_editorial,
    create_draft_with_item,
    require_edit_002_schema,
    unique_suffix,
)

pytestmark = pytest.mark.usefixtures("_require_po_characterization_schema")


@pytest.fixture(scope="module", autouse=True)
def _require_editorial_schema() -> None:
    require_edit_002_schema()


def _find_block(state: dict, *, block_type: str, locale: str, item_id: int | None = None):
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


def test_personnel_orders_characterization_ru_kk_generated_independently(
    client, privileged_headers
) -> None:
    order_id: int | None = None
    try:
        order_id, _item_id = create_draft_with_item(
            client,
            privileged_headers,
            suffix=unique_suffix(),
        )
        gen_resp = client.post(
            f"/directory/personnel-orders/{order_id}/editorial/generate",
            json={},
            headers=privileged_headers,
        )
        assert gen_resp.status_code == 200, gen_resp.text
        state = gen_resp.json()

        ru_title = _find_block(state, block_type="title", locale="ru")
        kk_title = _find_block(state, block_type="title", locale="kk")
        assert ru_title["generated_text"]
        assert kk_title["generated_text"]
        assert ru_title["generated_text"] != kk_title["generated_text"]
    finally:
        cleanup_order_with_editorial(order_id)


def test_personnel_orders_characterization_override_not_equal_to_generated(
    client, privileged_headers
) -> None:
    order_id: int | None = None
    try:
        order_id, _item_id = create_draft_with_item(
            client,
            privileged_headers,
            suffix=unique_suffix(),
        )
        gen_resp = client.post(
            f"/directory/personnel-orders/{order_id}/editorial/generate",
            json={},
            headers=privileged_headers,
        )
        assert gen_resp.status_code == 200, gen_resp.text
        title = _find_block(gen_resp.json(), block_type="title", locale="ru")

        patch_resp = client.patch(
            f"/directory/personnel-orders/{order_id}/editorial/blocks/{title['block_id']}",
            json={"override_text": "Synthetic RU override title"},
            headers=privileged_headers,
        )
        assert patch_resp.status_code == 200, patch_resp.text
        patched = _find_block(patch_resp.json(), block_type="title", locale="ru")
        assert patched["effective_text"] == "Synthetic RU override title"
        assert patched["generated_text"] == title["generated_text"]
        assert patched["effective_text"] != patched["generated_text"]
    finally:
        cleanup_order_with_editorial(order_id)


def test_personnel_orders_characterization_locale_override_does_not_replace_other_locale(
    client, privileged_headers
) -> None:
    order_id: int | None = None
    try:
        order_id, _item_id = create_draft_with_item(
            client,
            privileged_headers,
            suffix=unique_suffix(),
        )
        gen_resp = client.post(
            f"/directory/personnel-orders/{order_id}/editorial/generate",
            json={},
            headers=privileged_headers,
        )
        assert gen_resp.status_code == 200, gen_resp.text
        ru_title = _find_block(gen_resp.json(), block_type="title", locale="ru")
        kk_before = _find_block(gen_resp.json(), block_type="title", locale="kk")

        patch_resp = client.patch(
            f"/directory/personnel-orders/{order_id}/editorial/blocks/{ru_title['block_id']}",
            json={"override_text": "Synthetic RU-only override"},
            headers=privileged_headers,
        )
        assert patch_resp.status_code == 200, patch_resp.text
        kk_after = _find_block(patch_resp.json(), block_type="title", locale="kk")
        assert kk_after["effective_text"] == kk_before["effective_text"]
        assert kk_after["generated_text"] == kk_before["generated_text"]
    finally:
        cleanup_order_with_editorial(order_id)


def test_personnel_orders_characterization_regenerate_keeps_override(
    client, privileged_headers
) -> None:
    order_id: int | None = None
    try:
        order_id, _item_id = create_draft_with_item(
            client,
            privileged_headers,
            suffix=unique_suffix(),
        )
        gen_resp = client.post(
            f"/directory/personnel-orders/{order_id}/editorial/generate",
            json={},
            headers=privileged_headers,
        )
        assert gen_resp.status_code == 200, gen_resp.text
        title = _find_block(gen_resp.json(), block_type="title", locale="kk")
        original_generated = title["generated_text"]

        patch_resp = client.patch(
            f"/directory/personnel-orders/{order_id}/editorial/blocks/{title['block_id']}",
            json={"override_text": "Synthetic KK override"},
            headers=privileged_headers,
        )
        assert patch_resp.status_code == 200, patch_resp.text

        regen_resp = client.post(
            f"/directory/personnel-orders/{order_id}/editorial/generate",
            json={"block_type": "title", "locale": "kk"},
            headers=privileged_headers,
        )
        assert regen_resp.status_code == 200, regen_resp.text
        regenerated = _find_block(regen_resp.json(), block_type="title", locale="kk")
        assert regenerated["override_text"] == "Synthetic KK override"
        assert regenerated["effective_text"] == "Synthetic KK override"
    finally:
        cleanup_order_with_editorial(order_id)
