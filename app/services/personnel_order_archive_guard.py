"""Archive immutability guard for personnel orders (WP-PO-LC-DEL-005A)."""
from __future__ import annotations

from typing import Any, Mapping


class PersonnelOrderArchivedError(RuntimeError):
    """Mutation blocked because the order is archived."""

    code = "ORDER_ARCHIVED"

    def __init__(
        self,
        message: str = "Архивный приказ необходимо восстановить перед изменением.",
    ):
        super().__init__(message)
        self.code = str(self.code)


def assert_order_not_archived(order: Mapping[str, Any]) -> None:
    """Raise ORDER_ARCHIVED when archived_at is set on the order row."""
    if order.get("archived_at") is not None:
        order_id = order.get("order_id")
        suffix = f" {order_id}" if order_id is not None else ""
        raise PersonnelOrderArchivedError(
            f"Архивный приказ{suffix} необходимо восстановить перед изменением."
        )
