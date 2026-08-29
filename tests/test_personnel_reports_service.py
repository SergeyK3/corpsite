from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

from openpyxl import load_workbook

from app.services.personnel_reports_service import (
    assert_report_org_unit_accessible,
    build_personnel_roster,
    build_personnel_roster_xlsx,
    list_report_org_options,
)
from app.main import app


class _MappingsResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


class _Connection:
    def __init__(self, rows):
        self.rows = rows
        self.statements: list[str] = []
        self.params: list[dict] = []

    def execute(self, statement, params=None):
        self.statements.append(str(statement))
        self.params.append(params or {})
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


def test_removed_declaration_export_api_route_is_not_registered():
    paths = {route.path for route in app.routes}
    assert "/directory/personnel/import/batches/{batch_id}/declarations/export" not in paths


def test_options_only_include_visible_departments_and_preserve_group_relation():
    engine = _Engine(
        [
            {"unit_id": 12, "unit_name": "Хирургия", "group_id": 3, "group_name": "Клинические"},
            {"unit_id": 15, "unit_name": "Терапия", "group_id": 3, "group_name": "Клинические"},
        ]
    )

    result = list_report_org_options(engine, scope_unit_ids=[12, 15])

    assert result["groups"] == [{"group_id": 3, "group_name": "Клинические"}]
    assert [row["unit_id"] for row in result["departments"]] == [12, 15]
    assert engine.connection.params == [{"scope_unit_ids": [12, 15]}]
    assert "ou.unit_id = ANY(:scope_unit_ids)" in engine.connection.statements[0]


def test_direct_inaccessible_department_is_rejected_before_query():
    connection = _Connection([])
    assert assert_report_org_unit_accessible(
        connection,
        org_unit_id=99,
        scope_unit_ids=[12, 15],
    ) is None
    assert connection.statements == []


def test_roster_uses_only_current_operational_employees_and_formats_missing_values():
    engine = _Engine(
        [
            {"full_name": "Абдулова А.А.", "position_name": None, "rate": 1},
            {"full_name": "Беков Б.Б.", "position_name": "Врач", "rate": None},
        ]
    )
    generated_at = datetime(2026, 8, 29, 9, 30, tzinfo=timezone.utc)

    report = build_personnel_roster(
        engine,
        org_unit={"unit_id": 12, "unit_name": "Хирургия", "group_id": 3, "group_name": "Клинические"},
        generated_at=generated_at,
    )

    assert report["items"] == [
        {"number": 1, "full_name": "Абдулова А.А.", "position": "Не указано", "rate": "1"},
        {"number": 2, "full_name": "Беков Б.Б.", "position": "Врач", "rate": "Не указано"},
    ]
    sql = engine.connection.statements[0]
    assert "e.operational_status = 'active'" in sql
    assert "pa.active_flag IS TRUE" in sql
    assert "pa.is_primary IS TRUE" in sql
    assert "pa.lifecycle_status = 'active'" in sql
    assert "ORDER BY LOWER" in sql
    assert "hr_import" not in sql


def test_excel_contains_the_same_rows_as_preview():
    report = {
        "report_name": "Личный состав",
        "generated_at": "2026-08-29T09:30:00+00:00",
        "group": {"id": 3, "name": "Клинические"},
        "department": {"id": 12, "name": "Хирургия"},
        "items": [
            {"number": 1, "full_name": "Абдулова А.А.", "position": "Не указано", "rate": "1"},
            {"number": 2, "full_name": "Беков Б.Б.", "position": "Врач", "rate": "Не указано"},
        ],
    }

    workbook = load_workbook(BytesIO(build_personnel_roster_xlsx(report)))
    sheet = workbook["Личный состав"]

    assert sheet["A1"].value == "Личный состав"
    assert [sheet.cell(7, col).value for col in range(1, 5)] == ["№", "ФИО", "Должность", "Ставка"]
    excel_rows = [tuple(sheet.cell(row, col).value for col in range(1, 5)) for row in range(8, 10)]
    preview_rows = [tuple(item[key] for key in ("number", "full_name", "position", "rate")) for item in report["items"]]
    assert excel_rows == preview_rows
    assert sheet.freeze_panes == "A8"
    assert sheet.page_setup.orientation == "portrait"
    assert sheet.page_setup.fitToWidth == 1
