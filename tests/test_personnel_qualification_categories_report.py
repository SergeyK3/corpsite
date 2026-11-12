from datetime import date, timedelta

import pytest
from fastapi import HTTPException

from app.services import personnel_qualification_categories_report_service as report_service


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self

    def all(self):
        return self.rows


class _Connection:
    def __init__(self, rows, pending_rows):
        self.rows = rows
        self.pending_rows = pending_rows

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        pass

    def execute(self, _statement, parameters=None):
        if "FROM public.personnel_order_items" in str(_statement):
            return _Rows(self.pending_rows)
        assert parameters == {"today": date(2026, 11, 12)}
        return _Rows(self.rows)


class _Engine:
    def __init__(self, rows, pending_rows=None):
        self.rows = rows
        self.pending_rows = pending_rows or []

    def connect(self):
        return _Connection(self.rows, self.pending_rows)


def test_status_boundaries_use_explicit_local_date():
    today = date(2026, 11, 12)
    assert report_service.category_status("2026-11-11", today)[0] == "EXPIRED"
    assert report_service.category_status("2026-11-12", today)[0] == "EXPIRING_SOON"
    assert report_service.category_status((today + timedelta(days=30)).isoformat(), today)[0] == "EXPIRING_SOON"
    assert report_service.category_status((today + timedelta(days=31)).isoformat(), today)[0] == "ACTIVE"
    assert report_service.category_status("", today) == ("NO_EXPIRY", None)
    assert report_service.category_status("invalid", today) == ("NO_EXPIRY", None)


def test_report_includes_every_active_employee_and_matches_card_profile():
    today = date(2026, 11, 12)
    card_profiles = {
        101: {"qualification_categories": [{"specialty": "Терапия", "category": "first", "assigned_at": "2024-01-01", "valid_until": "2026-12-13"}]},
        102: {"qualification_categories": [{"specialty": "Педиатрия", "category": "highest", "assigned_at": "2021-01-01", "valid_until": "2026-12-12"}]},
        103: {"qualification_categories": [{"specialty": "Хирургия", "category": "second", "assigned_at": "2020-01-01", "valid_until": "2026-11-11"}]},
        104: {"qualification_categories": [{"specialty": "Терапия", "category": "first", "assigned_at": "2024-01-01"}]},
        105: {"qualification_categories": []},
        106: {"qualification_categories": [
            {"specialty": "Терапия", "category": "first", "valid_until": "2026-11-01"},
            {"specialty": "Кардиология", "category": "highest", "valid_until": "2027-01-01"},
        ]},
    }

    rows = [
        {"employee_id": index, "person_id": index + 100, "full_name": f"Сотрудник {index}",
         "org_unit_id": 2 if index < 4 else 3, "org_unit_name": "А" if index < 4 else "Б",
         "metadata_profile": card_profiles[index + 100], "intake_profile": None}
        for index in range(1, 7)
    ]
    pending = [
        {"employee_id": 3, "name_ru": "Высшая", "category_code": "4", "legacy_category": None},
        {"employee_id": 2, "name_ru": "Незаполненный черновик", "category_code": None, "legacy_category": None},
        {"employee_id": 999, "name_ru": "Чужая", "category_code": "4", "legacy_category": None},
    ]
    result = report_service.build_personnel_qualification_categories_report(_Engine(rows, pending), today=today)
    assert len(result["employees"]) == 6
    assert [employee["categories"][0]["status"] for employee in result["employees"]] == [
        "ACTIVE", "EXPIRING_SOON", "EXPIRED", "NO_EXPIRY", "NO_CATEGORY", "EXPIRED"
    ]
    assert result["employees"][2]["categories"][0]["category_label"] == "Вторая"
    assert result["employees"][2]["categories"][0]["valid_until"] == "2026-11-11"
    assert result["employees"][2]["pending_categories"] == ["Высшая"]
    assert result["employees"][1]["pending_categories"] == []
    assert result["employees"][2]["categories"][0]["category_label"] == "Вторая"
    assert [category["specialty"] for category in result["employees"][5]["categories"]] == ["Терапия", "Кардиология"]
    assert result["employees"][0]["categories"][0]["category"] == card_profiles[101]["qualification_categories"][0]["category"]
    assert result["employees"][2]["categories"][0]["category"] == card_profiles[103]["qualification_categories"][0]["category"]
    assert all(category["document_status"] == "Наличие файла не установлено" for employee in result["employees"] for category in employee["categories"])


def test_report_route_keeps_personnel_admin_guard(monkeypatch):
    from app.directory import personnel_reports_routes as routes

    calls = []

    def guard(user):
        calls.append(user)
        if user["role"] == "employee":
            raise HTTPException(status_code=403)

    monkeypatch.setattr(routes, "require_personnel_admin_or_403", guard)
    monkeypatch.setattr(routes, "build_personnel_qualification_categories_report", lambda _engine: {"employees": []})
    with pytest.raises(HTTPException) as denied:
        routes.preview_personnel_qualification_categories(user={"role": "employee"})
    assert denied.value.status_code == 403
    assert routes.preview_personnel_qualification_categories(user={"role": "hr"}) == {"employees": []}
    assert calls == [{"role": "employee"}, {"role": "hr"}]
