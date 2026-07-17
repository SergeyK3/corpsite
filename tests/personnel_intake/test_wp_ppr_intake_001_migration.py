# tests/personnel_intake/test_wp_ppr_intake_001_migration.py
"""Migration tests for WP-PPR-INTAKE-001."""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import table_exists
from tests.ppr.conftest import ppr_db_available


@pytest.fixture
def db_ready():
    if not ppr_db_available():
        pytest.skip("PostgreSQL not available")


def test_intake_tables_exist(db_ready) -> None:
    with engine.connect() as conn:
        assert table_exists(conn, "personnel_intake_links")
        assert table_exists(conn, "personnel_intake_drafts")


def test_intake_link_status_check(db_ready) -> None:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT pg_get_constraintdef(oid) AS def
                FROM pg_constraint
                WHERE conname = 'chk_personnel_intake_links_status'
                """
            )
        ).first()
    assert row is not None
    assert "issued" in row[0]
    assert "revoked" in row[0]
