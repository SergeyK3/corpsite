# tests/test_wp_mrd_003_repository_contract.py
"""Repository contract tests for WP-MRD-003 fork persistence."""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.mrd.domain.types import REFERENCE_EVENT_CREATE
from app.mrd.infrastructure.repository import SqlAlchemyMrdRepository, mrd_tables_available
from tests.mrd_helpers import mrd_command_table_available, seed_active_mrd, unique_report_period


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _require_schema(conn) -> None:
    if not mrd_tables_available(conn):
        pytest.skip("MRD schema not migrated")


@pytest.fixture
def db_tx():
    conn = engine.connect()
    tx = conn.begin()
    try:
        yield conn
    finally:
        tx.rollback()
        conn.close()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_insert_version_event_create_type(seed, db_tx) -> None:
    if not mrd_command_table_available(db_tx):
        pytest.skip("WP-MRD-003 command idempotency schema not migrated")
    period = unique_report_period()
    user_id = int(seed["initiator_user_id"])
    mrd_id = seed_active_mrd(db_tx, report_period=period, created_by=user_id)
    repo = SqlAlchemyMrdRepository(db_tx)
    event_id = repo.insert_version_event(
        event_type=REFERENCE_EVENT_CREATE,
        report_period=period,
        mrd_id=mrd_id,
        performed_by=user_id,
        source_mrd_id=mrd_id,
        event_context={"command_id": "test-create-event"},
    )
    row = db_tx.execute(
        text(
            """
            SELECT event_type
            FROM public.hr_reference_version_events
            WHERE event_id = :event_id
            """
        ),
        {"event_id": event_id},
    ).scalar_one()
    assert row == REFERENCE_EVENT_CREATE


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_copy_confirmed_entries_only_target_mrd(seed, db_tx) -> None:
    _require_schema(db_tx)
    period = unique_report_period()
    user_id = int(seed["initiator_user_id"])
    source_id = seed_active_mrd(db_tx, report_period=period, created_by=user_id)
    target_id = seed_active_mrd(db_tx, report_period=unique_report_period(), created_by=user_id)
    from tests.mrd_helpers import seed_mrd_entry

    seed_mrd_entry(db_tx, mrd_id=source_id, match_key="emp:1", payload={"position_raw": "Nurse"})
    repo = SqlAlchemyMrdRepository(db_tx)
    copied = repo.copy_confirmed_entries(source_mrd_id=source_id, target_mrd_id=target_id)
    assert copied == 1
    assert len(repo.load_mrd_entries(target_id)) == 1
    assert len(repo.load_mrd_entries(source_id)) == 1
