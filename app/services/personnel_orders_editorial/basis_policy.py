"""Basis-required policy for personnel order item types (WP-PO-EDIT-002)."""
from __future__ import annotations

from app.db.models.personnel_orders import (
    ORDER_TYPE_CONCURRENT_DUTY_END,
    ORDER_TYPE_CONCURRENT_DUTY_START,
    ORDER_TYPE_HIRE,
    ORDER_TYPE_TERMINATION,
    ORDER_TYPE_TRANSFER,
)

_BASIS_REQUIRED_TYPES = frozenset(
    {
        ORDER_TYPE_HIRE,
        ORDER_TYPE_TRANSFER,
        ORDER_TYPE_TERMINATION,
        ORDER_TYPE_CONCURRENT_DUTY_START,
        ORDER_TYPE_CONCURRENT_DUTY_END,
    }
)


def resolve_basis_required(item_type_code: str) -> tuple[bool, str | None]:
    """Return ``(basis_required, unsupported_code)``.

    Supported MVP types always require a basis. Unknown types fail closed:
    treat as required AND unsupported so callers mark REVIEW_REQUIRED.
    """
    normalized = str(item_type_code or "").strip().upper()
    if normalized in _BASIS_REQUIRED_TYPES:
        return True, None
    return True, "UNSUPPORTED_ITEM_TYPE"
