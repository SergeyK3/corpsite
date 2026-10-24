"""Excel representation of the five columns in the staff roster."""
from typing import Any, Iterable

from app.services.table_export import build_table_workbook


def staff_status_label(item: dict[str, Any]) -> str:
    """Keep labels consistent with employees/_lib/employeeStatus.ts."""
    raw = str(item.get("status") or "").strip().lower()
    if raw == "applicant" or item.get("record_kind") == "applicant":
        return "Заявитель"
    if raw == "archived":
        return "Архив"
    if raw == "active":
        active = True
    elif raw == "inactive":
        active = False
    elif isinstance(item.get("is_active"), bool):
        active = item["is_active"]
    elif isinstance(item.get("isActive"), bool):
        active = item["isActive"]
    elif "date_to" in item:
        active = item["date_to"] is None
    elif "dateTo" in item:
        active = item["dateTo"] is None
    else:
        active = True
    if active:
        return "Работает"
    if "увол" in raw or raw == "fired":
        return "Уволен"
    date_to = item.get("date_to", item.get("dateTo"))
    return "Завершён" if date_to is not None and str(date_to).strip() else "Не работает"


def build_staff_workbook(items: Iterable[dict[str, Any]]) -> bytes:
    rows = []
    for item in items:
        def first(*values):
            return next((value for value in values if value is not None), "—")

        label = staff_status_label(item)
        if (item.get("termination") or {}).get("verification_status") == "UNVERIFIED":
            label += "; Сведения не верифицированы"
        rows.append((
            first(item.get("fio"), item.get("full_name"), item.get("fullName"), item.get("name"), item.get("title")),
            first(item.get("position_name"), item.get("positionName"), (item.get("position") or {}).get("name"), (item.get("position") or {}).get("title")),
            first(item.get("department_name"), item.get("departmentName"), (item.get("department") or {}).get("name"), (item.get("org_unit") or {}).get("name")),
            first(item.get("employment_rate"), item.get("rate")),
            label,
        ))
    return build_table_workbook(("ФИО", "Должность", "Отделение", "Ставка", "Статус"), rows, "Персонал", (42, 38, 45, 12, 30))
