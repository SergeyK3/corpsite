import pytest
from fastapi import HTTPException

from app.services import personnel_type_headcount_report_service as service


def test_headcount_uses_active_register_rows_once_including_people_without_orders(monkeypatch):
    rows = [
        {"id": "1", "type_code": 1, "order_count": 0},
        {"id": "2", "type_code": 2, "manual_type_code": 2, "position_type_code": 1},
        {"id": "3", "type_code": 3},
        {"id": "4", "type_code": 4},
        {"id": "5", "type_code": None, "fio": "Иванова Анна", "org_unit": {"name": "Терапия"}, "position": {"name": "Специалист"}},
        {"id": "5", "type_code": None, "fio": "Иванова Анна", "org_unit": {"name": "Терапия"}, "position": {"name": "Специалист"}},
    ]
    calls = []

    def list_page(**kwargs):
        calls.append(kwargs)
        return {"items": rows[kwargs["offset"]:kwargs["offset"] + kwargs["limit"]], "total": len(rows)}

    monkeypatch.setattr(service, "list_employees", list_page)
    report = service.build_personnel_type_headcount_report(page_size=2)
    assert [group["count"] for group in report["groups"]] == [1, 1, 1, 1, 1]
    assert report["total"] == 5
    assert report["unknown_employees"] == [{
        "employee_id": 5, "full_name": "Иванова Анна",
        "org_unit_name": "Терапия", "position_name": "Специалист",
    }]
    assert len(report["unknown_employees"]) == report["groups"][-1]["count"]
    assert [call["offset"] for call in calls] == [0, 2, 4]
    assert all(call["status"] == "active" and call["sort"] == "id" for call in calls)


def test_manual_type_from_register_changes_only_its_employee_group(monkeypatch):
    employees = [
        {"id": "1", "type_code": 1, "position_type_code": 1, "manual_type_code": None},
        {"id": "2", "type_code": 1, "position_type_code": 1, "manual_type_code": None},
    ]
    monkeypatch.setattr(service, "list_employees", lambda **_kwargs: {"items": employees, "total": 2})
    assert [group["count"] for group in service.build_personnel_type_headcount_report()["groups"][:2]] == [2, 0]
    employees[0]["manual_type_code"] = 2
    employees[0]["type_code"] = 2
    assert [group["count"] for group in service.build_personnel_type_headcount_report()["groups"][:2]] == [1, 1]
    employees[0]["manual_type_code"] = None
    employees[0]["type_code"] = 1
    assert [group["count"] for group in service.build_personnel_type_headcount_report()["groups"][:2]] == [2, 0]


def test_headcount_route_keeps_existing_hr_report_guard(monkeypatch):
    from app.directory import personnel_reports_routes as routes

    def guard(user):
        if user["role"] != "hr":
            raise HTTPException(status_code=403)

    monkeypatch.setattr(routes, "require_personnel_admin_or_403", guard)
    monkeypatch.setattr(routes, "build_personnel_type_headcount_report", lambda: {"total": 5})
    with pytest.raises(HTTPException) as denied:
        routes.preview_personnel_type_headcount(user={"role": "employee"})
    assert denied.value.status_code == 403
    assert routes.preview_personnel_type_headcount(user={"role": "hr"}) == {"total": 5}
