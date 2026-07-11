"""Draft-writability guard for editorial mutations (WP-PO-EDIT-002)."""
from __future__ import annotations

from typing import Any, Mapping

from app.db.models.personnel_orders import ORDER_STATUS_DRAFT


def ensure_draft_writable(order: Mapping[str, Any]) -> None:
    status = str(order.get("status") or "")
    if status != ORDER_STATUS_DRAFT:
        from app.services.personnel_orders_command_service import PersonnelOrderConflictError

        raise PersonnelOrderConflictError(
            f"Personnel order {order['order_id']} editorial writes require DRAFT "
            f"(current: {status})."
        )
