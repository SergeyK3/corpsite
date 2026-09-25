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
from app.services.personnel_order_action_classifier import classify_personnel_order_action


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


def test_preamble_keeps_type_specific_legal_wording_and_moves_verb_to_next_line() -> None:
    assert generate_order_block(
        "preamble", "ru", {"order_type_code": "HIRE", "legal_basis_article": "33"},
    )["generated_text"] == "В соответствии со статьёй 33 Трудового кодекса Республики Казахстан\nПРИКАЗЫВАЮ:"
    assert generate_order_block(
        "preamble", "ru", {"order_type_code": "TRANSFER", "legal_basis_article": "38"},
    )["generated_text"] == "В соответствии со статьёй 38 Трудового кодекса Республики Казахстан\nПРИКАЗЫВАЮ:"
    assert generate_order_block(
        "preamble", "kk", {"order_type_code": "TERMINATION", "legal_basis_article": "57"},
    )["generated_text"] == "Қазақстан Республикасының Еңбек кодексінің 57 бабына сәйкес\nБҰЙЫРАМЫН:"


def test_supplementary_pay_generated_text_is_bilingual_and_does_not_invent_terms() -> None:
    ctx = {
        "item_type_code": "SUPPLEMENTARY_PAY",
        "employee_name": "Иванов И.И.",
        "effective_date": "2026-07-07",
        "org_unit_name": "Кардиология",
        "position_name": "Врач",
        "rate": "0.75",
    }
    ru = generate_item_body("ru", ctx)["generated_text"]
    kk = generate_item_body("kk", ctx)["generated_text"]

    assert "сверки с DOCX" in ru
    assert "DOCX-пен салыстыруды" in kk
    for forbidden in ("0.75", "2026", "Кардиология", "Врач"):
        assert forbidden not in ru
        assert forbidden not in kk


def test_return_from_childcare_leave_is_bilingual_fail_closed_and_does_not_invent_terms() -> None:
    assert classify_personnel_order_action("Выход из отпуска по уходу за ребёнком") == "RETURN_FROM_CHILDCARE_LEAVE"
    assert classify_personnel_order_action("Выйти на работу после отпуска по уходу за ребёнком") == "RETURN_FROM_CHILDCARE_LEAVE"
    assert classify_personnel_order_action("Бала күтіміне байланысты демалыстан шығу") == "RETURN_FROM_CHILDCARE_LEAVE"
    assert classify_personnel_order_action("Вышла на работу") is None

    ctx = {
        "item_type_code": "RETURN_FROM_CHILDCARE_LEAVE",
        "employee_name": "Иванова И.И.",
        "effective_date": "2099-01-02",
        "org_unit_name": {"ru": "Не включать", "kk": "Қоспау"},
        "position_name": {"ru": "Не включать", "kk": "Қоспау"},
        "rate": "9.99",
        "basis": {"number": "999"},
        "education": "Тестовое образование",
        "certificate": "Тестовый сертификат",
        "tenure": "Тестовый стаж",
    }
    ru = generate_item_body("ru", ctx)["generated_text"]
    kk = generate_item_body("kk", ctx)["generated_text"]

    assert DOCUMENT_TITLES["RETURN_FROM_CHILDCARE_LEAVE"] == {
        "ru": "О выходе на работу из отпуска по уходу за ребёнком",
        "kk": "Бала күтіміне байланысты демалыстан жұмысқа шығу туралы",
    }
    assert generate_order_block(
        "preamble", "ru", {"order_type_code": "RETURN_FROM_CHILDCARE_LEAVE", "legal_basis_article": "999"}
    )["generated_text"] == "В соответствии с Трудовым кодексом Республики Казахстан\nПРИКАЗЫВАЮ:"
    assert generate_order_block(
        "preamble", "kk", {"order_type_code": "RETURN_FROM_CHILDCARE_LEAVE"}
    )["generated_text"] == "Қазақстан Республикасының Еңбек кодексіне сәйкес\nБҰЙЫРАМЫН:"
    assert "выходом из отпуска по уходу за ребёнком" in ru
    assert "бала күтіміне байланысты демалыстан" in kk
    for forbidden in (
        "9.99", "Не включать", "999",
        "Тестовое образование", "Тестовый сертификат", "Тестовый стаж",
    ):
        assert forbidden not in ru
        assert forbidden not in kk


