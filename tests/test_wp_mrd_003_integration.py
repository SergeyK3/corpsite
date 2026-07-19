# tests/test_wp_mrd_003_integration.py
"""PostgreSQL integration tests for WP-MRD-003 fork / ACTIVE management."""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.mrd.application.active_mrd_service import require_active_mrd_for_period, resolve_active_mrd
from app.mrd.application.fork_period_service import ForkPeriodService
from app.mrd.application.fork_version_service import ForkVersionService
from app.mrd.domain.errors import (
    ActiveMrdMissingError,
    MrdCommandConflictError,
    MrdOptimisticConcurrencyConflictError,
    MrdPeriodExistsError,
    MrdPeriodWindowError,
)
from app.mrd.domain.period_window import get_creation_window_periods
from app.mrd.domain.fork_models import ForkPeriodCommand, ForkVersionCommand
from app.mrd.domain.types import (
    MRD_STATUS_ACTIVE,
    MRD_STATUS_CLOSED,
    REFERENCE_EVENT_ACTIVATE,
    REFERENCE_EVENT_CLOSE,
    REFERENCE_EVENT_CREATE,
    REFERENCE_EVENT_FORK_PERIOD,
)
from app.mrd.infrastructure.command_idempotency_repository import SqlAlchemyMrdCommandIdempotencyRepository
from app.mrd.infrastructure.repository import SqlAlchemyMrdRepository, mrd_tables_available
from tests.mrd_helpers import (
    insert_detected_difference,
    mrd_command_table_available,
    purge_mrd_report_period,
    seed_active_mrd,
    seed_mrd_entry,
    unique_report_period,
)


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
    if not mrd_command_table_available(conn):
        pytest.skip("WP-MRD-003 command idempotency schema not migrated")


def _command_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def _fork_services(conn):
    repo = SqlAlchemyMrdRepository(conn)
    idempotency = SqlAlchemyMrdCommandIdempotencyRepository(conn)
    return repo, ForkVersionService(repo, idempotency), ForkPeriodService(repo, idempotency)


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
def test_resolve_active_mrd(seed, db_tx) -> None:
    _require_schema(db_tx)
    period = unique_report_period()
    user_id = int(seed["initiator_user_id"])
    mrd_id = seed_active_mrd(db_tx, report_period=period, created_by=user_id)
    active = resolve_active_mrd(db_tx, period)
    assert active is not None
    assert active.mrd_id == mrd_id


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_require_active_missing_raises(seed, db_tx) -> None:
    _require_schema(db_tx)
    period = unique_report_period()
    purge_mrd_report_period(db_tx, period)
    with pytest.raises(ActiveMrdMissingError):
        require_active_mrd_for_period(db_tx, period)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_fork_version_from_active(seed, db_tx) -> None:
    _require_schema(db_tx)
    period = unique_report_period()
    user_id = int(seed["initiator_user_id"])
    source_id = seed_active_mrd(db_tx, report_period=period, created_by=user_id)
    seed_mrd_entry(db_tx, mrd_id=source_id, match_key="emp:100", payload={"position_raw": "Nurse"})
    _, fork_version, _ = _fork_services(db_tx)

    result = fork_version.fork_version(
        ForkVersionCommand(
            command_id=_command_id("fork-v-active"),
            source_mrd_id=source_id,
            performed_by=user_id,
            expected_active_row_version=1,
        )
    )

    assert result.target_version == 2
    assert result.closed_mrd_id == source_id
    assert result.copied_entry_count == 1
    assert result.idempotent_replay is False

    repo = SqlAlchemyMrdRepository(db_tx)
    source = repo.load_mrd(source_id)
    target = repo.load_mrd(result.target_mrd_id)
    assert source is not None and source.status == MRD_STATUS_CLOSED
    assert target is not None and target.status == MRD_STATUS_ACTIVE
    assert resolve_active_mrd(db_tx, period).mrd_id == result.target_mrd_id

    events = [row["event_type"] for row in repo.list_version_events(mrd_id=result.target_mrd_id)]
    assert REFERENCE_EVENT_CREATE in events
    assert REFERENCE_EVENT_ACTIVATE in events


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_fork_version_from_closed_while_other_active(seed, db_tx) -> None:
    _require_schema(db_tx)
    period = unique_report_period()
    user_id = int(seed["initiator_user_id"])
    v1_id = seed_active_mrd(db_tx, report_period=period, created_by=user_id)
    seed_mrd_entry(db_tx, mrd_id=v1_id, match_key="emp:old", payload={"position_raw": "Old"})
    _, fork_version, _ = _fork_services(db_tx)
    fork_version.fork_version(
        ForkVersionCommand(
            command_id=_command_id("fork-bootstrap-v2"),
            source_mrd_id=v1_id,
            performed_by=user_id,
        )
    )
    v2_id = require_active_mrd_for_period(db_tx, period).mrd_id
    seed_mrd_entry(db_tx, mrd_id=v2_id, match_key="emp:new", payload={"position_raw": "New"})

    result = fork_version.fork_version(
        ForkVersionCommand(
            command_id=_command_id("fork-v-closed"),
            source_mrd_id=v1_id,
            performed_by=user_id,
        )
    )

    assert result.target_version == 3
    assert result.closed_mrd_id == v2_id
    repo = SqlAlchemyMrdRepository(db_tx)
    target_entries = repo.load_mrd_entries(result.target_mrd_id)
    assert len(target_entries) == 1
    assert target_entries[0].match_key == "emp:old"
    closed_source_row = repo.load_mrd(v1_id)
    assert closed_source_row is not None and closed_source_row.status == MRD_STATUS_CLOSED


