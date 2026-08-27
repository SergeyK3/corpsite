from __future__ import annotations

from collections import Counter
import importlib.util
from pathlib import Path
import sys

from openpyxl import Workbook
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


@pytest.fixture(scope="module")
def reconcile():
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec = importlib.util.spec_from_file_location(
            "reconcile_personnel_csv_under_test", SCRIPTS / "reconcile_personnel_csv.py"
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(SCRIPTS))


def _database(reconcile, units: list[dict[str, object]]) -> dict[str, object]:
    units_by_id = {int(unit["unit_id"]): unit for unit in units}
    units_by_code: dict[str, list[dict[str, object]]] = {}
    for unit in units:
        units_by_code.setdefault(str(unit["code"]), []).append(unit)
    position = {"position_id": 77, "name": "Engineer"}
    return {
        "person_by_id": {},
        "employees_by_person": {},
        "people_by_iin": {},
        "people_by_name_birth": {},
        "people_by_name": {},
        "employees_by_name": {},
        "employees_by_id": {},
        "person_iins": {},
        "units_by_id": units_by_id,
        "units_by_code": units_by_code,
        "positions_by_key": {reconcile.normalized("Engineer"): [position]},
        "positions_by_id": {77: position},
    }


def _source_row() -> dict[str, str]:
    return {
        "ФИО": "Import Test",
        "ИИН": "123456789012",
        "Дата рождения": "",
        "должность": "Engineer",
        "отдел": "Source Department",
        "ТабНомер": "",
        "телефон": "",
        "date_from": "2026-01-01",
    }


def _reconcile(reconcile, units: list[dict[str, object]]) -> dict[str, str]:
    department_map = {
        reconcile.normalized("Source Department"): {
            "name": "Control name",
            "code": "GENERAL",
            "source_department": "Source Department",
        }
    }
    return reconcile.reconcile_row(
        _source_row(),
        2,
        "",
        Counter(),
        department_map,
        set(),
        _database(reconcile, units),
    )


@pytest.mark.parametrize("xlsx_unit_id", [7, None])
def test_department_code_resolves_current_database_id_even_when_xlsx_unit_id_differs(
    reconcile, tmp_path: Path, xlsx_unit_id: int | None
):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = reconcile.DEPARTMENT_SHEET
    sheet.append(["unit_id", "name", "code", "отдел1С"])
    sheet.append([xlsx_unit_id, "Control name", "GENERAL", "Source Department"])
    workbook_path = tmp_path / "mapping.xlsx"
    workbook.save(workbook_path)

    department_map, ambiguous = reconcile.load_department_map(workbook_path)
    assert not ambiguous
    assert department_map[reconcile.normalized("Source Department")]["code"] == "GENERAL"
    assert "unit_id" not in department_map[reconcile.normalized("Source Department")]

    report = _reconcile(
        reconcile,
        [{"unit_id": 901, "name": "Current unit", "code": "GENERAL", "is_active": True}],
    )
    assert report["status"] == reconcile.STATUS_NEW
    assert report["found_department_unit_id"] == "901"


def test_department_code_missing_in_database_is_an_error(reconcile):
    report = _reconcile(reconcile, [])

    assert report["status"] == reconcile.STATUS_ERROR
    assert report["found_department_unit_id"] == ""
    assert "code=GENERAL из XLSX отсутствует" in report["notes"]


def test_ambiguous_department_code_is_an_error(reconcile):
    report = _reconcile(
        reconcile,
        [
            {"unit_id": 901, "name": "First", "code": "GENERAL", "is_active": True},
            {"unit_id": 902, "name": "Second", "code": "GENERAL", "is_active": True},
        ],
    )

    assert report["status"] == reconcile.STATUS_ERROR
    assert report["found_department_unit_id"] == ""
    assert "code=GENERAL неоднозначен" in report["notes"]


def test_inactive_department_code_is_not_used(reconcile):
    report = _reconcile(
        reconcile,
        [{"unit_id": 901, "name": "Archived", "code": "GENERAL", "is_active": False}],
    )

    assert report["status"] == reconcile.STATUS_ERROR
    assert report["found_department_unit_id"] == ""
    assert "подразделение неактивно" in report["notes"]


@pytest.mark.parametrize(
    ("field", "value", "expected_note"),
    [
        ("должность", "", "не заполнена должность"),
        ("ИИН", "123", "ИИН должен содержать 12 цифр"),
        ("date_from", "not-a-date", "некорректный date_from"),
    ],
)
def test_position_iin_and_date_validation_are_unchanged(reconcile, field, value, expected_note):
    row = _source_row()
    row[field] = value
    department_map = {
        reconcile.normalized("Source Department"): {
            "name": "Control name",
            "code": "GENERAL",
            "source_department": "Source Department",
        }
    }
    report = reconcile.reconcile_row(
        row,
        2,
        "",
        Counter(),
        department_map,
        set(),
        _database(reconcile, [{"unit_id": 901, "name": "Current", "code": "GENERAL", "is_active": True}]),
    )

    assert report["status"] == reconcile.STATUS_ERROR
    assert expected_note in report["notes"]


def test_csv_duplicate_and_existing_employee_statuses_are_unchanged(reconcile):
    unit = {"unit_id": 901, "name": "Current", "code": "GENERAL", "is_active": True}
    duplicate_report = reconcile.reconcile_row(
        _source_row(),
        2,
        "iin:123456789012",
        Counter({"iin:123456789012": 2}),
        {reconcile.normalized("Source Department"): {"name": "Control", "code": "GENERAL"}},
        set(),
        _database(reconcile, [unit]),
    )
    assert duplicate_report["status"] == reconcile.STATUS_AMBIGUOUS

    database = _database(reconcile, [unit])
    database["person_by_id"] = {1: {"person_id": 1, "full_name": "Import Test", "iin": "123456789012", "birth_date": None}}
    database["people_by_iin"] = {"123456789012": {1}}
    database["person_iins"] = {1: {"123456789012"}}
    existing_report = reconcile.reconcile_row(
        _source_row(),
        2,
        "",
        Counter(),
        {reconcile.normalized("Source Department"): {"name": "Control", "code": "GENERAL"}},
        set(),
        database,
    )
    assert existing_report["status"] == reconcile.STATUS_EXISTING
