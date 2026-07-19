# tests/test_wp_mrd_001_repository_contract.py
"""Repository and domain contract tests for WP-MRD-001."""
from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.mrd.domain.errors import (
    DifferenceLifecycleError,
    DifferenceOriginError,
    MrdMutationForbiddenError,
)
from app.mrd.domain.invariants import (
    is_terminal_lifecycle,
    validate_active_origin,
    validate_closed_mrd_immutable,
    validate_difference_origin_required,
    validate_lifecycle_transition,
    validate_mrd_status_for_entry_mutation,
    validate_origin_context,
)
from app.mrd.domain.types import (
    DIFFERENCE_LIFECYCLE_CONFIRMED,
    DIFFERENCE_LIFECYCLE_DETECTED,
    DIFFERENCE_LIFECYCLE_REJECTED,
    DIFFERENCE_LIFECYCLE_SUPERSEDED,
    ORIGIN_IMPORT_COMPARE,
)
from app.mrd.infrastructure.schema_repository import MrdSchemaRepository
from tests.conftest import table_exists


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _require_wp_mrd_001() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "hr_monthly_references"):
            pytest.skip("WP-MRD-001 schema missing — run alembic upgrade head")


def _report_period() -> date:
    suffix = uuid4().hex
    year = 2090 + int(suffix[:2], 16) % 10
    month = int(suffix[2:4], 16) % 12 + 1
    return date(year, month, 1)


@pytest.fixture
def db_tx():
    conn = engine.connect()
    tx = conn.begin()
    try:
        yield conn
    finally:
        tx.rollback()
        conn.close()


def test_domain_lifecycle_transition_matrix() -> None:
    validate_lifecycle_transition(DIFFERENCE_LIFECYCLE_DETECTED, DIFFERENCE_LIFECYCLE_CONFIRMED)
    validate_lifecycle_transition(DIFFERENCE_LIFECYCLE_DETECTED, DIFFERENCE_LIFECYCLE_REJECTED)
    validate_lifecycle_transition(DIFFERENCE_LIFECYCLE_DETECTED, DIFFERENCE_LIFECYCLE_SUPERSEDED)

    with pytest.raises(DifferenceLifecycleError):
        validate_lifecycle_transition(DIFFERENCE_LIFECYCLE_CONFIRMED, DIFFERENCE_LIFECYCLE_DETECTED)
    with pytest.raises(DifferenceLifecycleError):
        validate_lifecycle_transition(DIFFERENCE_LIFECYCLE_REJECTED, DIFFERENCE_LIFECYCLE_DETECTED)

    assert is_terminal_lifecycle(DIFFERENCE_LIFECYCLE_SUPERSEDED)
    assert not is_terminal_lifecycle(DIFFERENCE_LIFECYCLE_DETECTED)


