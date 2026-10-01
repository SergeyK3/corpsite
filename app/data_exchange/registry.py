"""Explicit scenario registry; no dynamic table/import selection."""
from __future__ import annotations

from app.data_exchange.category_scenario import ControlListCategoriesScenario
from app.data_exchange.order_scenario import PersonnelOrdersReviewScenario
from app.data_exchange.vacation_scenario import PersonnelVacationRegisterReviewScenario


# Discoverable specifications include deliberately unavailable legacy adapters.
# They are shown as such rather than accepting a workbook whose legacy-only
# rules have not been separated from a local script.
CATALOG_ONLY = (
    {
        "code": "EMPLOYEE_REFERENCE_EXPORT",
        "schema_version": "EMPLOYEE_REFERENCE_XLSX_V1",
        "label": "Экспорт эталонного списка сотрудников",
        "available": True,
        "export_only": True,
    },
)


def scenarios() -> dict[str, object]:
    order = PersonnelOrdersReviewScenario()
    categories = ControlListCategoriesScenario()
    vacation = PersonnelVacationRegisterReviewScenario()
    return {categories.code: categories, order.code: order, vacation.code: vacation}


def get_scenario(code: str):
    return scenarios().get(str(code or "").strip().upper())


def catalog() -> list[dict[str, object]]:
    items = [
        {"code": value.code, "schema_version": value.schema_version, "label": value.label,
         "available": True, "export_only": False, "accepted_suffixes": list(value.accepted_suffixes),
         "max_bytes": value.max_bytes, "atomic_apply": value.atomic_apply}
        for value in scenarios().values()
    ]
    return [*items, *CATALOG_ONLY]
