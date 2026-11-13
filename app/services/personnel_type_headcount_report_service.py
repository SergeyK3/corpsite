"""Read-only personnel type headcount from the active personnel register."""
from __future__ import annotations

from typing import Any

from app.services.directory_service import list_employees


TYPE_NAMES = (
    (1, "Врачи"),
    (2, "Медсёстры и фельдшеры"),
    (3, "Санитарки"),
    (4, "Прочий персонал"),
    (None, "Тип не указан"),
)


def build_personnel_type_headcount_report(*, page_size: int = 1000) -> dict[str, Any]:
    """Use the register's active filter and its live assignment type projection."""
    if page_size < 1:
        raise ValueError("page_size must be positive")

    counts: dict[int | None, int] = {code: 0 for code, _ in TYPE_NAMES}
    unknown_employees: list[dict[str, Any]] = []
    seen_employee_ids: set[int] = set()
    offset = 0
    while True:
        page = list_employees(
            status="active", q=None, department_id=None, position_id=None,
            limit=page_size, offset=offset, sort="id", order="asc",
        )
        items = page["items"]
        for employee in items:
            employee_id = int(employee["id"])
            if employee_id in seen_employee_ids:
                continue
            seen_employee_ids.add(employee_id)
            raw_type = employee.get("type_code")
            type_code = int(raw_type) if raw_type is not None else None
            group_code = type_code if type_code in counts else None
            counts[group_code] += 1
            if group_code is None:
                unknown_employees.append({
                    "employee_id": employee_id,
                    "full_name": employee.get("fio"),
                    "org_unit_name": (employee.get("org_unit") or {}).get("name"),
                    "position_name": (employee.get("position") or {}).get("name"),
                })
        offset += len(items)
        if not items or offset >= int(page["total"]):
            break

    groups = [
        {"code": code, "name": name, "count": counts[code]}
        for code, name in TYPE_NAMES
    ]
    return {
        "report_code": "personnel_type_headcount",
        "groups": groups,
        "unknown_employees": unknown_employees,
        "total": sum(counts.values()),
    }
