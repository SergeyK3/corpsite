"""Read-only catalogue derived from the current personnel-order registry."""
from __future__ import annotations

from typing import Any

from app.db.models.personnel_orders import (
    BASIS_TYPE_PERSONAL_APPLICATION,
    ORDER_BLOCK_TYPE_PREAMBLE,
    ORDER_TYPE_COMPOSITE,
    ORDER_TYPE_RETURN_FROM_CHILDCARE_LEAVE,
    PERSONNEL_ORDER_ITEM_TYPE_CODES,
)
from app.services.personnel_orders_editorial.generators import (
    DOCUMENT_TITLES,
    generate_basis_text,
    generate_item_body,
    generate_order_block,
)


_PILOT_REQUIRED_FIELDS = [
    "ФИО сотрудника",
    "Должность на русском языке",
    "Должность на казахском языке",
    "Подразделение на русском языке",
    "Подразделение на казахском языке",
    "Ставка",
    "Дата выхода на работу",
    "Основание: личное заявление или другое подтверждённое основание",
]


def _pilot_detail() -> dict[str, Any]:
    """Return a display-only specimen built through the live editorial helpers."""
    previews: dict[str, dict[str, str]] = {}
    for locale in ("ru", "kk"):
        item = {
            "item_type_code": ORDER_TYPE_RETURN_FROM_CHILDCARE_LEAVE,
            "employee_name": "«ФИО сотрудника»" if locale == "ru" else "шартты адам",
            "effective_date": "2026-01-15",
            "org_unit_name": {"ru": "Подразделение", "kk": "Бөлімше"},
            "position_name": {"ru": "Должность", "kk": "Лауазым"},
            "rate": "1.0",
        }
        basis_text = generate_basis_text(
            locale,
            {
                "basis_type": BASIS_TYPE_PERSONAL_APPLICATION,
                "item_type_code": ORDER_TYPE_RETURN_FROM_CHILDCARE_LEAVE,
            },
        )["generated_text"]
        previews[locale] = {
            "title": DOCUMENT_TITLES[ORDER_TYPE_RETURN_FROM_CHILDCARE_LEAVE][locale],
            "preamble": generate_order_block(
                ORDER_BLOCK_TYPE_PREAMBLE,
                locale,
                {"order_type_code": ORDER_TYPE_RETURN_FROM_CHILDCARE_LEAVE},
            )["generated_text"],
            "directive": "ПРИКАЗЫВАЮ:" if locale == "ru" else "БҰЙЫРАМЫН:",
            "body": generate_item_body(locale, item)["generated_text"],
            "basis": f"Основание: {basis_text}" if locale == "ru" else f"Негіз: {basis_text}",
            "footer": (
                "С приказом ознакомлен(а): ___________________ [Фамилия И.]\n"
                "«___» ______________ 20___ г.\n"
                "Исполнитель: [Инициалы и фамилия исполнителя]"
                if locale == "ru"
                else "Бұйрықпен таныстым: ___________________ [Тегі А.]\n"
                "«___» ______________ 20___ ж.\n"
                "Орындаушы: [Орындаушының аты-жөні]"
            ),
        }
    return {
        "required_fields": _PILOT_REQUIRED_FIELDS,
        "additional_fields": [],
        "document_parts": [
            "Заголовок",
            "Преамбула",
            "ПРИКАЗЫВАЮ: / БҰЙЫРАМЫН:",
            "Распорядительный текст",
            "Основание",
            "Печатный подвал",
        ],
        "variables": [
            {"code": "employee.full_name", "label": "ФИО сотрудника"},
            {"code": "position.title_ru", "label": "Должность на русском языке"},
            {"code": "position.title_kk", "label": "Должность на казахском языке"},
            {"code": "org_unit.title_ru", "label": "Подразделение на русском языке"},
            {"code": "org_unit.title_kk", "label": "Подразделение на казахском языке"},
            {"code": "rate", "label": "Ставка"},
            {"code": "effective_date", "label": "Дата выхода на работу"},
            {"code": "basis", "label": "Подтверждённое основание"},
        ],
        "specialty_note": "Специальность хранится отдельно и в тело этого приказа не включается.",
        "previews": previews,
    }


_SUPPORT_LEVELS = {
    "HIRE": "SUPPORTED",
    "TRANSFER": "SUPPORTED",
    "TERMINATION": "SUPPORTED",
    "CONCURRENT_DUTY_START": "SUPPORTED",
    "CONCURRENT_DUTY_END": "SUPPORTED",
    "LEAVE.ANNUAL.GRANT": "SUPPORTED",
    ORDER_TYPE_RETURN_FROM_CHILDCARE_LEAVE: "SUPPORTED",
    "LEAVE.UNPAID.GRANT": "PARTIAL",
    "LEAVE.CHILDCARE.GRANT": "PARTIAL",
    "SUPPLEMENTARY_PAY": "PARTIAL",
}


def list_personnel_order_template_catalog() -> list[dict[str, Any]]:
    """Expose only registry-backed, non-personal template capabilities."""
    rows: list[dict[str, Any]] = []
    for type_code in PERSONNEL_ORDER_ITEM_TYPE_CODES:
        if type_code == ORDER_TYPE_COMPOSITE:
            continue
        titles = DOCUMENT_TITLES.get(type_code)
        if not titles:
            continue
        locales = [locale for locale in ("ru", "kk") if titles.get(locale)]
        rows.append({
            "type_code": type_code,
            "title_ru": titles["ru"],
            "title_kk": titles["kk"],
            "source": "BUILT_IN",
            "support_level": _SUPPORT_LEVELS.get(type_code, "NOT_IMPLEMENTED"),
            "supported_locales": locales,
            "uses_specialized_generator": type_code in DOCUMENT_TITLES,
            "is_pilot": type_code == ORDER_TYPE_RETURN_FROM_CHILDCARE_LEAVE,
            "required_fields": (
                _PILOT_REQUIRED_FIELDS
                if type_code == ORDER_TYPE_RETURN_FROM_CHILDCARE_LEAVE
                else []
            ),
            "notes": "Обязательные поля шаблона пока не формализованы; каталог не выводит данные конкретных приказов.",
            "pilot_detail": _pilot_detail() if type_code == ORDER_TYPE_RETURN_FROM_CHILDCARE_LEAVE else None,
        })
    return rows
