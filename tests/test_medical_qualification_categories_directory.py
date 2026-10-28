"""Run with MEDQUAL_LOCAL_TESTS=1 using unittest; all test writes roll back."""
import os
import unittest
from contextlib import nullcontext
from unittest.mock import patch

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


@unittest.skipUnless(os.getenv("MEDQUAL_LOCAL_TESTS") == "1", "Local PostgreSQL opt-in required")
class MedicalQualificationCategoriesTests(unittest.TestCase):
    def setUp(self):
        from app.db.engine import engine
        from app.db.medical_qualification_categories_schema import upgrade
        self.assertIn(engine.url.host, {"localhost", "127.0.0.1", "::1"})
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.addCleanup(self.connection.close)
        self.addCleanup(self.transaction.rollback)
        upgrade(self.connection)
        upgrade(self.connection)
        self.engine_patch = patch("app.services.medical_qualification_categories_service.engine")
        mocked_engine = self.engine_patch.start()
        self.addCleanup(self.engine_patch.stop)
        mocked_engine.connect.side_effect = lambda: nullcontext(self.connection)

    def test_exact_set_repeatable_seed_and_bilingual_search(self):
        from app.services.medical_qualification_categories_service import list_categories
        expected = [
            (1, 1, "Без категории", "Санаты жоқ"),
            (2, 2, "Вторая категория", "Екінші санат"),
            (3, 3, "Первая категория", "Бірінші санат"),
            (4, 4, "Высшая категория", "Жоғары санат"),
        ]
        result = list_categories()
        self.assertEqual(result["total"], 4)
        self.assertEqual([tuple(row.values()) for row in result["items"]], expected)
        for term in ("  ПЕРВАЯ  ", "БІРІНШІ"):
            self.assertEqual([row["code"] for row in list_categories(q=term)["items"]], [3])
        for term in ("%", "_", "\\", "Несуществующая"):
            self.assertEqual(list_categories(q=term), {"items": [], "total": 0})

    def test_database_rejects_duplicates_extra_values_and_mutations(self):
        statements = [
            "INSERT INTO public.medical_qualification_categories VALUES (1,1,'Без категории','Санаты жоқ')",
            "INSERT INTO public.medical_qualification_categories VALUES (5,5,'Новая','Жаңа')",
            "INSERT INTO public.medical_qualification_categories VALUES (5,1,'Без категории','Санаты жоқ')",
            "UPDATE public.medical_qualification_categories SET name='Другая' WHERE code=1",
            "DELETE FROM public.medical_qualification_categories WHERE code=1",
            "TRUNCATE public.medical_qualification_categories",
        ]
        for statement in statements:
            with self.subTest(statement=statement):
                with self.assertRaises(IntegrityError):
                    with self.connection.begin_nested():
                        self.connection.execute(text(statement))
        self.assertEqual(self.connection.execute(text("SELECT count(*) FROM public.medical_qualification_categories")).scalar_one(), 4)

    def test_api_permissions_search_and_absence_of_write_endpoints(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.auth import get_current_user
        from app.directory.medical_qualification_categories_routes import router
        app = FastAPI()
        app.include_router(router, prefix="/directory")
        client = TestClient(app)
        path = "/directory/medical-qualification-categories"
        self.assertEqual(client.get(path).status_code, 401)
        app.dependency_overrides[get_current_user] = lambda: {"user_id": 999999, "role_id": 999999}
        self.assertEqual(client.get(path).status_code, 403)
        app.dependency_overrides[get_current_user] = lambda: {"user_id": 25, "role_id": 2}
        self.assertEqual(client.get(path).json()["total"], 4)
        self.assertEqual(client.get(path, params={"q": "ЖОҒАРЫ"}).json()["items"][0]["code"], 4)
        self.assertEqual(client.get(path, params={"q": "x" * 501}).status_code, 422)
        for method in ("post", "put", "patch", "delete"):
            self.assertEqual(getattr(client, method)(path).status_code, 405)
