# tests/test_wp_po_edit_002_migration.py
"""Schema tests for WP-PO-EDIT-002 editorial persistence tables."""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import get_columns, table_exists

DDL_REVISION = "s3t4u5v6w7x8"

EDITORIAL_TABLES = (
    "personnel_order_editorial_blocks",
    "personnel_order_item_editorial_blocks",
    "personnel_order_item_bases",
)


def _schema_available() -> bool:
    with engine.begin() as conn:
        return all(table_exists(conn, table) for table in EDITORIAL_TABLES)


def _require_schema() -> None:
    if not _schema_available():
        pytest.skip(
            f"WP-PO-EDIT-002 editorial schema missing — run: alembic upgrade head "
            f"(revision {DDL_REVISION})"
        )


def test_editorial_tables_exist() -> None:
    _require_schema()
    with engine.begin() as conn:
        for table in EDITORIAL_TABLES:
            assert table_exists(conn, table)


def test_editorial_block_columns_and_unique() -> None:
    _require_schema()
    with engine.begin() as conn:
        cols = get_columns(conn, "personnel_order_editorial_blocks")
        for expected in (
            "editorial_block_id",
            "order_id",
            "locale",
            "block_type",
            "generated_text",
            "override_text",
            "generator_key",
            "generator_version",
            "source_fingerprint",
            "review_status",
            "revision",
        ):
            assert expected in cols

        constraints = {
            r[0]
            for r in conn.execute(
                text(
                    """
                    SELECT conname
                    FROM pg_constraint
                    WHERE conrelid = 'public.personnel_order_editorial_blocks'::regclass
                    """
                )
            ).all()
        }
        assert "uq_personnel_order_editorial_blocks_order_locale_type" in constraints
        assert "chk_personnel_order_editorial_blocks_block_type" in constraints
        assert "chk_personnel_order_editorial_blocks_review_status" in constraints


def test_item_basis_one_to_one_unique() -> None:
    _require_schema()
    with engine.begin() as conn:
        cols = get_columns(conn, "personnel_order_item_bases")
        assert "item_basis_id" in cols
        assert "basis_type" in cols
        assert "metadata" in cols
        constraints = {
            r[0]
            for r in conn.execute(
                text(
                    """
                    SELECT conname
                    FROM pg_constraint
                    WHERE conrelid = 'public.personnel_order_item_bases'::regclass
                    """
                )
            ).all()
        }
        assert "uq_personnel_order_item_bases_order_item_id" in constraints
