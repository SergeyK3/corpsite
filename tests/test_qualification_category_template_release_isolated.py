"""Standalone full-chain rehearsal; never connects to a working application DB.

Run with ``python -B -m unittest tests.test_qualification_category_template_release_isolated``.
An explicit loopback TEST_DATABASE_URL with a database name ending in _test is
required. Only its maintenance connection is used to create a disposable DB.
"""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from uuid import uuid4
import zipfile

from alembic import command
from alembic.config import Config
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import NullPool


ROOT = Path(__file__).resolve().parents[1]
BASE_COMMIT = "36f9d4c317eeff60a2a597aaa5227cd0098bcf3a"
MIGRATION = "qualtext001_published_qualification_category_template.py"
EXPORT_SHA256 = "64fd8b00b688cbe2829955ee321dcdf99070e5cb347fceeb259492900bc70129"


class QualificationTemplateReleaseTest(unittest.TestCase):
    def test_full_chain_publication_and_exact_export(self):
        raw = os.environ.get("TEST_DATABASE_URL")
        if not raw:
            self.skipTest("Explicit local TEST_DATABASE_URL required")
        source = make_url(raw)
        self.assertEqual(source.get_backend_name(), "postgresql")
        self.assertIn(source.host, {"127.0.0.1", "localhost", "::1"})
        self.assertTrue((source.database or "").endswith("_test"))
        name = "corpsite_qual_release_" + uuid4().hex + "_test"
        self.assertRegex(name, r"^corpsite_qual_release_[0-9a-f]{32}_test$")
        target = source.set(database=name)
        admin = create_engine(source.set(database="postgres"), poolclass=NullPool,
                              isolation_level="AUTOCOMMIT", hide_parameters=True)
        engine = create_engine(target, poolclass=NullPool, hide_parameters=True)
        created = False
        try:
            with admin.connect() as conn:
                self.assertEqual(conn.execute(text(
                    "SELECT count(*) FROM pg_database WHERE datname=:name"
                ), {"name": name}).scalar_one(), 0)
                conn.exec_driver_sql(f'CREATE DATABASE "{name}"')
                created = True
            with engine.connect() as conn:
                self.assertEqual(conn.execute(text("SELECT current_database()")).scalar_one(), name)
                self.assertEqual(conn.execute(text("""
                    SELECT count(*) FROM information_schema.tables WHERE table_schema='public'
                """)).scalar_one(), 0)
            self._rehearse(engine, target)
        finally:
            engine.dispose()
            if created:
                with admin.connect() as conn:
                    conn.execute(text("""
                        SELECT pg_terminate_backend(pid) FROM pg_stat_activity
                        WHERE datname=:name AND pid<>pg_backend_pid()
                    """), {"name": name})
                    conn.exec_driver_sql(f'DROP DATABASE "{name}"')
                # A separate connection verifies cleanup even if rehearsal failed.
                with admin.connect() as conn:
                    self.assertEqual(conn.execute(text(
                        "SELECT count(*) FROM pg_database WHERE datname=:name"
                    ), {"name": name}).scalar_one(), 0)
                print("TEMP_DATABASE_DELETED_AND_ABSENT", name, flush=True)
            admin.dispose()

    def _rehearse(self, engine, target):
        archive = subprocess.check_output([
            "git", "archive", "--format=zip", BASE_COMMIT,
            "alembic", "alembic.ini", "app", "tests/personnel_lk/adr065_test_bootstrap.sql",
            "tests/personnel_lk/adr065_test_org_bootstrap.sql",
        ], cwd=ROOT)
        # Exporting the committed chain avoids unrelated, uncommitted branches.
        with tempfile.TemporaryDirectory(prefix="corpsite_qual_release_", dir=ROOT / "runtime") as temporary:
            checkout = Path(temporary)
            with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
                zipped.extractall(checkout)
            shutil.copyfile(ROOT / "alembic/versions" / MIGRATION,
                            checkout / "alembic/versions" / MIGRATION)
            config = Config(str(checkout / "alembic.ini"))
            config.set_main_option("sqlalchemy.url", target.render_as_string(
                hide_password=False).replace("%", "%%"))
            old_cwd = Path.cwd()
            old_bytecode = sys.dont_write_bytecode
            old_path = sys.path[:]
            environment = {"DATABASE_URL": target.render_as_string(hide_password=False),
                           "CORPSITE_SKIP_DOTENV": "1", "PYTHONDONTWRITEBYTECODE": "1"}
            old_environment = {key: os.environ.get(key) for key in environment}
            try:
                sys.dont_write_bytecode = True
                sys.path.insert(0, str(checkout))
                os.chdir(checkout)
                os.environ.update(environment)
                self._run_chain(engine, config, checkout)
            finally:
                os.chdir(old_cwd)
                sys.path[:] = old_path
                sys.dont_write_bytecode = old_bytecode
                for key, value in old_environment.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value

    def _run_chain(self, engine, config, checkout):
        def upgrade(revision):
            command.upgrade(config, revision)
            with engine.connect() as conn:
                self.assertEqual(conn.execute(text(
                    "SELECT version_num FROM alembic_version"
                )).scalars().all(), [revision])
            print("UPGRADE_OK", revision, flush=True)

        upgrade("02b0d99063cd")
        with engine.begin() as conn:
            conn.exec_driver_sql((checkout / "tests/personnel_lk/adr065_test_bootstrap.sql").read_text(encoding="utf-8"))
        upgrade("r1s2t3u4v5w6")
        with engine.begin() as conn:
            conn.exec_driver_sql((checkout / "tests/personnel_lk/adr065_test_org_bootstrap.sql").read_text(encoding="utf-8"))
        upgrade("poprint001")
        upgrade("poqual001")
        upgrade("medqual001")
        expected_categories = [
            (1, 1, "Без категории", "Санаты жоқ"),
            (2, 2, "Вторая категория", "Екінші санат"),
            (3, 3, "Первая категория", "Бірінші санат"),
            (4, 4, "Высшая категория", "Жоғары санат"),
        ]

        def categories(conn):
            return [tuple(row) for row in conn.execute(text("""
                SELECT qualification_category_id,code,name,name_kk
                FROM medical_qualification_categories ORDER BY code
            """))]

        with engine.begin() as conn:
            self.assertEqual(categories(conn), expected_categories)
            # Occupy unrelated identities and advance server sequences. The
            # release must use those sequences, never the local IDs 42 / 56.
            conn.execute(text("""
                INSERT INTO personnel_order_templates(template_id,item_type_code,name_ru,name_kk)
                VALUES (1000,'TRANSFER','Synthetic unrelated template','Synthetic unrelated KK')
            """))
            conn.execute(text("""
                INSERT INTO personnel_order_template_versions(
                    template_version_id,template_id,item_type_code,version_number,status,
                    title_ru,title_kk,preamble_ru,preamble_kk,body_template_ru,body_template_kk,
                    basis_template_ru,basis_template_kk,print_title_ru,print_title_kk,published_at)
                VALUES (2000,1000,'TRANSFER',1,'PUBLISHED','Synthetic','Synthetic',
                    'Synthetic','Synthetic','Synthetic','Synthetic','Synthetic','Synthetic',
                    'Synthetic','Synthetic',now())
            """))
            conn.execute(text("SELECT setval('personnel_order_templates_template_id_seq',1000)"))
            conn.execute(text("SELECT setval('personnel_order_template_versions_template_version_id_seq',2000)"))
            before_template = conn.execute(text(
                "SELECT to_jsonb(t) FROM personnel_order_templates t WHERE template_id=1000"
            )).scalar_one()
            before_version = conn.execute(text(
                "SELECT to_jsonb(v) FROM personnel_order_template_versions v WHERE template_version_id=2000"
            )).scalar_one()
        upgrade("qualtext001")
        spec = importlib.util.spec_from_file_location("qualification_release", checkout / "alembic/versions" / MIGRATION)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        payload = {"template": migration.TEMPLATE, "version": migration.VERSION}
        digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                           separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(digest, EXPORT_SHA256)
        self.assertEqual(digest, migration.EXPORT_SHA256)
        with engine.begin() as conn:
            template = dict(conn.execute(text(
                "SELECT * FROM personnel_order_templates WHERE template_id=1001"
            )).mappings().one())
            version = dict(conn.execute(text(
                "SELECT * FROM personnel_order_template_versions WHERE template_version_id=2001"
            )).mappings().one())
            self.assertEqual({key: template[key] for key in migration.TEMPLATE}, migration.TEMPLATE)
            self.assertEqual({key: version[key] for key in migration.VERSION}, migration.VERSION)
            self.assertEqual(version["template_id"], template["template_id"])
            self.assertEqual(version["item_type_code"], "QUALIFICATION_CATEGORY")
            self.assertEqual(version["status"], "PUBLISHED")
            self.assertIsNotNone(version["published_at"])
            for key in ("created_by_user_id", "updated_by_user_id", "published_by_user_id"):
                self.assertIsNone(version[key])
            self.assertEqual(categories(conn), expected_categories)
            constraints = conn.execute(text("""
                SELECT convalidated,pg_get_constraintdef(oid) FROM pg_constraint
                WHERE conname IN ('chk_personnel_orders_order_type_code',
                                  'chk_personnel_order_items_item_type_code')
            """)).all()
            self.assertEqual(len(constraints), 2)
            for validated, definition in constraints:
                self.assertTrue(validated)
                self.assertIn("'QUALIFICATION_CATEGORY'", definition)
            self.assertEqual(conn.execute(text(
                "SELECT to_jsonb(t) FROM personnel_order_templates t WHERE template_id=1000"
            )).scalar_one(), before_template)
            self.assertEqual(conn.execute(text(
                "SELECT to_jsonb(v) FROM personnel_order_template_versions v WHERE template_version_id=2000"
            )).scalar_one(), before_version)
            # Conflict protection must not silently replace or duplicate a publication.
            with self.assertRaisesRegex(RuntimeError, "already exists"):
                with conn.begin_nested(), Operations.context(MigrationContext.configure(conn)):
                    migration.upgrade()
            with self.assertRaisesRegex(RuntimeError, "retains its published template"):
                with Operations.context(MigrationContext.configure(conn)):
                    migration.downgrade()
            with self.assertRaises(IntegrityError):
                with conn.begin_nested():
                    conn.execute(text("""
                        INSERT INTO medical_qualification_categories
                        SELECT * FROM medical_qualification_categories WHERE code=1
                    """))
        upgrade("qualtext001")  # Alembic rerun is a no-op, with no duplicate rows.
        with engine.connect() as conn:
            self.assertEqual(conn.execute(text(
                "SELECT count(*) FROM personnel_order_templates WHERE item_type_code='QUALIFICATION_CATEGORY'"
            )).scalar_one(), 1)
            self.assertEqual(categories(conn), expected_categories)
        print("VERIFIED published template, exact export, server IDs, untouched sentinel, four categories",
              flush=True)


if __name__ == "__main__":
    unittest.main()
