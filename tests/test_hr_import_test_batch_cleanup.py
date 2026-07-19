"""Tests for pytest import batch fingerprint cleanup."""
from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.hr_import_service import import_control_list
from tests.conftest import table_exists
from tests.hr_import_fixtures import (
    cleanup_orphan_test_import_batches,
    find_orphan_test_import_batches,
    is_sample_workbook_import_batch,
    write_control_list_workbook,
)


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_orphan_sample_import_batch_is_detected_and_removed(seed, tmp_path: Path):
    source = write_control_list_workbook(tmp_path, yymm="2612")
    with engine.begin() as conn:
        batch_id, summary, _ = import_control_list(
            conn,
            file_path=source,
            imported_by=int(seed["initiator_user_id"]),
        )
    import_code = str(summary["import_code"])
    assert import_code == "2612-01"

    with engine.connect() as conn:
        assert is_sample_workbook_import_batch(conn, batch_id) is True
        matches = find_orphan_test_import_batches(conn)
        assert any(str(row["import_code"]) == import_code for row in matches)

    with engine.begin() as conn:
        removed = cleanup_orphan_test_import_batches(conn)
    assert import_code in removed

    with engine.connect() as conn:
        still = conn.execute(
            text("SELECT 1 FROM public.hr_import_batches WHERE import_code = :import_code"),
            {"import_code": import_code},
        ).first()
        assert still is None


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_cleanup_does_not_match_production_import_code_2606_02():
    with engine.connect() as conn:
        if not table_exists(conn, "hr_import_batches"):
            pytest.skip("hr_import_batches not available")
        row = conn.execute(
            text(
                """
                SELECT batch_id
                FROM public.hr_import_batches
                WHERE import_code = '2606-02'
                LIMIT 1
                """
            )
        ).first()
        if row is None:
            pytest.skip("import 2606-02 is not present in this database")
        assert is_sample_workbook_import_batch(conn, int(row[0])) is False
        matches = find_orphan_test_import_batches(conn)
        assert all(str(item["import_code"]) != "2606-02" for item in matches)