def test_childcare_grant_is_distinct_from_return_for_ru_and_kk() -> None:
    assert classify_personnel_order_action("Предоставить отпуск по уходу за ребёнком") == "LEAVE.CHILDCARE.GRANT"
    assert classify_personnel_order_action("Бала күтіміне байланысты демалыс берілсін") == "LEAVE.CHILDCARE.GRANT"
    assert classify_personnel_order_action("Вышла на работу") is None
    assert "ребёнком" in generate_order_block("title", "ru", {"order_type_code": "LEAVE.CHILDCARE.GRANT"})["generated_text"]
    assert "бала" in generate_order_block("title", "kk", {"order_type_code": "LEAVE.CHILDCARE.GRANT"})["generated_text"].casefold()
    ru = generate_item_body("ru", {"item_type_code": "LEAVE.CHILDCARE.GRANT", "employee_name": "Иванова", "leave_start": "2026-01-01", "leave_end": "2026-01-02"})["generated_text"]
    kk = generate_item_body("kk", {"item_type_code": "LEAVE.CHILDCARE.GRANT", "employee_name": "Иванова", "leave_start": "2026-01-01", "leave_end": "2026-01-02"})["generated_text"]
    assert not ru.endswith("Стаж работы ещё не определён.")
    assert not kk.endswith("Жұмыс өтілі әлі анықталмаған.")


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
    assert not ru["generated_text"].endswith("Стаж работы ещё не определён.")


def test_return_from_childcare_leave_uses_confirmed_presentation_context() -> None:
    ctx = {
        "item_type_code": "RETURN_FROM_CHILDCARE_LEAVE",
        "employee_name": "Иванова Алия Сериковна",
        "effective_date": "2026-08-05",
        "position_name": {"ru": "руководитель отдела кадров", "kk": "кадрлар бөлімінің басшысы"},
        "org_unit_name": {"ru": "отдел кадров", "kk": "кадрлар бөлімі"},
    }
    assert generate_item_body("ru", ctx)["generated_text"] == (
        "Разрешить сотруднику Иванова Алия Сериковна, должность: руководитель отдела кадров "
        "(отдел кадров) приступить к работе в связи с выходом из отпуска по уходу за ребёнком с 5 августа 2026 года."
    )
    kk = generate_item_body("kk", ctx)["generated_text"]
    assert "кадрлар бөлімінің басшысы (кадрлар бөлімі)" in kk
    assert "руководитель отдела кадров" not in kk
    assert "2026 жылғы 5 тамыздан бастап" in kk


def test_kazakh_return_start_date_declines_every_month() -> None:
    months = (
        "қаңтардан", "ақпаннан", "наурыздан", "сәуірден",
        "мамырдан", "маусымнан", "шілдеден", "тамыздан",
        "қыркүйектен", "қазаннан", "қарашадан", "желтоқсаннан",
    )
    for month, expected_month in enumerate(months, start=1):
        text = generate_item_body("kk", {
            "item_type_code": "RETURN_FROM_CHILDCARE_LEAVE",
            "employee_name": "Иванова",
            "effective_date": f"2026-{month:02d}-05",
            "position_name": {"kk": "лауазым"},
            "org_unit_name": {"kk": "бөлімше"},
        })["generated_text"]
        assert f"2026 жылғы 5 {expected_month} бастап" in text


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


def test_position_dictionary_translates_only_approved_pair_and_preserves_saved_kk() -> None:
    base = {
        "item_type_code": "HIRE",
        "employee_name": "Иванова И.И.",
        "effective_date": "2026-07-07",
        "org_unit_name": "Отделение",
        "rate": 1,
    }
    translated = generate_item_body("kk", {**base, "position_name": "Медсестра — анестезистка"})
    preserved = generate_item_body(
        "kk",
        {**base, "position_name": {"ru": "медсестра-анестезистка", "kk": "сақталған атау"}},
    )
    assert "анестезист мейіргері" in translated["generated_text"]
    assert "сақталған атау" in preserved["generated_text"]


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
