"""READY-for-signature editorial gate (WP-PO-EDIT-002 / R8)."""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from app.db.engine import engine
from app.db.models.personnel_orders import (
    ITEM_BLOCK_TYPE_BASIS,
    ITEM_BLOCK_TYPE_BODY,
    ITEM_STATUS_ACTIVE,
    ORDER_BLOCK_TYPE_CLOSING,
    ORDER_BLOCK_TYPE_PREAMBLE,
    ORDER_BLOCK_TYPE_TITLE,
    REVIEW_STATUS_GENERATION_FAILED,
    REVIEW_STATUS_REVIEW_REQUIRED,
    REVIEW_STATUS_STALE,
)
from app.services.personnel_orders_editorial.availability import require_available
from app.services.personnel_orders_editorial.basis_policy import resolve_basis_required
from app.services.personnel_orders_editorial.constants import ALLOWED_LOCALES
from app.services.personnel_orders_editorial.mapper import effective_text
from app.services.personnel_orders_editorial.repository import (
    fetch_order,
    load_item_blocks,
    load_items,
    load_order_blocks,
)


def append_status_problems(
    problems: List[Dict[str, Any]],
    block: Mapping[str, Any],
    *,
    locale: str,
    order_item_id: Optional[int] = None,
) -> None:
    status = str(block.get("review_status") or "")
    base = {
        "locale": locale,
        "block_type": block.get("block_type"),
        "order_item_id": order_item_id,
        "block_id": int(block["block_id"]) if block.get("block_id") is not None else None,
    }
    if status == REVIEW_STATUS_GENERATION_FAILED:
        problems.append({"code": "GENERATION_FAILED", **base})
    elif status == REVIEW_STATUS_STALE:
        problems.append({"code": "STALE_REQUIRED", **base})
    elif status == REVIEW_STATUS_REVIEW_REQUIRED:
        problems.append({"code": "REVIEW_REQUIRED", **base})


def evaluate_ready_gate(order_id: int) -> List[Dict[str, Any]]:
    """Return editorial problems blocking READY_FOR_SIGNATURE (no full text).

    Per locale (kk/ru): title and preamble are required with non-empty effective
    text; closing is optional (status checked only when present).
    """
    require_available()
    problems: List[Dict[str, Any]] = []

    with engine.begin() as conn:
        order = fetch_order(conn, order_id)
        items = [
            i
            for i in load_items(conn, order_id)
            if str(i.get("item_status")) == ITEM_STATUS_ACTIVE
        ]
        order_blocks = load_order_blocks(conn, order_id)
        item_blocks = load_item_blocks(conn, order_id=order_id)

        order_by_key = {(b["locale"], b["block_type"]): b for b in order_blocks}
        for locale in ALLOWED_LOCALES:
            title = order_by_key.get((locale, ORDER_BLOCK_TYPE_TITLE))
            if title is None:
                problems.append(
                    {
                        "code": "MISSING_TITLE",
                        "locale": locale,
                        "block_type": ORDER_BLOCK_TYPE_TITLE,
                        "order_item_id": None,
                    }
                )
            else:
                eff = effective_text(title.get("override_text"), title.get("generated_text"))
                if not eff:
                    problems.append(
                        {
                            "code": "EMPTY_EFFECTIVE",
                            "locale": locale,
                            "block_type": ORDER_BLOCK_TYPE_TITLE,
                            "order_item_id": None,
                            "block_id": int(title["block_id"]),
                        }
                    )
                append_status_problems(problems, title, locale=locale)

            preamble = order_by_key.get((locale, ORDER_BLOCK_TYPE_PREAMBLE))
            if preamble is None:
                problems.append(
                    {
                        "code": "MISSING_PREAMBLE",
                        "locale": locale,
                        "block_type": ORDER_BLOCK_TYPE_PREAMBLE,
                        "order_item_id": None,
                    }
                )
            else:
                eff = effective_text(
                    preamble.get("override_text"), preamble.get("generated_text")
                )
                if not eff:
                    problems.append(
                        {
                            "code": "EMPTY_EFFECTIVE",
                            "locale": locale,
                            "block_type": ORDER_BLOCK_TYPE_PREAMBLE,
                            "order_item_id": None,
                            "block_id": int(preamble["block_id"]),
                        }
                    )
                append_status_problems(problems, preamble, locale=locale)

            closing = order_by_key.get((locale, ORDER_BLOCK_TYPE_CLOSING))
            if closing is not None:
                append_status_problems(problems, closing, locale=locale)

        item_blocks_by_item: Dict[int, List[Dict[str, Any]]] = {}
        for b in item_blocks:
            item_blocks_by_item.setdefault(int(b["order_item_id"]), []).append(b)

        for item in items:
            item_id = int(item["item_id"])
            basis_required, unsupported = resolve_basis_required(str(item["item_type_code"]))
            if unsupported:
                problems.append(
                    {
                        "code": "UNSUPPORTED_BASIS_POLICY",
                        "order_item_id": item_id,
                        "item_type_code": item["item_type_code"],
                        "detail": unsupported,
                    }
                )

            by_key = {
                (b["locale"], b["block_type"]): b
                for b in item_blocks_by_item.get(item_id, [])
            }
            for locale in ALLOWED_LOCALES:
                body = by_key.get((locale, ITEM_BLOCK_TYPE_BODY))
                if body is None or not effective_text(
                    body.get("override_text"), body.get("generated_text")
                ):
                    problems.append(
                        {
                            "code": "EMPTY_EFFECTIVE" if body else "EMPTY_EFFECTIVE",
                            "locale": locale,
                            "block_type": ITEM_BLOCK_TYPE_BODY,
                            "order_item_id": item_id,
                            "block_id": int(body["block_id"]) if body else None,
                        }
                    )
                if body:
                    append_status_problems(
                        problems, body, locale=locale, order_item_id=item_id
                    )

                if basis_required:
                    basis = by_key.get((locale, ITEM_BLOCK_TYPE_BASIS))
                    if basis is None or not effective_text(
                        basis.get("override_text"), basis.get("generated_text")
                    ):
                        problems.append(
                            {
                                "code": "EMPTY_EFFECTIVE",
                                "locale": locale,
                                "block_type": ITEM_BLOCK_TYPE_BASIS,
                                "order_item_id": item_id,
                                "block_id": int(basis["block_id"]) if basis else None,
                            }
                        )
                    if basis:
                        append_status_problems(
                            problems, basis, locale=locale, order_item_id=item_id
                        )

        _ = order  # fetched for existence

    # Deduplicate by code+locale+block_type+item
    seen = set()
    unique: List[Dict[str, Any]] = []
    for problem in problems:
        key = (
            problem.get("code"),
            problem.get("locale"),
            problem.get("block_type"),
            problem.get("order_item_id"),
            problem.get("block_id"),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(problem)
    return unique