def test_domain_origin_and_mrd_guards() -> None:
    with pytest.raises(DifferenceOriginError):
        validate_difference_origin_required("")
    with pytest.raises(DifferenceOriginError):
        validate_origin_context(None)
    with pytest.raises(DifferenceOriginError):
        validate_active_origin(ORIGIN_IMPORT_COMPARE, is_active=False)

    with pytest.raises(MrdMutationForbiddenError):
        validate_mrd_status_for_entry_mutation("CLOSED")
    with pytest.raises(MrdMutationForbiddenError):
        validate_closed_mrd_immutable("CLOSED")

    validate_mrd_status_for_entry_mutation("ACTIVE")


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_repository_insert_mrd_and_entry(seed, db_tx) -> None:
    _require_wp_mrd_001()
    period = _report_period()
    user_id = int(seed["initiator_user_id"])

    repo = MrdSchemaRepository(db_tx)
    mrd = repo.insert_monthly_reference(
        report_period=period,
        version=1,
        created_by=user_id,
    )
    entry_id = repo.insert_entry(
        mrd_id=mrd.mrd_id,
        entity_scope="employee:42",
        match_key=f"mk:{uuid4().hex}",
        canonical_hash="abc123",
        effective_payload={"position": "nurse"},
    )
    assert entry_id > 0
    assert mrd.status == "ACTIVE"
    assert mrd.row_version == 1


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_repository_confirmed_change_one_to_one(seed, db_tx) -> None:
    _require_wp_mrd_001()
    period = _report_period()
    user_id = int(seed["initiator_user_id"])

    repo = MrdSchemaRepository(db_tx)
    mrd = repo.insert_monthly_reference(
        report_period=period,
        version=1,
        created_by=user_id,
    )
    difference = repo.insert_detected_difference(
        report_period=period,
        mrd_id=mrd.mrd_id,
        logical_key=f"lk:{uuid4().hex}",
        entity_scope="employee:42",
        attribute="position",
        business_type="PERIOD_CHANGED",
        difference_origin_code=ORIGIN_IMPORT_COMPARE,
        origin_context={"batch_id": 1},
        old_value="nurse",
        new_value="senior nurse",
    )
    event = repo.insert_confirmed_change(
        detected_difference_id=difference.difference_id,
        report_period=period,
        mrd_id=mrd.mrd_id,
        entity_scope="employee:42",
        attribute="position",
        old_value="nurse",
        new_value="senior nurse",
        confirmed_by=user_id,
        difference_origin_code=ORIGIN_IMPORT_COMPARE,
        origin_context={"batch_id": 1},
    )
    assert event.detected_difference_id == difference.difference_id
    assert repo.count_confirmed_changes_for_difference(difference.difference_id) == 1

    nested = db_tx.begin_nested()
    with pytest.raises(Exception):
        MrdSchemaRepository(db_tx).insert_confirmed_change(
            detected_difference_id=difference.difference_id,
            report_period=period,
            mrd_id=mrd.mrd_id,
            entity_scope="employee:42",
            attribute="position",
            old_value="nurse",
            new_value="duplicate",
            confirmed_by=user_id,
            difference_origin_code=ORIGIN_IMPORT_COMPARE,
        )
    nested.rollback()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_repository_supersession_chain(seed, db_tx) -> None:
    _require_wp_mrd_001()
    period = _report_period()
    user_id = int(seed["initiator_user_id"])

    repo = MrdSchemaRepository(db_tx)
    mrd = repo.insert_monthly_reference(
        report_period=period,
        version=1,
        created_by=user_id,
    )
    logical_key = f"lk:{uuid4().hex}"
    first = repo.insert_detected_difference(
        report_period=period,
        mrd_id=mrd.mrd_id,
        logical_key=logical_key,
        entity_scope="employee:42",
        attribute="position",
        business_type="PERIOD_CHANGED",
        difference_origin_code=ORIGIN_IMPORT_COMPARE,
        new_value="A",
    )
    db_tx.execute(
        text(
            """
            UPDATE public.hr_detected_differences
            SET lifecycle_status = 'SUPERSEDED'
            WHERE difference_id = :difference_id
            """
        ),
        {"difference_id": first.difference_id},
    )
    second = repo.insert_detected_difference(
        report_period=period,
        mrd_id=mrd.mrd_id,
        logical_key=logical_key,
        entity_scope="employee:42",
        attribute="position",
        business_type="PERIOD_CHANGED",
        difference_origin_code=ORIGIN_IMPORT_COMPARE,
        new_value="B",
        supersedes_difference_id=first.difference_id,
    )
    assert second.supersedes_difference_id == first.difference_id


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_repository_closed_mrd_blocks_entry_insert(seed, db_tx) -> None:
    _require_wp_mrd_001()
    period = _report_period()
    user_id = int(seed["initiator_user_id"])
    closed_at = datetime.now(timezone.utc)

    repo = MrdSchemaRepository(db_tx)
    mrd = repo.insert_monthly_reference(
        report_period=period,
        version=1,
        created_by=user_id,
        status="CLOSED",
        closed_at=closed_at,
        closed_by=user_id,
    )
    nested = db_tx.begin_nested()
    with pytest.raises(Exception):
        repo.insert_entry(
            mrd_id=mrd.mrd_id,
            entity_scope="employee:42",
            match_key=f"mk:{uuid4().hex}",
            canonical_hash="hash",
        )
    nested.rollback()
