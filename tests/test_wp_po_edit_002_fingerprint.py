# tests/test_wp_po_edit_002_fingerprint.py
"""Unit tests for editorial fingerprint helpers (WP-PO-EDIT-002)."""
from __future__ import annotations

from app.services.personnel_orders_editorial.constants import GENERATOR_VERSION
from app.services.personnel_orders_editorial.fingerprint import (
    canonical_json,
    compute_fingerprint,
)


def test_same_input_same_hash() -> None:
    payload = {
        "generator_key": "order.title",
        "generator_version": GENERATOR_VERSION,
        "locale": "kk",
        "order_type_code": "HIRE",
    }
    assert compute_fingerprint(payload) == compute_fingerprint(dict(payload))


def test_key_order_does_not_matter() -> None:
    a = {"b": 1, "a": 2, "generator_key": "x", "generator_version": "1.0.0"}
    b = {"a": 2, "generator_key": "x", "generator_version": "1.0.0", "b": 1}
    assert compute_fingerprint(a) == compute_fingerprint(b)
    assert canonical_json(a) == canonical_json(b)


def test_relevant_field_change_changes_hash() -> None:
    base = {
        "generator_key": "item.body",
        "generator_version": GENERATOR_VERSION,
        "employee_name": "Ivanov",
        "item_type_code": "HIRE",
    }
    changed = dict(base)
    changed["employee_name"] = "Petrov"
    assert compute_fingerprint(base) != compute_fingerprint(changed)


def test_irrelevant_none_exclusion_is_stable() -> None:
    with_none = {
        "generator_key": "order.preamble",
        "generator_version": GENERATOR_VERSION,
        "legal_basis_article": None,
        "locale": "ru",
    }
    without_none = {
        "generator_key": "order.preamble",
        "generator_version": GENERATOR_VERSION,
        "locale": "ru",
    }
    assert compute_fingerprint(with_none) == compute_fingerprint(without_none)


def test_generator_version_change_changes_hash() -> None:
    base = {
        "generator_key": "order.title",
        "generator_version": "1.0.0",
        "order_type_code": "HIRE",
    }
    bumped = dict(base)
    bumped["generator_version"] = "1.0.1"
    assert compute_fingerprint(base) != compute_fingerprint(bumped)
