"""Database-free tests for the stateless XLSX formatter."""
from io import BytesIO
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.api.table_export_routes import router
from app.auth import get_current_user


class TableExportTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(router)
        self.client = TestClient(self.app)

    def test_requires_authentication(self):
        response = self.client.post("/exports/table.xlsx", json={"headers": ["ФИО"], "rows": [["Иванов"]]})
        self.assertEqual(response.status_code, 401)

    def test_any_authenticated_table_reader_can_format_values(self):
        # Formatting does not require an admin/write permission or query the DB.
        self.app.dependency_overrides[get_current_user] = lambda: {"user_id": 99, "role_code": "USER"}
        rows = [[f"Сотрудник {i}", "001234567890", 0.5] for i in range(231)]
        rows.append(["=1+1", "+не формула", 0])
        response = self.client.post("/exports/table.xlsx", json={"headers": ["ФИО", "ИИН", "Ставка"], "rows": rows})
        self.assertEqual(response.status_code, 200)
        self.assertIn("spreadsheetml.sheet", response.headers["content-type"])
        self.assertEqual(response.headers["cache-control"], "no-store")
        sheet = load_workbook(BytesIO(response.content)).active
        self.assertEqual(list(sheet.values), [("ФИО", "ИИН", "Ставка"), *map(tuple, rows)])
        self.assertEqual(sheet["A233"].data_type, "s")
        self.assertEqual(sheet["B2"].value, "001234567890")
        self.assertEqual(sheet.auto_filter.ref, "A1:C233")
        self.assertEqual(sheet.freeze_panes, "A2")

    def test_empty_and_invalid_shape(self):
        self.app.dependency_overrides[get_current_user] = lambda: {"user_id": 99}
        response = self.client.post("/exports/table.xlsx", json={"headers": ["ФИО"], "rows": []})
        self.assertEqual(response.status_code, 404)
        self.assertIn("Нет записей", response.json()["detail"])
        response = self.client.post("/exports/table.xlsx", json={"headers": ["ФИО"], "rows": [["Имя", 2]]})
        self.assertEqual(response.status_code, 422)
