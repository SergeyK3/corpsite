"""Explicit additional placement for concurrent-duty template rendering."""
from decimal import Decimal, InvalidOperation
from collections.abc import Mapping
from app.services.personnel_orders_editorial.generators import _format_date_from, format_personnel_order_date_numeric

VARIABLES = ("employee.full_name", "employee.full_name_dative_ru", "employee.full_name_dative_kk", "effective_date", "concurrent.rate", "total.rate", "basis", "concurrent.position_genitive_ru", "concurrent.org_unit_genitive_ru", "concurrent.position_kk", "concurrent.org_unit_kk")
LABELS = {"position_ru":"дополнительная должность (RU)", "position_kk":"дополнительная должность (KK)", "org_unit_ru":"дополнительное подразделение (RU)", "org_unit_kk":"дополнительное подразделение (KK)", "position_genitive_ru":"дополнительная должность в родительном падеже (RU)", "org_unit_genitive_ru":"дополнительное подразделение в родительном падеже (RU)", "employee_dative_ru":"ФИО в дательном падеже (RU)", "employee_dative_kk":"ФИО в дательном падеже (KK)", "rate":"дополнительная ставка", "total_rate":"общая ставка", "basis_ru":"основание (RU)", "basis_kk":"основание (KK)"}

def concurrent_values(data, effective_date):
    data = data if isinstance(data, Mapping) else {}
    missing = [label for key,label in LABELS.items() if data.get(key) is None or not str(data[key]).strip()]
    if not effective_date: missing.append("дата начала совмещения")
    if missing: raise ValueError("Заполните данные совмещения: " + ", ".join(missing) + ".")
    try:
        rate, total = (Decimal(str(data[key])) for key in ("rate", "total_rate"))
    except (InvalidOperation, ValueError):
        raise ValueError("Дополнительная и общая ставки должны быть положительными числами.") from None
    if not rate.is_finite() or not total.is_finite() or rate <= 0 or total <= rate:
        raise ValueError("Дополнительная ставка должна быть положительной; общая ставка должна быть больше дополнительной.")
    return {"employee.full_name_dative_ru":str(data["employee_dative_ru"]).strip(), "employee.full_name_dative_kk":str(data["employee_dative_kk"]).strip(),
        "effective_date.ru":format_personnel_order_date_numeric(str(effective_date)), "effective_date.kk":_format_date_from(str(effective_date),"kk"),
        "concurrent.rate":format(rate.normalize(),"f"), "total.rate":format(total.normalize(),"f"),
        "concurrent.position_genitive_ru":str(data["position_genitive_ru"]).strip(), "concurrent.org_unit_genitive_ru":str(data["org_unit_genitive_ru"]).strip(),
        "concurrent.position_kk":str(data["position_kk"]).strip(), "concurrent.org_unit_kk":str(data["org_unit_kk"]).strip(),
        "basis.ru":str(data["basis_ru"]).strip(), "basis.kk":str(data["basis_kk"]).strip()}

PREVIEW = {
 "ru":{"employee.full_name_dative_ru":"Иванову Ивану Ивановичу", "effective_date":"21.05.2026", "concurrent.rate":"0.5", "total.rate":"1.5", "concurrent.position_genitive_ru":"врача", "concurrent.org_unit_genitive_ru":"отделения терапии", "basis":"личное заявление"},
 "kk":{"employee.full_name_dative_kk":"Иван Иванович Ивановқа", "effective_date":"2026 жылғы 21 мамырдан", "concurrent.rate":"0.5", "total.rate":"1.5", "concurrent.position_kk":"дәрігер", "concurrent.org_unit_kk":"терапия бөлімшесінің", "basis":"жеке өтініш"},
}
