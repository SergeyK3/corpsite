# tests/test_wp_po_edit_002_generators.py
"""Unit tests for editorial text generators (WP-PO-EDIT-002)."""
from __future__ import annotations

from app.db.engine import engine
from app.services.personnel_orders_editorial.constants import GENERATOR_VERSION
from app.services.personnel_orders_editorial.generators import (
    DOCUMENT_TITLES,
    generate_basis_text,
    generate_item_body,
    generate_order_block,
)
from app.services.personnel_orders_editorial.mapper import build_item_ctx
from app.services.personnel_orders_editorial.repository import load_items


def test_document_titles_kk_ru() -> None:
    assert DOCUMENT_TITLES["HIRE"]["kk"]
    assert DOCUMENT_TITLES["HIRE"]["ru"]
    title_kk = generate_order_block("title", "kk", {"order_type_code": "HIRE"})
    title_ru = generate_order_block("title", "ru", {"order_type_code": "HIRE"})
    assert title_kk["generated_text"] == DOCUMENT_TITLES["HIRE"]["kk"]
    assert title_ru["generated_text"] == DOCUMENT_TITLES["HIRE"]["ru"]
    assert title_kk["generator_version"] == GENERATOR_VERSION
    assert title_kk["source_fingerprint"]


def test_unpaid_leave_titles_kk_ru() -> None:
    ru = generate_order_block("title", "ru", {"order_type_code": "LEAVE.UNPAID.GRANT"})
    kk = generate_order_block("title", "kk", {"order_type_code": "LEAVE.UNPAID.GRANT"})
    assert ru["generated_text"] == "О предоставлении отпуска без сохранения заработной платы"
    assert kk["generated_text"] == "Жалақы сақталмайтын демалыс беру туралы"


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


def test_closing_has_default_responsibility_text() -> None:
    kk = generate_order_block("closing", "kk", {"order_type_code": "HIRE"})
    ru = generate_order_block("closing", "ru", {"order_type_code": "HIRE"})
    assert kk["generated_text"]
    assert ru["generated_text"]
    assert "бақылау" in kk["generated_text"]
    assert "Контроль" in ru["generated_text"]
    assert kk["source_fingerprint"]


def test_annual_leave_body_uses_saved_payload_for_both_locales() -> None:
    ctx = build_item_ctx(
        {
            "item_type_code": "LEAVE.ANNUAL.GRANT",
            "effective_date": "2026-08-03",
            "payload": {
                "org_unit_name": "Отдел кадров",
                "position_name": "Руководитель отдела кадров",
                "leave_start": "2026-08-03",
                "leave_end": "2026-08-26",
                "leave_days": 24,
                "work_periods": [
                    {"start": "2024-06-01", "end": "2025-05-31", "days": 10},
                    {"start": "2025-06-01", "end": "2026-05-31", "days": 14},
                ],
                "basis": {
                    "kind": "PERSONAL_APPLICATION",
                    "date": "2026-07-20",
                    "number": "15",
                },
                "vacation_benefit_applicable": True,
                "vacation_benefit_rule": "один должностной оклад",
            },
        },
        "Иванов И.И.",
    )

    ru = generate_item_body("ru", ctx)
    kk = generate_item_body("kk", ctx)

    for value in ("Иванов И.И.", "Руководитель отдела кадров", "Отдел кадров", "24", "10", "14", "15"):
        assert value in ru["generated_text"]
    for value in ("Иванов И.И.", "Руководитель отдела кадров", "Отдел кадров", "24", "10", "14", "15"):
        assert value in kk["generated_text"]
    assert "Пособие к отпуску" in ru["generated_text"]
    assert "Демалыс жәрдемақысы" in kk["generated_text"]
    assert "Основание: личное заявление" in ru["generated_text"]
    assert "Негіз:" in kk["generated_text"]
    assert ru["source_fingerprint"] != kk["source_fingerprint"]


def test_annual_leave_body_falls_back_to_saved_employee_snapshot() -> None:
    ctx = build_item_ctx(
        {
            "item_type_code": "LEAVE.ANNUAL.GRANT",
            "payload": {
                "leave_start": "2026-08-03",
                "leave_end": "2026-08-12",
                "leave_days": 10,
                "work_periods": [{"start": "2025-06-01", "end": "2026-05-31", "days": 10}],
                "basis": {"kind": "PERSONAL_APPLICATION", "date": "2026-07-20"},
            },
            "snapshot_org_unit_name": "Отдел кадров",
            "snapshot_position_name": "Руководитель отдела кадров",
        },
        "Иванов И.И.",
    )

    kk = generate_item_body("kk", ctx)
    assert "Отдел кадров" in kk["generated_text"]
    assert "Руководитель отдела кадров" in kk["generated_text"]
    assert "—" not in kk["generated_text"]


def test_load_items_executes_snapshot_join_without_ambiguous_columns() -> None:
    """Regression: the snapshot JOIN must qualify every personnel item column."""
    with engine.connect() as conn:
        rows = load_items(conn, 0)
    assert rows == []


def test_annual_leave_body_reads_legacy_single_work_period() -> None:
    body = generate_item_body(
        "ru",
        {
            "item_type_code": "LEAVE.ANNUAL.GRANT",
            "employee_name": "Иванов И.И.",
            "leave_start": "2026-08-03",
            "leave_end": "2026-08-12",
            "leave_days": 10,
            "work_period_start": "2025-06-01",
            "work_period_end": "2026-05-31",
            "work_period_days": 10,
            "basis": {"kind": "PERSONAL_APPLICATION", "date": "2026-07-20"},
        },
    )
    assert "1 июня 2025 года" in body["generated_text"]
    assert "31 мая 2026 года" in body["generated_text"]
    assert "10 календарных дней" in body["generated_text"]


def test_unpaid_leave_body_uses_payload_and_snapshot_in_both_locales() -> None:
    ctx = build_item_ctx(
        {
            "item_type_code": "LEAVE.UNPAID.GRANT",
            "payload": {
                "leave_start": "2026-08-03",
                "leave_end": "2026-08-12",
                "leave_days": 10,
                "basis": {
                    "kind": "PERSONAL_APPLICATION",
                    "date": "2026-07-20",
                    "number": "15",
                },
            },
            "snapshot_org_unit_name": "Отдел кадров",
            "snapshot_position_name": "Руководитель отдела кадров",
        },
        "Иванов И.И.",
    )
    ru = generate_item_body("ru", ctx)
    kk = generate_item_body("kk", ctx)
    for text in (ru["generated_text"], kk["generated_text"]):
        for value in ("Иванов И.И.", "Отдел кадров", "Руководитель отдела кадров", "10", "15"):
            assert value in text
    assert "без сохранения заработной платы" in ru["generated_text"]
    assert "жалақы сақталмайтын" in kk["generated_text"]


def test_unpaid_leave_basis_omits_missing_date_and_number_cleanly() -> None:
    body = generate_item_body(
        "ru",
        {
            "item_type_code": "LEAVE.UNPAID.GRANT",
            "employee_name": "Иванов И.И.",
            "org_unit_name": "Отдел кадров",
            "position_name": "Специалист",
            "leave_start": "2026-08-03",
            "leave_end": "2026-08-12",
            "leave_days": 10,
            "basis": {"kind": "PERSONAL_APPLICATION"},
        },
    )
    assert "Основание: личное заявление." in body["generated_text"]
    assert "от —" not in body["generated_text"]
    assert "…" not in body["generated_text"]
