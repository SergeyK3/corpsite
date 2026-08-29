from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.directory import personnel_reports_routes
from app.main import app
from app.services.hr_event_registry import EVENT_CATEGORY_LEAVE, HR_EVENT_REGISTRY
from app.services.personnel_orders_summary_report_service import (
    CATEGORY_HIRE,
    CATEGORY_LEAVE,
    CATEGORY_OTHER,
    CATEGORY_TERMINATION,
    CATEGORY_TRANSFER,
    ORDER_CATEGORY_BY_TYPE,
    PersonnelOrdersSummaryFilterError,
    build_personnel_orders_summary,
    classify_order_category,
)


class _MappingsResult:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self

    def all(self):
        return self.rows


class _Connection:
    def __init__(self, rows):
        self.rows = rows
        self.sql = ""
        self.params = {}

    def execute(self, statement, params):
        self.sql = str(statement)
        self.params = params
        return _MappingsResult(self.rows)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class _Engine:
    def __init__(self, rows):
        self.connection = _Connection(rows)

    def connect(self):
        return self.connection


def _row(
    order_id: int,
    order_type_code: str,
    *,
    number: str | None = None,
    order_date: date | None = None,
    item_types: list[str] | None = None,
    employees: list[str] | None = None,
    departments: list[str] | None = None,
    status: str = "SIGNED",
):
    return {
        "order_id": order_id,
        "order_number": number,
        "order_date": order_date,
        "order_type_code": order_type_code,
        "status": status,
        "item_type_codes": item_types or [order_type_code],
        "employee_names": employees or [],
        "department_names": departments or [],
    }


def _build(rows, **filters):
    return build_personnel_orders_summary(
        _Engine(rows),
        generated_at=datetime(2026, 8, 29, 9, 30, tzinfo=timezone.utc),
        **filters,
    )


def test_always_returns_five_categories_in_business_order_and_matching_totals():
    report = _build(
        [
            _row(1, "HIRE", number="1", order_date=date(2026, 1, 1)),
            _row(2, "TERMINATION", order_date=date(2026, 1, 2)),
            _row(3, "UNKNOWN", number="3"),
        ]
    )

    assert [category["name"] for category in report["categories"]] == [
        "Приём",
        "Увольнение",
        "Перевод",
        "Отпуска",
        "Прочие",
    ]
    assert [category["count"] for category in report["categories"]] == [1, 1, 0, 0, 1]
    assert report["total_count"] == 3
    assert report["total_incomplete_count"] == 2
    assert report["total_count"] == sum(item["count"] for item in report["categories"])


def test_order_with_multiple_employees_is_counted_once_and_keeps_compact_details():
    report = _build(
        [
            _row(
                10,
                "HIRE",
                number="10",
                order_date=date(2026, 2, 1),
                employees=["Абдулов А.А.", "Бекова Б.Б."],
                departments=["Терапия", "Хирургия"],
            ),
            # Defensive duplicate produced by a hypothetical join must not change totals.
            _row(
                10,
                "HIRE",
                number="10",
                order_date=date(2026, 2, 1),
                employees=["Абдулов А.А.", "Бекова Б.Б."],
                departments=["Терапия", "Хирургия"],
            ),
        ]
    )

    category = report["categories"][0]
    assert category["count"] == report["total_count"] == 1
    assert category["orders"][0]["employee_names"] == ["Абдулов А.А.", "Бекова Б.Б."]


@pytest.mark.parametrize(
    ("number", "order_date", "expected"),
    [
        (None, date(2026, 1, 1), 1),
        ("1", None, 1),
        (None, None, 1),
        ("1", date(2026, 1, 1), 0),
    ],
)
def test_incomplete_count_uses_missing_official_number_or_official_date_once(
    number, order_date, expected
):
    report = _build([_row(1, "HIRE", number=number, order_date=order_date)])

    assert report["categories"][0]["incomplete_count"] == expected
    assert report["total_incomplete_count"] == expected


