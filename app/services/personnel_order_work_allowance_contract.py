"""Additional duties with an allowance and a confirmed total workload.

Uses existing concurrent/replacement JSON keys and existing template variables.
An absent additional rate is unknown, never a difference calculated from totals.
"""
from collections.abc import Mapping
import re

MODE = "WORK_ALLOWANCE"
BODY_RU = "Разрешить {{employee.full_name_dative_ru}} с {{effective_date}} выполнять по совместительству обязанности {{concurrent.position_genitive_ru}} {{concurrent.org_unit_genitive_ru}} с доплатой {{allowance.percent}}% от {{allowance.basis}}. (Общая занятость: {{total.rate}} ставки)."
BODY_KK = "{{employee.full_name_dative_kk}} {{effective_date}} бастап {{concurrent.org_unit_kk}} {{concurrent.position_kk}} қызметін қоса атқаруға рұқсат берілсін және {{allowance.basis}} {{allowance.percent}} % қосымша ақы төленсін. (Барлығы: {{total.rate}} ставка)."


def enabled(texts):
    tokens = set(re.findall(r"\{\{\s*([\w.]+)\s*\}\}", " ".join(str(texts.get("body_template_" + lang) or "") for lang in ("ru", "kk"))))
    return "allowance.percent" in tokens and "allowance.recipient" not in tokens and not any(token.startswith("replacement.") for token in tokens)


def validate_bodies(texts):
    for lang in ("ru", "kk"):
        tokens = set(re.findall(r"\{\{\s*([\w.]+)\s*\}\}", str(texts.get("body_template_" + lang) or "")))
        required = {"employee.full_name_dative_" + lang, "effective_date", "allowance.percent", "allowance.basis", "total.rate"}
        required.update({"concurrent.position_genitive_ru", "concurrent.org_unit_genitive_ru"} if lang == "ru" else {"concurrent.position_kk", "concurrent.org_unit_kk"})
        if required - tokens:
            raise ValueError("Отсутствуют подстановки дополнительной работы (" + lang.upper() + "): " + ", ".join(sorted(required - tokens)))


def values(concurrent, allowance, effective_date):
    from datetime import date
    from app.services.personnel_order_concurrent_contract import LABELS
    from app.services.personnel_order_replacement_contract import number, decimal_text
    from app.services.personnel_orders_editorial.generators import format_personnel_order_date_numeric, _format_date_from

    c = concurrent if isinstance(concurrent, Mapping) else {}
    a = allowance if isinstance(allowance, Mapping) else {}
    missing = [label for key, label in LABELS.items() if key != "rate" and not str(c.get(key) or "").strip()]
    missing += [label for key, label in {"allowance_percent": "процент доплаты", "allowance_basis_ru": "база доплаты (RU)", "allowance_basis_kk": "база доплаты (KK)"}.items() if not str(a.get(key) or "").strip()]
    if missing:
        raise ValueError("Заполните данные дополнительной работы: " + ", ".join(missing) + ".")
    try:
        start = date.fromisoformat(str(effective_date))
    except (ValueError, TypeError):
        raise ValueError("Укажите дату начала дополнительной работы.") from None
    total = number(c.get("total_rate"), "Общая занятость")
    percent = number(a.get("allowance_percent"), "Процент доплаты", maximum=100)
    rate = number(c["rate"], "Дополнительная ставка") if str(c.get("rate") if c.get("rate") is not None else "").strip() else None
    if rate is not None and total <= rate:
        raise ValueError("Общая занятость должна быть больше дополнительной ставки.")
    result = {"employee.full_name_dative_ru": str(c["employee_dative_ru"]).strip(), "employee.full_name_dative_kk": str(c["employee_dative_kk"]).strip(),
              "effective_date.ru": format_personnel_order_date_numeric(start), "effective_date.kk": _format_date_from(start, "kk"),
              "total.rate": decimal_text(total, fractional=True), "concurrent.rate": decimal_text(rate, fractional=True) if rate is not None else "",
              "allowance.percent": decimal_text(percent)}
    result.update({"concurrent." + key: str(c[key]).strip() for key in ("position_genitive_ru", "org_unit_genitive_ru", "position_kk", "org_unit_kk")})
    for lang in ("ru", "kk"):
        result["basis." + lang] = str(c["basis_" + lang]).strip()
        result["allowance.basis." + lang] = str(a["allowance_basis_" + lang]).strip()
    return result


def preview_context():
    from app.services.personnel_order_replacement_contract import SAMPLE_CONCURRENT
    data = values({**SAMPLE_CONCURRENT, "rate": None, "total_rate": "1.25"}, {"allowance_percent": 25, "allowance_basis_ru": "должностного оклада", "allowance_basis_kk": "лауазымдық айлық ақыдан"}, "2026-02-02")
    return {lang: {key.removesuffix("." + lang): value for key, value in data.items() if not key.endswith((".ru", ".kk")) or key.endswith("." + lang)} for lang in ("ru", "kk")}
