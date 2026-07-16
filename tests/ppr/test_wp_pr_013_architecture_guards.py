# tests/ppr/test_wp_pr_013_architecture_guards.py
"""Architecture guard tests for WP-PR-013 / ADR-056 employment biography foundation."""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import table_exists


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_person_external_employment_has_no_employee_fk() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "person_external_employment"):
            pytest.skip("person_external_employment missing — run: alembic upgrade head")
        rows = conn.execute(
            text(
                """
                SELECT ccu.table_name AS referenced_table
                FROM information_schema.table_constraints tc
                JOIN information_schema.constraint_column_usage ccu
                  ON ccu.constraint_name = tc.constraint_name
                 AND ccu.constraint_schema = tc.constraint_schema
                WHERE tc.table_schema = 'public'
                  AND tc.table_name = 'person_external_employment'
                  AND tc.constraint_type = 'FOREIGN KEY'
                """
            )
        ).mappings().all()
    referenced = {str(row["referenced_table"]) for row in rows}
    assert referenced == {"persons"}


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_person_external_employment_employee_context_id_is_not_fk() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "person_external_employment"):
            pytest.skip("person_external_employment missing — run: alembic upgrade head")
        row = conn.execute(
            text(
                """
                SELECT COUNT(*) AS fk_count
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON kcu.constraint_name = tc.constraint_name
                 AND kcu.constraint_schema = tc.constraint_schema
                WHERE tc.table_schema = 'public'
                  AND tc.table_name = 'person_external_employment'
                  AND tc.constraint_type = 'FOREIGN KEY'
                  AND kcu.column_name = 'employee_context_id'
                """
            )
        ).scalar_one()
    assert int(row) == 0
