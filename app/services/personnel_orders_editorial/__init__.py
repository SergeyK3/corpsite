"""Personnel order editorial generators and helpers (WP-PO-EDIT-002).

Heavy service entrypoints live behind
``app.services.personnel_orders_editorial_service`` (thin facade) to avoid
pulling DB-backed modules at package import time.
"""
from app.services.personnel_orders_editorial.basis_policy import resolve_basis_required
from app.services.personnel_orders_editorial.constants import (
    ALLOWED_LOCALES,
    GENERATOR_KEY_ITEM_BASIS,
    GENERATOR_KEY_ITEM_BODY,
    GENERATOR_KEY_ORDER_CLOSING,
    GENERATOR_KEY_ORDER_PREAMBLE,
    GENERATOR_KEY_ORDER_TITLE,
    GENERATOR_VERSION,
)
from app.services.personnel_orders_editorial.fingerprint import (
    canonical_json,
    compute_fingerprint,
)
from app.services.personnel_orders_editorial.generators import (
    generate_basis_text,
    generate_item_body,
    generate_order_block,
)

__all__ = [
    "ALLOWED_LOCALES",
    "GENERATOR_KEY_ITEM_BASIS",
    "GENERATOR_KEY_ITEM_BODY",
    "GENERATOR_KEY_ORDER_CLOSING",
    "GENERATOR_KEY_ORDER_PREAMBLE",
    "GENERATOR_KEY_ORDER_TITLE",
    "GENERATOR_VERSION",
    "canonical_json",
    "compute_fingerprint",
    "generate_basis_text",
    "generate_item_body",
    "generate_order_block",
    "resolve_basis_required",
]
