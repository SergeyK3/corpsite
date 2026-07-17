# tests/architecture/test_personnel_application_invariants.py
"""Architecture guard: domain terminal set synchronized with DB partial index."""
from __future__ import annotations

import re

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.personnel_applications.domain.status import TERMINAL_APPLICATION_STATUSES
from tests.conftest import table_exists


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _extract_index_terminal_statuses(indexdef: str) -> set[str]:
    not_in_match = re.search(r"NOT IN \(([^)]+)\)", indexdef, flags=re.IGNORECASE)
    if not_in_match is not None:
        raw = not_in_match.group(1)
        return {part.strip().strip("'").lower() for part in raw.split(",")}

    all_match = re.search(r"ARRAY\[([^\]]+)\]", indexdef, flags=re.IGNORECASE)
    if all_match is not None:
        return set(re.findall(r"'([^']+)'", all_match.group(1)))

    assert False, indexdef


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_terminal_status_set_matches_partial_index_predicate() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "personnel_applications"):
            pytest.skip("personnel_applications missing — run: alembic upgrade head")
        row = conn.execute(
            text(
                """
                SELECT indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename = 'personnel_applications'
                  AND indexname = 'uq_personnel_applications_one_active_per_person'
                """
            )
        ).mappings().first()
    assert row is not None
    index_terminals = _extract_index_terminal_statuses(str(row["indexdef"]))
    domain_terminals = {s.lower() for s in TERMINAL_APPLICATION_STATUSES}
    assert index_terminals == domain_terminals
