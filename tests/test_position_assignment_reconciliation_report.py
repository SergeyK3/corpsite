from datetime import date

import pytest
from fastapi import HTTPException

from app.services.position_assignment_reconciliation_report_service import (
    assemble_position_assignment_reconciliation,
)


def test_detail_counts_and_duplicate_employee_are_stable():
    positions = [
        {"position_id": 10, "name": "Врач", "type_code": 1, "type_name": "Врачи"},
        {"position_id": 11, "name": "  врач  ", "type_code": 1, "type_name": "Врачи"},
        {"position_id": 12, "name": "Медсестра", "type_code": 2, "type_name": "Медсёстры"},
    ]
    assignments = [
        {"position_id": 10, "employee_id": 101, "full_name": "Анна Иванова", "org_unit_name": "Отделение А"},
        {"position_id": 10, "employee_id": 101, "full_name": "Анна Иванова", "org_unit_name": "Отделение Б"},
        {"position_id": 11, "employee_id": 102, "full_name": "Иван Петров", "org_unit_name": "Отделение В"},
    ]

    report = assemble_position_assignment_reconciliation(positions, assignments, as_of=date(2026, 11, 13))

    assert report["metrics"]["assignment_names"] == len(report["assignment_names"]) == 1
    assert report["metrics"]["catalog_positions"] == len(report["catalog_positions"]) == 3
    assert report["metrics"]["catalog_without_active_assignments"] == len(report["catalog_without_active_assignments"]) == 1
    assert report["metrics"]["assignment_names_missing_in_catalog"] is None
    assert report["independent_assignment_name_available"] is False
    assert report["position_active_flag_available"] is False

    name_group = report["assignment_names"][0]
    assert name_group["employee_count"] == len(name_group["employees"]) == 2
    assert name_group["possible_duplicate_ids"] == [10, 11]
    assert len(name_group["positions"]) == 2
    first_position = next(p for p in report["catalog_positions"] if p["position_id"] == 10)
    assert first_position["employee_count"] == len(first_position["employees"]) == 1
    assert first_position["employees"][0]["departments"] == ["Отделение А", "Отделение Б"]
    assert report["catalog_without_active_assignments"][0]["position_id"] == 12


def test_route_keeps_existing_hr_report_permission(monkeypatch):
    from app.directory import personnel_reports_routes as routes

    def guard(user):
        if user["role"] != "hr":
            raise HTTPException(status_code=403)

    monkeypatch.setattr(routes, "require_personnel_admin_or_403", guard)
    monkeypatch.setattr(routes, "build_position_assignment_reconciliation", lambda _engine: {"ok": True})
    with pytest.raises(HTTPException) as denied:
        routes.position_assignment_reconciliation(user={"role": "employee"})
    assert denied.value.status_code == 403
    assert routes.position_assignment_reconciliation(user={"role": "hr"}) == {"ok": True}
