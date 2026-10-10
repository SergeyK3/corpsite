"""Confirmed additional placement and explicit remaining total for duty cessation."""
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation

from app.services.personnel_order_concurrent_contract import LABELS
from app.services.personnel_orders_editorial.generators import _format_date_from, format_personnel_order_date_numeric

VARIABLES = ("employee.full_name", "employee.full_name_genitive_ru", "employee.full_name_ablative_kk", "effective_date", "concurrent.rate", "remaining.rate", "basis", "concurrent.position_genitive_ru", "concurrent.org_unit_genitive_ru", "concurrent.position_kk", "concurrent.org_unit_kk")
BODY_RU = "Прекратить с {{effective_date}} совмещение {{employee.full_name_genitive_ru}} должности {{concurrent.position_genitive_ru}} {{concurrent.org_unit_genitive_ru}} в объёме {{concurrent.rate}} ставки. (Всего: {{remaining.rate}} ставки)."
BODY_KK = "{{employee.full_name_ablative_kk}} {{effective_date}} бастап {{concurrent.org_unit_kk}} {{concurrent.position_kk}} қызметінен {{concurrent.rate}} ставкасы алынып тасталсын. (Барлығы: {{remaining.rate}} ставка)."


def cessation_values(data, effective_date):
    data = data if isinstance(data, Mapping) else {}
    labels = {key: value for key, value in LABELS.items() if key not in {"employee_dative_ru", "employee_dative_kk", "total_rate"}}
    labels.update(employee_genitive_ru="ФИО в родительном падеже (RU)", employee_ablative_kk="ФИО в исходном падеже (KK)", remaining_rate="общая ставка после прекращения совмещения")
    missing = [label for key, label in labels.items() if data.get(key) is None or not str(data[key]).strip()]
    if not effective_date:
        missing.append("дата прекращения совмещения")
    if missing:
        raise ValueError("Заполните данные прекращения совмещения: " + ", ".join(missing) + ".")
    try:
        rate, remaining = (Decimal(str(data[key]).replace(",", ".")) for key in ("rate", "remaining_rate"))
    except (InvalidOperation, ValueError):
        raise ValueError("Снимаемая и оставшаяся общая ставки должны быть числами.") from None
    if not rate.is_finite() or not remaining.is_finite() or rate <= 0 or remaining < 0:
        raise ValueError("Снимаемая ставка должна быть положительной; оставшаяся общая ставка — неотрицательной.")
    def decimal_text(value):
        result = format(value.normalize(), "f")
        return (result if "." in result else result + ".0").replace(".", ",")
    return {
        "employee.full_name_genitive_ru": str(data["employee_genitive_ru"]).strip(),
        "employee.full_name_ablative_kk": str(data["employee_ablative_kk"]).strip(),
        "effective_date.ru": format_personnel_order_date_numeric(str(effective_date)),
        "effective_date.kk": _format_date_from(str(effective_date), "kk"),
        "concurrent.rate": decimal_text(rate), "remaining.rate": decimal_text(remaining),
        **{f"concurrent.{key}": str(data[key]).strip() for key in ("position_genitive_ru", "org_unit_genitive_ru", "position_kk", "org_unit_kk")},
        "basis.ru": str(data["basis_ru"]).strip(), "basis.kk": str(data["basis_kk"]).strip(),
    }


# Synthetic preview only; this placement is not Turymov's personnel assignment.
PREVIEW_DATA = dict(position_ru="Врач", position_kk="дәрігері", org_unit_ru="Терапия", org_unit_kk="терапия бөлімшесінің", position_genitive_ru="врача", org_unit_genitive_ru="отделения терапии", employee_genitive_ru="Турымова Алибека Рапхатовича", employee_ablative_kk="Алибек Рапхатович Турымовтан", rate="0,5", remaining_rate="1,0", basis_ru="личное заявление", basis_kk="жеке өтініш")
_sample = cessation_values(PREVIEW_DATA, "2026-07-01")
PREVIEW = {locale: {key: _sample.get(f"{key}.{locale}", _sample.get(key, "")) for key in VARIABLES} for locale in ("ru", "kk")}
