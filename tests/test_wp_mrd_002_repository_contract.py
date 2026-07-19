# tests/test_wp_mrd_002_repository_contract.py
"""Repository contract tests for WP-MRD-002."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.mrd.domain.difference_models import CreateDifferenceCommand
from app.mrd.domain.errors import MrdOptimisticConcurrencyConflictError
from app.mrd.domain.types import DIFFERENCE_BUSINESS_PERIOD_CHANGED, ORIGIN_IMPORT_COMPARE
from app.mrd.infrastructure.repository import SqlAlchemyMrdRepository, mrd_tables_available
from tests.mrd_helpers import seed_active_mrd, unique_report_period


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _require_mrd_schema() -> None:
    with engine.begin() as conn:
        if not mrd_tables_available(conn):
            pytest.skip("MRD schema missing — run alembic upgrade head")


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
def test_repository_resolve_and_insert_difference(seed, db_tx) -> None:
    _require_mrd_schema()
    period = unique_report_period()
    user_id = int(seed["initiator_user_id"])
    mrd_id = seed_active_mrd(db_tx, report_period=period, created_by=user_id)
    repo = SqlAlchemyMrdRepository(db_tx)

    active = repo.resolve_active_mrd(period)
    assert active is not None
    assert active.mrd_id == mrd_id

    diff = repo.insert_difference(
        CreateDifferenceCommand(
            report_period=period,
            mrd_id=mrd_id,
            logical_key=f"lk:{uuid4().hex}",
            entity_scope="emp:1",
            attribute="position_raw",
            business_type=DIFFERENCE_BUSINESS_PERIOD_CHANGED,
            difference_origin_code=ORIGIN_IMPORT_COMPARE,
            origin_context={"batch_id": 1},
            old_value="A",
            new_value="B",
            record_kind="roster",
            technical_diff_class="CHANGED",
        )
    )
    assert diff.difference_id > 0
    assert repo.count_differences_for_mrd(mrd_id) == 1


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_repository_mark_confirmed_optimistic_lock(seed, db_tx) -> None:
    _require_mrd_schema()
    period = unique_report_period()
    user_id = int(seed["initiator_user_id"])
    mrd_id = seed_active_mrd(db_tx, report_period=period, created_by=user_id)
    repo = SqlAlchemyMrdRepository(db_tx)
    diff = repo.insert_difference(
        CreateDifferenceCommand(
            report_period=period,
            mrd_id=mrd_id,
            logical_key=f"lk:{uuid4().hex}",
            entity_scope="emp:2",
            attribute="position_raw",
            business_type=DIFFERENCE_BUSINESS_PERIOD_CHANGED,
            difference_origin_code=ORIGIN_IMPORT_COMPARE,
            origin_context={"batch_id": 1},
            old_value="A",
            new_value="B",
            record_kind="roster",
            technical_diff_class="CHANGED",
        )
    )
    with pytest.raises(MrdOptimisticConcurrencyConflictError):
        repo.mark_confirmed(
            diff.difference_id,
            expected_row_version=99,
            confirmed_by=user_id,
            confirmed_at=datetime.now(timezone.utc),
        )
