"""Read-only catalogue derived from the current personnel-order registry."""
from __future__ import annotations

from typing import Any

from app.db.models.personnel_orders import (
    ORDER_TYPE_COMPOSITE,
    ORDER_TYPE_RETURN_FROM_CHILDCARE_LEAVE,
    PERSONNEL_ORDER_ITEM_TYPE_CODES,
)
from app.services.personnel_orders_editorial.generators import DOCUMENT_TITLES


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
            "required_fields": [],
            "notes": "Обязательные поля шаблона пока не формализованы; каталог не выводит данные конкретных приказов.",
        })
    return rows
