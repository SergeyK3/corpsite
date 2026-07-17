# tests/personnel_applications/test_wp_ppr_applicant_002_migration.py
"""Migration tests for WP-PPR-APPLICANT-002."""
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


def test_resolution_audit_table_exists(db_ready) -> None:
    with engine.connect() as conn:
        assert table_exists(conn, "personnel_application_resolution_audit")


def test_application_status_includes_applicant_002_values(db_ready) -> None:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT pg_get_constraintdef(oid) AS def
                FROM pg_constraint
                WHERE conname = 'chk_personnel_applications_status'
                """
            )
        ).first()
    assert row is not None
    for value in (
        "resolution_pending",
        "approved",
        "rejected",
        "revision_requested",
        "order_draft_created",
    ):
        assert value in row[0]
