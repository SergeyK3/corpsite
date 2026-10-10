"""Explicit bilingual destination and basis for a manual TRANSFER template."""
from decimal import Decimal, InvalidOperation
from collections.abc import Mapping

LABELS = {
    "position_ru": "новая должность (RU)", "position_kk": "новая должность (KK)",
    "org_unit_ru": "новое подразделение (RU)", "org_unit_kk": "новое подразделение (KK)",
    "rate": "ставка после перевода", "basis_ru": "основание перевода (RU)", "basis_kk": "основание перевода (KK)",
}

def transfer_values(data):
    data = data if isinstance(data, Mapping) else {}
    missing = [label for key, label in LABELS.items() if data.get(key) is None or not str(data[key]).strip()]
    if missing:
        raise ValueError("Заполните данные перевода: " + ", ".join(missing) + ".")
    try:
        rate = Decimal(str(data["rate"]))
    except (InvalidOperation, ValueError):
        raise ValueError("Ставка после перевода должна быть положительным числом.") from None
    if not rate.is_finite() or rate <= 0:
        raise ValueError("Ставка после перевода должна быть положительным числом.")
    return {
        "position.title_ru": str(data["position_ru"]).strip(), "position.title_kk": str(data["position_kk"]).strip(),
        "org_unit.title_ru": str(data["org_unit_ru"]).strip(), "org_unit.title_kk": str(data["org_unit_kk"]).strip(),
        "rate": format(rate.normalize(), "f"), "basis.ru": str(data["basis_ru"]).strip(), "basis.kk": str(data["basis_kk"]).strip(),
    }
