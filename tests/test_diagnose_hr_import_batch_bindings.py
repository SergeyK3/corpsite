"""Smoke/unit tests for scripts/diagnose_hr_import_batch_bindings.py."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import text

from app.db.engine import engine

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "diagnose_hr_import_batch_bindings.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("diagnose_hr_import_batch_bindings", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_batch_filename_sql_expr_prefers_file_name_column() -> None:
    mod = _load_script_module()
    assert mod.batch_filename_sql_expr(["batch_id", "file_name", "status"]) == "file_name"


def test_batch_filename_sql_expr_falls_back_to_source_filename() -> None:
    mod = _load_script_module()
    assert mod.batch_filename_sql_expr(["batch_id", "source_filename", "status"]) == "source_filename"


def test_batch_filename_sql_expr_uses_coalesce_when_both_exist() -> None:
    mod = _load_script_module()
    expr = mod.batch_filename_sql_expr(["file_name", "source_filename", "batch_id"])
    assert expr == "COALESCE(file_name, source_filename)"


def test_batch_header_select_sql_uses_file_name_alias() -> None:
    mod = _load_script_module()
    sql = mod.batch_header_select_sql(
        ["batch_id", "file_name", "imported_at", "status"],
    )
    assert "file_name AS file_name" in sql
    assert "source_filename" not in sql


@pytest.mark.skipif(not SCRIPT_PATH.exists(), reason="diagnose script missing")
def test_fetch_batch_header_smoke_against_live_schema() -> None:
    mod = _load_script_module()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        pytest.skip("PostgreSQL not available")

    with engine.connect() as conn:
        columns = mod._table_column_names(conn, mod.BATCH_TABLE)
        assert {"batch_id", "imported_at", "status"}.issubset(columns)
        assert "file_name" in columns or "source_filename" in columns

        batch_id = conn.execute(text("SELECT MIN(batch_id) FROM public.hr_import_batches")).scalar()
        if batch_id is None:
            pytest.skip("no hr_import_batches rows to smoke-test")

        row = mod.fetch_batch_header(conn, int(batch_id))

    assert row is not None
    assert "file_name" in row
    assert "batch_id" in row