def test_all_canonical_hire_termination_transfer_and_leave_codes_are_classified():
    assert classify_order_category("HIRE", []) == CATEGORY_HIRE
    assert classify_order_category("TERMINATION", []) == CATEGORY_TERMINATION
    assert classify_order_category("TRANSFER", []) == CATEGORY_TRANSFER
    leave_codes = {
        code for code, definition in HR_EVENT_REGISTRY.items() if definition.category == EVENT_CATEGORY_LEAVE
    }
    assert leave_codes
    assert all(ORDER_CATEGORY_BY_TYPE[code] == CATEGORY_LEAVE for code in leave_codes)
    assert all(classify_order_category(code, []) == CATEGORY_LEAVE for code in leave_codes)


def test_composite_uses_unambiguous_subtypes_and_mixed_or_unknown_types_fall_back_to_other():
    assert classify_order_category("COMPOSITE", ["LEAVE.ANNUAL.GRANT"]) == CATEGORY_LEAVE
    assert classify_order_category("COMPOSITE", ["HIRE", "CONCURRENT_DUTY_START"]) == CATEGORY_OTHER
    assert classify_order_category("UNKNOWN", ["UNKNOWN.SUBTYPE"]) == CATEGORY_OTHER


def test_period_uses_official_order_date_and_explicitly_excludes_missing_dates():
    engine = _Engine([])
    report = build_personnel_orders_summary(
        engine,
        date_from=date(2026, 1, 1),
        date_to=date(2026, 1, 31),
    )

    assert "po.order_date >= :date_from" in engine.connection.sql
    assert "po.order_date <= :date_to" in engine.connection.sql
    assert "created_at" not in engine.connection.sql
    assert engine.connection.params["date_from"] == date(2026, 1, 1)
    assert report["period_note"] == "При заданном периоде приказы без официальной даты не включаются."


def test_invalid_period_is_rejected_before_database_query():
    engine = _Engine([])
    with pytest.raises(PersonnelOrdersSummaryFilterError, match="Дата с"):
        build_personnel_orders_summary(
            engine,
            date_from=date(2026, 2, 1),
            date_to=date(2026, 1, 1),
        )
    assert engine.connection.sql == ""


def test_details_are_sorted_by_date_desc_then_number_then_stable_id_with_null_dates_last():
    report = _build(
        [
            _row(4, "HIRE", number="2", order_date=None),
            _row(3, "HIRE", number="2", order_date=date(2026, 1, 2)),
            _row(2, "HIRE", number="1", order_date=date(2026, 1, 2)),
            _row(1, "HIRE", number="9", order_date=date(2026, 1, 3)),
        ]
    )
    assert [order["order_id"] for order in report["categories"][0]["orders"]] == [1, 2, 3, 4]


def test_query_excludes_voided_archived_orders_and_voided_items():
    engine = _Engine([])
    build_personnel_orders_summary(engine)

    assert "po.archived_at IS NULL" in engine.connection.sql
    assert "po.status <> :voided_status" in engine.connection.sql
    assert engine.connection.params["voided_status"] == "VOIDED"
    assert engine.connection.sql.count("item_status = :active_item_status") == 3


def test_access_guard_runs_before_summary_service(monkeypatch):
    called = False

    def deny(_user):
        raise HTTPException(status_code=403, detail="Personnel admin access required.")

    def service(*_args, **_kwargs):
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(personnel_reports_routes, "require_personnel_admin_or_403", deny)
    monkeypatch.setattr(personnel_reports_routes, "build_personnel_orders_summary", service)

    with pytest.raises(HTTPException) as exc_info:
        personnel_reports_routes.preview_personnel_orders_summary(user={"user_id": 9})

    assert exc_info.value.status_code == 403
    assert called is False


def test_exact_orders_summary_get_route_is_registered_and_not_shadowed(monkeypatch):
    expected = {
        "report_code": "personnel_orders_summary",
        "categories": [],
        "total_count": 0,
        "total_incomplete_count": 0,
    }
    app.dependency_overrides[get_current_user] = lambda: {"user_id": 1}
    monkeypatch.setattr(personnel_reports_routes, "require_personnel_admin_or_403", lambda _user: None)
    monkeypatch.setattr(
        personnel_reports_routes,
        "build_personnel_orders_summary",
        lambda _engine, **_filters: expected,
    )
    try:
        response = TestClient(app).get(
            "/directory/personnel/reports/orders-summary",
            params={"date_from": "2026-06-01", "date_to": "2026-06-30"},
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    assert response.json() == expected
