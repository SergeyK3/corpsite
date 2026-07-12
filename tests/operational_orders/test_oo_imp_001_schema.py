# tests/operational_orders/test_oo_imp_001_schema.py
"""Schema smoke tests for OO-IMP-001."""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import get_columns, table_exists
from tests.operational_orders.conftest import DDL_REVISION, _require_schema

pytestmark = pytest.mark.usefixtures("_require_oo_schema_fixture")

OO_TABLES = (
    "operational_order_draft_workspaces",
    "operational_order_draft_blocks",
    "operational_order_text_provenance",
    "operational_order_clarifications",
    "operational_order_draft_audit",
    "operational_order_translation_assignments",
    "operational_order_content_confirmations",
    "operational_order_bilingual_reconciliations",
    "operational_order_promotions",
    "operational_order_documents",
    "operational_order_document_versions",
    "operational_order_document_localizations",
    "operational_order_promotion_audit",
)


def test_oo_tables_exist() -> None:
    _require_schema()
    with engine.connect() as conn:
        for table in OO_TABLES:
            assert table_exists(conn, table), table


def test_workspace_columns() -> None:
    with engine.connect() as conn:
        cols = get_columns(conn, "operational_order_draft_workspaces")
    for required in (
        "workspace_id",
        "organization_id",
        "drafting_path",
        "stage",
        "content_author_reference",
        "record_creator_user_id",
        "version",
    ):
        assert required in cols


def test_personnel_orders_tables_unchanged() -> None:
    with engine.connect() as conn:
        assert table_exists(conn, "personnel_orders")
        cols = get_columns(conn, "personnel_orders")
    assert "order_id" in cols
    assert "document_id" not in cols


def test_migration_revision_registered() -> None:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT version_num FROM alembic_version LIMIT 1")
        ).fetchone()
    assert row is not None
    assert row[0] == DDL_REVISION
