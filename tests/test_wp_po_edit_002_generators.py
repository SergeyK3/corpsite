# tests/test_wp_po_edit_002_generators.py
"""Unit tests for editorial text generators (WP-PO-EDIT-002)."""
from __future__ import annotations

from app.services.personnel_orders_editorial.constants import GENERATOR_VERSION
from app.services.personnel_orders_editorial.generators import (
    DOCUMENT_TITLES,
    generate_basis_text,
    generate_item_body,
    generate_order_block,
)


def test_document_titles_kk_ru() -> None:
    assert DOCUMENT_TITLES["HIRE"]["kk"]
    assert DOCUMENT_TITLES["HIRE"]["ru"]
    title_kk = generate_order_block("title", "kk", {"order_type_code": "HIRE"})
    title_ru = generate_order_block("title", "ru", {"order_type_code": "HIRE"})
    assert title_kk["generated_text"] == DOCUMENT_TITLES["HIRE"]["kk"]
    assert title_ru["generated_text"] == DOCUMENT_TITLES["HIRE"]["ru"]
    assert title_kk["generator_version"] == GENERATOR_VERSION
    assert title_kk["source_fingerprint"]


def test_preamble_includes_legal_basis() -> None:
    out = generate_order_block(
        "preamble",
        "ru",
        {"order_type_code": "HIRE", "legal_basis_article": "33"},
    )
    assert "33" in out["generated_text"]
    assert "ПРИКАЗЫВАЮ" in out["generated_text"]


def test_hire_body_kk_ru() -> None:
    ctx = {
        "item_type_code": "HIRE",
        "employee_name": "Иванов И.И.",
        "effective_date": "2026-07-07",
        "org_unit_name": "Отдел кадров",
        "position_name": "Специалист",
        "rate": 1,
    }
    kk = generate_item_body("kk", ctx)
    ru = generate_item_body("ru", ctx)
    assert "Иванов" in kk["generated_text"]
    assert "қабылдансын" in kk["generated_text"]
    assert "Принять на работу" in ru["generated_text"]
    assert kk["source_fingerprint"] != ru["source_fingerprint"]


def test_personal_application_basis() -> None:
    fact = {
        "basis_type": "PERSONAL_APPLICATION",
        "subject_employee_name": "Иванов Иван",
    }
    ru = generate_basis_text("ru", fact)
    kk = generate_basis_text("kk", fact)
    assert "личное заявление" in ru["generated_text"]
    assert "жеке өтініш" in kk["generated_text"]


def test_missing_employee_uses_dash() -> None:
    ctx = {
        "item_type_code": "TERMINATION",
        "employee_name": None,
        "effective_date": "2026-07-07",
    }
    ru = generate_item_body("ru", ctx)
    assert "—" in ru["generated_text"]
    assert "Уволить" in ru["generated_text"]


def test_closing_may_be_empty() -> None:
    out = generate_order_block("closing", "kk", {"order_type_code": "HIRE"})
    assert out["generated_text"] == ""
    assert out["source_fingerprint"]
