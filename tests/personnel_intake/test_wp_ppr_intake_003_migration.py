# tests/personnel_intake/test_wp_ppr_intake_003_migration.py
"""Migration tests for WP-PPR-INTAKE-003 token ciphertext."""
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


def test_intake_link_token_ciphertext_column(db_ready) -> None:
    with engine.connect() as conn:
        assert table_exists(conn, "personnel_intake_links")
        row = conn.execute(
            text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'personnel_intake_links'
                  AND column_name = 'token_ciphertext'
                """
            )
        ).scalar_one_or_none()
        assert row == 1
