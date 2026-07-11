# tests/test_wp_po_edit_002_basis_policy.py
"""Unit tests for basis-required policy (WP-PO-EDIT-002)."""
from __future__ import annotations

import pytest

from app.services.personnel_orders_editorial.basis_policy import resolve_basis_required


@pytest.mark.parametrize(
    "item_type",
    [
        "HIRE",
        "TRANSFER",
        "TERMINATION",
        "CONCURRENT_DUTY_START",
        "CONCURRENT_DUTY_END",
        "hire",
    ],
)
def test_supported_types_require_basis(item_type: str) -> None:
    required, unsupported = resolve_basis_required(item_type)
    assert required is True
    assert unsupported is None


def test_unknown_type_fail_closed() -> None:
    required, unsupported = resolve_basis_required("BONUS")
    assert required is True
    assert unsupported == "UNSUPPORTED_ITEM_TYPE"