def _in_window_fork_pair():
    from datetime import date

    previous, current, _next = get_creation_window_periods(date.today())
    return previous, current


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_fork_period_creates_active_v1(seed, db_tx) -> None:
    _require_schema(db_tx)
    source_period, target_period = _in_window_fork_pair()
    user_id = int(seed["initiator_user_id"])
    purge_mrd_report_period(db_tx, source_period)
    purge_mrd_report_period(db_tx, target_period)
    source_id = seed_active_mrd(db_tx, report_period=source_period, created_by=user_id)
    seed_mrd_entry(db_tx, mrd_id=source_id, match_key="emp:200", payload={"position_raw": "Doctor"})
    _, _, fork_period = _fork_services(db_tx)

    result = fork_period.fork_period(
        ForkPeriodCommand(
            command_id=_command_id("fork-p"),
            source_mrd_id=source_id,
            target_report_period=target_period,
            performed_by=user_id,
        )
    )

    assert result.target_version == 1
    assert result.copied_entry_count == 1
    active = require_active_mrd_for_period(db_tx, target_period)
    assert active.mrd_id == result.target_mrd_id
    source = SqlAlchemyMrdRepository(db_tx).load_mrd(source_id)
    assert source is not None and source.status == MRD_STATUS_ACTIVE

    events = [
        row["event_type"]
        for row in SqlAlchemyMrdRepository(db_tx).list_version_events(mrd_id=result.target_mrd_id)
    ]
    assert events == [REFERENCE_EVENT_CREATE, REFERENCE_EVENT_FORK_PERIOD, REFERENCE_EVENT_ACTIVATE]


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_fork_does_not_copy_differences_or_confirmed_changes(seed, db_tx) -> None:
    _require_schema(db_tx)
    period = unique_report_period()
    user_id = int(seed["initiator_user_id"])
    source_id = seed_active_mrd(db_tx, report_period=period, created_by=user_id)
    seed_mrd_entry(db_tx, mrd_id=source_id, match_key="emp:300", payload={"position_raw": "Tech"})
    insert_detected_difference(
        db_tx,
        report_period=period,
        mrd_id=source_id,
        logical_key=f"{period.isoformat()}|{source_id}|emp:300|position_raw|roster",
        entity_scope="emp:300",
        attribute="position_raw",
        business_type="PERIOD_CHANGED",
        old_value="Tech",
        new_value="Lead",
    )
    db_tx.execute(
        text(
            """
            INSERT INTO public.hr_comparison_runs (batch_id, mrd_id, report_period, status)
            VALUES (NULL, :mrd_id, :report_period, 'COMPLETED')
            """
        ),
        {"mrd_id": source_id, "report_period": period},
    )
    repo = SqlAlchemyMrdRepository(db_tx)
    assert repo.count_differences_for_mrd(source_id) == 1
    assert repo.count_comparison_runs_for_mrd(source_id) == 1

    _, fork_version, _ = _fork_services(db_tx)
    result = fork_version.fork_version(
        ForkVersionCommand(
            command_id=_command_id("fork-no-copy"),
            source_mrd_id=source_id,
            performed_by=user_id,
        )
    )
    assert repo.count_differences_for_mrd(result.target_mrd_id) == 0
    assert repo.count_confirmed_changes_for_mrd(result.target_mrd_id) == 0
    assert repo.count_comparison_runs_for_mrd(result.target_mrd_id) == 0


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_fork_period_rejects_out_of_window(seed, db_tx) -> None:
    _require_schema(db_tx)
    source_period = unique_report_period()
    target_period = unique_report_period()
    user_id = int(seed["initiator_user_id"])
    source_id = seed_active_mrd(db_tx, report_period=source_period, created_by=user_id)
    _, _, fork_period = _fork_services(db_tx)

    with pytest.raises(MrdPeriodWindowError):
        fork_period.fork_period(
            ForkPeriodCommand(
                command_id=_command_id("fork-out-window"),
                source_mrd_id=source_id,
                target_report_period=target_period,
                performed_by=user_id,
            )
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_fork_period_rejects_duplicate_target_period(seed, db_tx) -> None:
    _require_schema(db_tx)
    source_period, target_period = _in_window_fork_pair()
    user_id = int(seed["initiator_user_id"])
    purge_mrd_report_period(db_tx, source_period)
    purge_mrd_report_period(db_tx, target_period)
    source_id = seed_active_mrd(db_tx, report_period=source_period, created_by=user_id)
    seed_active_mrd(db_tx, report_period=target_period, created_by=user_id)
    _, _, fork_period = _fork_services(db_tx)

    with pytest.raises(MrdPeriodExistsError):
        fork_period.fork_period(
            ForkPeriodCommand(
                command_id=_command_id("fork-dup-period"),
                source_mrd_id=source_id,
                target_report_period=target_period,
                performed_by=user_id,
            )
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_fork_version_idempotent_command_id(seed, db_tx) -> None:
    _require_schema(db_tx)
    period = unique_report_period()
    user_id = int(seed["initiator_user_id"])
    source_id = seed_active_mrd(db_tx, report_period=period, created_by=user_id)
    _, fork_version, _ = _fork_services(db_tx)
    command_id = _command_id("fork-idem")
    command = ForkVersionCommand(
        command_id=command_id,
        source_mrd_id=source_id,
        performed_by=user_id,
    )
    first = fork_version.fork_version(command)
    second = fork_version.fork_version(command)
    assert second.idempotent_replay is True
    assert second.target_mrd_id == first.target_mrd_id
    assert (
        db_tx.execute(
            text(
                """
                SELECT COUNT(*)::int
                FROM public.hr_monthly_references
                WHERE report_period = :report_period
                """
            ),
            {"report_period": period},
        ).scalar_one()
        == 2
    )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_fork_command_id_conflict_on_different_payload(seed, db_tx) -> None:
    _require_schema(db_tx)
    period = unique_report_period()
    user_id = int(seed["initiator_user_id"])
    source_id = seed_active_mrd(db_tx, report_period=period, created_by=user_id)
    _, fork_version, _ = _fork_services(db_tx)
    command_id = _command_id("fork-conflict")
    fork_version.fork_version(
        ForkVersionCommand(command_id=command_id, source_mrd_id=source_id, performed_by=user_id)
    )
    other_period = unique_report_period()
    other_source = seed_active_mrd(db_tx, report_period=other_period, created_by=user_id)
    with pytest.raises(MrdCommandConflictError):
        fork_version.fork_version(
            ForkVersionCommand(command_id=command_id, source_mrd_id=other_source, performed_by=user_id)
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_fork_version_optimistic_concurrency_on_active(seed, db_tx) -> None:
    _require_schema(db_tx)
    period = unique_report_period()
    user_id = int(seed["initiator_user_id"])
    source_id = seed_active_mrd(db_tx, report_period=period, created_by=user_id)
    _, fork_version, _ = _fork_services(db_tx)
    with pytest.raises(MrdOptimisticConcurrencyConflictError):
        fork_version.fork_version(
            ForkVersionCommand(
                command_id=_command_id("fork-stale"),
                source_mrd_id=source_id,
                performed_by=user_id,
                expected_active_row_version=99,
            )
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_fork_version_rollback_on_failure(seed, db_tx) -> None:
    _require_schema(db_tx)
    period = unique_report_period()
    user_id = int(seed["initiator_user_id"])
    source_id = seed_active_mrd(db_tx, report_period=period, created_by=user_id)
    repo, fork_version, _ = _fork_services(db_tx)
    original_create = repo.create_mrd_version

    def failing_create(**kwargs):
        raise RuntimeError("simulated fork failure")

    repo.create_mrd_version = failing_create  # type: ignore[method-assign]
    command_id = _command_id("fork-rollback")
    nested = db_tx.begin_nested()
    with pytest.raises(RuntimeError):
        fork_version.fork_version(
            ForkVersionCommand(
                command_id=command_id,
                source_mrd_id=source_id,
                performed_by=user_id,
            )
        )
    nested.rollback()
    repo.create_mrd_version = original_create  # type: ignore[method-assign]

    source = repo.load_mrd(source_id)
    assert source is not None and source.status == MRD_STATUS_ACTIVE
    assert resolve_active_mrd(db_tx, period).mrd_id == source_id
    pending = db_tx.execute(
        text(
            """
            SELECT 1
            FROM public.hr_mrd_command_executions
            WHERE command_id = :command_id
            """
        ),
        {"command_id": command_id},
    ).first()
    assert pending is None


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_second_active_same_period_blocked_by_db(seed, db_tx) -> None:
    _require_schema(db_tx)
    period = unique_report_period()
    user_id = int(seed["initiator_user_id"])
    seed_active_mrd(db_tx, report_period=period, created_by=user_id)
    with pytest.raises(Exception):
        seed_active_mrd(db_tx, report_period=period, created_by=user_id, version=2)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_version_event_journal_on_fork_version(seed, db_tx) -> None:
    _require_schema(db_tx)
    period = unique_report_period()
    user_id = int(seed["initiator_user_id"])
    source_id = seed_active_mrd(db_tx, report_period=period, created_by=user_id)
    _, fork_version, _ = _fork_services(db_tx)
    result = fork_version.fork_version(
        ForkVersionCommand(
            command_id=_command_id("fork-events"),
            source_mrd_id=source_id,
            performed_by=user_id,
        )
    )
    repo = SqlAlchemyMrdRepository(db_tx)
    close_events = repo.list_version_events(mrd_id=result.closed_mrd_id or source_id)
    assert any(row["event_type"] == REFERENCE_EVENT_CLOSE for row in close_events)
    target_events = [row["event_type"] for row in repo.list_version_events(mrd_id=result.target_mrd_id)]
    assert target_events == [REFERENCE_EVENT_CREATE, REFERENCE_EVENT_ACTIVATE]
