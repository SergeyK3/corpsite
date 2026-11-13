"""Database-free checks for the printable all-assignment staff workbook."""
from datetime import date
from io import BytesIO
import unittest
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.auth import get_current_user
from app.directory import employees_routes
from app.services.staff_reconciliation_export import build_reconciliation_workbook


def row(assignment_id, unit_id, unit, position, type_code, name, *, primary=True, rate=1):
    return {
        "assignment_id": assignment_id, "org_unit_id": unit_id, "org_unit_name": unit,
        "position_name": position, "type_code": type_code, "full_name": name,
        "is_primary": primary, "rate": rate,
    }


class StaffReconciliationExportTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(employees_routes.router, prefix="/directory")
        app.dependency_overrides[get_current_user] = lambda: {"user_id": 9}
        self.client = TestClient(app)
        self.rows = [
            row(1, 20, "Хирургия", "Санитарка", 3, "Алина"),
            row(2, 20, "Хирургия", "Врач-ординатор", 1, "Борис"),
            row(3, 20, "Хирургия", "Заведующий отделением", 1, "Вера"),
            row(4, 20, "Хирургия", "Старшая медсестра", 2, "Галина"),
            row(5, 20, "Хирургия", "Медсестра", 2, "Дарья"),
            row(6, 20, "Хирургия", "Инженер", 4, "Елена"),
            row(7, 20, "Хирургия", "Должность без типа", None, "Жанна", rate=None),
            row(8, 10, "Терапия", "Фельдшер", 2, "Дарья", primary=False, rate=0.5),
            row(9, None, None, "Врач", 1, "Зоя"),
            row(10, 20, "Хирургия", "Врач", 1, "Алексей"),
        ]

    def test_all_departments_order_dedup_and_print_layout(self):
        content = build_reconciliation_workbook(self.rows + [self.rows[7]], as_of=date(2026, 11, 13))
        wb = load_workbook(BytesIO(content))
        self.assertEqual(wb.sheetnames, ["Отделение не указано", "Терапия", "Хирургия"])
        surgery = wb["Хирургия"]
        self.assertEqual([surgery.cell(i, 3).value for i in range(4, 12)], [
            "Заведующий отделением", "Врач", "Врач-ординатор", "Старшая медсестра",
            "Медсестра", "Санитарка", "Инженер", "Должность без типа",
        ])
        self.assertEqual([surgery.cell(i, 1).value for i in range(4, 12)], list(range(1, 9)))
        self.assertEqual(surgery["B5"].value, "Алексей")
        self.assertEqual(surgery["B6"].value, "Борис")
        self.assertIsNone(surgery["E11"].value)
        self.assertIsNone(surgery["F4"].value)
        self.assertGreaterEqual(surgery.column_dimensions["F"].width, 40)
        self.assertEqual(surgery.page_setup.fitToWidth, 1)
        self.assertEqual(surgery.print_title_rows, "$1:$3")
        self.assertEqual(wb["Терапия"]["D4"].value, "Совмещение")
        self.assertEqual(wb["Терапия"]["E4"].value, 0.5)
        self.assertEqual(wb["Терапия"].max_row, 4)
        self.assertEqual(wb["Отделение не указано"]["B4"].value, "Зоя")
        self.assertEqual(surgery["A1"].value, "Отделение: Хирургия")
        self.assertEqual(surgery["A2"].value, "Дата выгрузки: 13.11.2026")
        self.assertNotIn("ИИН", str(list(surgery.values)))

    def test_endpoint_uses_scope_and_ignores_current_roster_filters(self):
        with patch.object(employees_routes, "compute_scope", return_value={
            "scope_unit_id": None, "scope_unit_ids": [10, 20],
        }), patch.object(employees_routes, "require_personnel_visibility_or_403"), patch(
            "app.services.staff_reconciliation_export.fetch_current_assignments",
            return_value=(date(2026, 11, 13), self.rows),
        ) as fetch:
            response = self.client.get("/directory/employees/reconciliation.xlsx?q=никого&offset=100&limit=1")
        self.assertEqual(response.status_code, 200)
        fetch.assert_called_once_with(employees_routes.engine, scope_unit_id=None, scope_unit_ids=[10, 20])
        wb = load_workbook(BytesIO(response.content))
        self.assertEqual(sum(ws.max_row - 3 for ws in wb.worksheets), 10)

    def test_visibility_denial_stops_export(self):
        with patch.object(employees_routes, "compute_scope", return_value={}), patch.object(
            employees_routes, "require_personnel_visibility_or_403", side_effect=HTTPException(403),
        ), patch("app.services.staff_reconciliation_export.fetch_current_assignments") as fetch:
            response = self.client.get("/directory/employees/reconciliation.xlsx")
        self.assertEqual(response.status_code, 403)
        fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
