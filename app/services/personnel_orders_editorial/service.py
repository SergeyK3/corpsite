"""Editorial read / patch / reset operations (WP-PO-EDIT-002)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.db.engine import engine
from app.db.models.personnel_orders import (
    ITEM_BLOCK_TYPE_BASIS,
    ORDER_STATUS_DRAFT,
    REVIEW_STATUS_CURRENT,
)
from app.services.personnel_orders_editorial.audit import write_editorial_audit
from app.services.personnel_orders_editorial.availability import require_available
from app.services.personnel_orders_editorial.basis_policy import resolve_basis_required
from app.services.personnel_orders_editorial.exceptions import (
    PersonnelOrderEditorialConflictError,
)
from app.services.personnel_orders_editorial.mapper import serialize_block
from app.services.personnel_orders_editorial.repository import (
    fetch_order,
    find_block,
    load_item_blocks,
    load_items,
    load_order_blocks,
    update_item_block_override,
    update_order_block_override,
)
from app.services.personnel_order_archive_guard import assert_order_not_archived
from app.services.personnel_orders_editorial.write_lock import ensure_draft_writable
from app.services.personnel_orders_query_service import PersonnelOrderValidationError


def get_editorial_state(order_id: int) -> Dict[str, Any]:
    """Return order + item editorial blocks with effective_text and editable flag."""
    require_available()
    with engine.begin() as conn:
        order = fetch_order(conn, order_id)
        editable = str(order["status"]) == ORDER_STATUS_DRAFT
        items = load_items(conn, order_id)
        order_blocks = load_order_blocks(conn, order_id)
        item_blocks = load_item_blocks(conn, order_id=order_id)

        item_groups: List[Dict[str, Any]] = []
        blocks_by_item: Dict[int, List[Dict[str, Any]]] = {}
        for block in item_blocks:
            blocks_by_item.setdefault(int(block["order_item_id"]), []).append(block)

        for item in items:
            item_id = int(item["item_id"])
            basis_required, _ = resolve_basis_required(str(item["item_type_code"]))
            group_blocks = [
                serialize_block(b, scope="item", editable=editable)
                for b in blocks_by_item.get(item_id, [])
            ]
            # Prefer basis_required from stored basis blocks when present.
            for b in group_blocks:
                if b["block_type"] == ITEM_BLOCK_TYPE_BASIS and b.get("basis_required") is not None:
                    basis_required = bool(b["basis_required"])
                    break
            item_groups.append(
                {
                    "order_item_id": item_id,
                    "item_number": int(item["item_number"]),
                    "item_type_code": item["item_type_code"],
                    "basis_required": basis_required,
                    "blocks": group_blocks,
                }
            )

        return {
            "order_id": int(order["order_id"]),
            "order_status": order["status"],
            "editable": editable,
            "order_blocks": [
                serialize_block(b, scope="order", editable=editable) for b in order_blocks
            ],
            "items": item_groups,
        }


def patch_editorial_block(
    order_id: int,
    block_id: int,
    *,
    user_id: Optional[int],
    override_text: Optional[str] = None,
    clear_override: bool = False,
    expected_revision: Optional[int] = None,
) -> Dict[str, Any]:
    """Update override on a DRAFT order block (order or item PK)."""
    require_available()
    if not clear_override and override_text is None:
        raise PersonnelOrderValidationError(
            "Provide override_text or clear_override=true."
        )

    with engine.begin() as conn:
        order = fetch_order(conn, order_id)
        assert_order_not_archived(order)
        ensure_draft_writable(order)
        scope, row = find_block(conn, order_id, block_id)

        if expected_revision is not None and int(row["revision"]) != int(expected_revision):
            raise PersonnelOrderEditorialConflictError(
                f"Editorial block {block_id} revision mismatch "
                f"(expected {expected_revision}, actual {row['revision']})."
            )

        old_status = str(row["review_status"])
        if clear_override:
            new_override = None
            new_status = REVIEW_STATUS_CURRENT
            event_type = "EDITORIAL_OVERRIDE_CLEARED"
        else:
            new_override = override_text
            new_status = REVIEW_STATUS_CURRENT
            event_type = "EDITORIAL_OVERRIDE_UPDATED"

        if scope == "order":
            update_order_block_override(
                conn,
                block_id=int(block_id),
                override_text=new_override,
                review_status=new_status,
                user_id=user_id,
            )
        else:
            update_item_block_override(
                conn,
                block_id=int(block_id),
                override_text=new_override,
                review_status=new_status,
                user_id=user_id,
            )

        write_editorial_audit(
            event_type=event_type,
            actor_user_id=user_id,
            metadata={
                "order_id": int(order_id),
                "item_id": int(row["order_item_id"]) if row.get("order_item_id") is not None else None,
                "block_type": row["block_type"],
                "locale": row["locale"],
                "user_id": user_id,
                "result": "ok",
                "generator_version": row.get("generator_version"),
                "old_review_status": old_status,
                "new_review_status": new_status,
            },
            conn=conn,
        )

    return get_editorial_state(int(order_id))


def reset_block_to_generated(
    order_id: int,
    block_id: int,
    *,
    user_id: Optional[int],
) -> Dict[str, Any]:
    """Clear override and set review_status=CURRENT."""
    return patch_editorial_block(
        order_id,
        block_id,
        user_id=user_id,
        clear_override=True,
    )
