# tests/test_wp_mrd_002_integration.py
"""PostgreSQL integration tests for WP-MRD-002."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.mrd.application.automatic_comparison_service import resolve_active_mrd, run_automatic_import_comparison
from app.mrd.application.confirm_service import ConfirmDifferenceService
from app.mrd.application.difference_producer import DifferenceProducer
from app.mrd.application.reconcile_service import DifferenceReconcileService
from app.mrd.application.reject_service import RejectDifferenceService
from app.mrd.domain.difference_models import ConfirmDifferenceCommand, CreateDifferenceCommand, RejectDifferenceCommand
from app.mrd.domain.errors import (
    DifferenceConfirmForbiddenError,
    DifferenceStateConflictError,
    MrdNotFoundError,
    MrdOptimisticConcurrencyConflictError,
)
from app.mrd.domain.logical_key import build_logical_key
from app.mrd.domain.types import (
    DIFFERENCE_BUSINESS_PERIOD_CHANGED,
    DIFFERENCE_LIFECYCLE_CONFIRMED,
    DIFFERENCE_LIFECYCLE_DETECTED,
    DIFFERENCE_LIFECYCLE_SUPERSEDED,
    ORIGIN_IMPORT_COMPARE,
    TECHNICAL_DIFF_CONFLICT,
)
from app.mrd.infrastructure.repository import MrdEntryRow, SqlAlchemyMrdRepository, mrd_tables_available
from app.services.hr_canonical_snapshot_service import compute_roster_match_key
from tests.mrd_helpers import seed_active_mrd, seed_import_batch, seed_import_row, seed_mrd_entry, unique_report_period


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


def _row_match_key(conn, row_id: int) -> str:
    row = conn.execute(
        text(
            """
            SELECT employee_id, normalized_payload
            FROM public.hr_import_rows
            WHERE row_id = :row_id
            """
        ),
        {"row_id": row_id},
    ).mappings().one()
    payload = dict(row["normalized_payload"] or {})
    employee_id = int(row["employee_id"]) if row["employee_id"] is not None else None
    return compute_roster_match_key(
        employee_id=employee_id,
        iin=str(payload.get("iin") or ""),
        full_name=str(payload.get("full_name") or ""),
        birth_date=payload.get("birth_date"),
        row_id=row_id,
    )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_resolve_active_mrd(seed, db_tx) -> None:
    _require_mrd_schema()
    period = unique_report_period()
    user_id = int(seed["initiator_user_id"])
    mrd_id = seed_active_mrd(db_tx, report_period=period, created_by=user_id)

    resolved = resolve_active_mrd(db_tx, period)
    assert resolved is not None
    assert resolved.mrd_id == mrd_id
    assert resolved.status == "ACTIVE"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_automatic_compare_idempotent(seed, db_tx) -> None:
    _require_mrd_schema()
    period = unique_report_period()
    user_id = int(seed["initiator_user_id"])
    unit_id = int(seed["unit_id"])
    mrd_id = seed_active_mrd(db_tx, report_period=period, created_by=user_id)

    batch_id = seed_import_batch(db_tx, imported_by=user_id, report_period=period)
    row_id = seed_import_row(
        db_tx,
        batch_id=batch_id,
        full_name="Test User",
        iin="900101350123",
        position="Senior Nurse",
        org_unit_id=unit_id,
    )
    match_key = _row_match_key(db_tx, row_id)
    seed_mrd_entry(
        db_tx,
        mrd_id=mrd_id,
        match_key=match_key,
        payload={"full_name": "Test User", "iin": "900101350123", "position_raw": "Nurse"},
    )

    first = run_automatic_import_comparison(db_tx, batch_id, started_by=user_id)
    second = run_automatic_import_comparison(db_tx, batch_id, started_by=user_id)

    repo = SqlAlchemyMrdRepository(db_tx)
    differences = repo.list_differences_for_mrd(mrd_id)
    open_detected = [d for d in differences if d.lifecycle_status == DIFFERENCE_LIFECYCLE_DETECTED]
    assert len(open_detected) >= 1
    assert first.stats["candidate_count"] == second.stats["candidate_count"]
    assert second.stats.get("kept_detected", 0) >= 1


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_supersession_chain_on_candidate_change(seed, db_tx) -> None:
    _require_mrd_schema()
    period = unique_report_period()
    user_id = int(seed["initiator_user_id"])
    unit_id = int(seed["unit_id"])
    mrd_id = seed_active_mrd(db_tx, report_period=period, created_by=user_id)

    batch_id = seed_import_batch(db_tx, imported_by=user_id, report_period=period)
    row_id = seed_import_row(
        db_tx,
        batch_id=batch_id,
        full_name="Chain User",
        iin="900201350123",
        position="Senior Nurse",
        org_unit_id=unit_id,
    )
    match_key = _row_match_key(db_tx, row_id)
    seed_mrd_entry(
        db_tx,
        mrd_id=mrd_id,
        match_key=match_key,
        payload={"full_name": "Chain User", "position_raw": "Nurse"},
    )

    run_automatic_import_comparison(db_tx, batch_id, started_by=user_id)
    db_tx.execute(
        text(
            """
            UPDATE public.hr_import_rows
            SET normalized_payload = jsonb_set(
                normalized_payload, '{position_raw}', '"Chief Nurse"'::jsonb, true
            )
            WHERE row_id = :row_id
            """
        ),
        {"row_id": row_id},
    )
    run_automatic_import_comparison(db_tx, batch_id, started_by=user_id)

    repo = SqlAlchemyMrdRepository(db_tx)
    rows = repo.list_differences_for_mrd(mrd_id)
    position_rows = [r for r in rows if r.attribute == "position_raw"]
    assert any(r.lifecycle_status == DIFFERENCE_LIFECYCLE_SUPERSEDED for r in position_rows)
    assert any(r.lifecycle_status == DIFFERENCE_LIFECYCLE_DETECTED for r in position_rows)
    detected = [r for r in position_rows if r.lifecycle_status == DIFFERENCE_LIFECYCLE_DETECTED]
    assert detected[0].supersedes_difference_id is not None


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_confirmed_not_recreated_on_recompare(seed, db_tx) -> None:
    _require_mrd_schema()
    period = unique_report_period()
    user_id = int(seed["initiator_user_id"])
    mrd_id = seed_active_mrd(db_tx, report_period=period, created_by=user_id)
    repo = SqlAlchemyMrdRepository(db_tx)
    logical_key = build_logical_key(
        report_period=period,
        mrd_id=mrd_id,
        entity_scope="emp:9003",
        attribute="position_raw",
        record_kind="roster",
    )
    diff = repo.insert_difference(
        CreateDifferenceCommand(
            report_period=period,
            mrd_id=mrd_id,
            logical_key=logical_key,
            entity_scope="emp:9003",
            attribute="position_raw",
            business_type=DIFFERENCE_BUSINESS_PERIOD_CHANGED,
            difference_origin_code=ORIGIN_IMPORT_COMPARE,
            origin_context={"batch_id": 1, "match_key": "emp:9003"},
            old_value="Nurse",
            new_value="Senior",
            record_kind="roster",
            technical_diff_class="CHANGED",
        )
    )
    repo.mark_confirmed(
        diff.difference_id,
        expected_row_version=1,
        confirmed_by=user_id,
        confirmed_at=datetime.now(timezone.utc),
    )

    producer = DifferenceProducer(repo)
    reconcile = DifferenceReconcileService(repo, producer)
    from app.mrd.domain.comparison_models import ComparisonCandidate

    candidate = ComparisonCandidate(
        report_period=period,
        mrd_id=mrd_id,
        entity_scope="emp:9003",
        attribute="position_raw",
        business_type=DIFFERENCE_BUSINESS_PERIOD_CHANGED,
        technical_diff_class="CHANGED",
        old_value="Nurse",
        new_value="Senior",
        record_kind="roster",
        origin_context={"batch_id": 2, "match_key": "emp:9003"},
    )
    stats = reconcile.reconcile_import_compare(
        mrd_id=mrd_id,
        comparison_run_id=1,
        candidates=[candidate],
    )
    assert stats["skipped_terminal"] == 1
    confirmed_count = sum(
        1 for r in repo.list_differences_for_mrd(mrd_id) if r.lifecycle_status == DIFFERENCE_LIFECYCLE_CONFIRMED
    )
    assert confirmed_count == 1


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_confirm_updates_mrd_entry(seed, db_tx) -> None:
    _require_mrd_schema()
    period = unique_report_period()
    user_id = int(seed["initiator_user_id"])
    mrd_id = seed_active_mrd(db_tx, report_period=period, created_by=user_id)
    match_key = "emp:9004"
    seed_mrd_entry(
        db_tx,
        mrd_id=mrd_id,
        match_key=match_key,
        payload={"full_name": "Confirm User", "position_raw": "Nurse"},
    )
    repo = SqlAlchemyMrdRepository(db_tx)
    diff = repo.insert_difference(
        CreateDifferenceCommand(
            report_period=period,
            mrd_id=mrd_id,
            logical_key=build_logical_key(
                report_period=period,
                mrd_id=mrd_id,
                entity_scope=match_key,
                attribute="position_raw",
                record_kind="roster",
            ),
            entity_scope=match_key,
            attribute="position_raw",
            business_type=DIFFERENCE_BUSINESS_PERIOD_CHANGED,
            difference_origin_code=ORIGIN_IMPORT_COMPARE,
            origin_context={"batch_id": 1, "match_key": match_key},
            old_value="Nurse",
            new_value="Senior Nurse",
            record_kind="roster",
            technical_diff_class="CHANGED",
        )
    )
    mrd_before = repo.load_mrd(mrd_id)
    result = ConfirmDifferenceService(repo).confirm(
        ConfirmDifferenceCommand(
            difference_id=diff.difference_id,
            confirmed_by=user_id,
            expected_row_version=1,
        )
    )
    entry = repo.load_entry_by_match_key(mrd_id=mrd_id, match_key=match_key)
    assert result.confirmed_change_id > 0
    assert entry is not None
    assert entry.effective_payload["position_raw"] == "Senior Nurse"
    mrd_after = repo.load_mrd(mrd_id)
    assert mrd_after is not None and mrd_before is not None
    assert mrd_after.version == mrd_before.version


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_reject_does_not_change_mrd(seed, db_tx) -> None:
    _require_mrd_schema()
    period = unique_report_period()
    user_id = int(seed["initiator_user_id"])
    mrd_id = seed_active_mrd(db_tx, report_period=period, created_by=user_id)
    match_key = "emp:9005"
    seed_mrd_entry(
        db_tx,
        mrd_id=mrd_id,
        match_key=match_key,
        payload={"position_raw": "Nurse"},
    )
    repo = SqlAlchemyMrdRepository(db_tx)
    diff = repo.insert_difference(
        CreateDifferenceCommand(
            report_period=period,
            mrd_id=mrd_id,
            logical_key=build_logical_key(
                report_period=period,
                mrd_id=mrd_id,
                entity_scope=match_key,
                attribute="position_raw",
                record_kind="roster",
            ),
            entity_scope=match_key,
            attribute="position_raw",
            business_type=DIFFERENCE_BUSINESS_PERIOD_CHANGED,
            difference_origin_code=ORIGIN_IMPORT_COMPARE,
            origin_context={"batch_id": 1, "match_key": match_key},
            old_value="Nurse",
            new_value="Senior",
            record_kind="roster",
            technical_diff_class="CHANGED",
        )
    )
    entry_before = repo.load_entry_by_match_key(mrd_id=mrd_id, match_key=match_key)
    RejectDifferenceService(repo).reject(
        RejectDifferenceCommand(
            difference_id=diff.difference_id,
            rejected_by=user_id,
            expected_row_version=1,
            basis="not valid",
        )
    )
    entry_after = repo.load_entry_by_match_key(mrd_id=mrd_id, match_key=match_key)
    assert entry_after is not None and entry_before is not None
    assert entry_after.effective_payload == entry_before.effective_payload
    assert repo.count_confirmed_changes_for_mrd(mrd_id) == 0


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_confirm_closed_mrd_forbidden(seed, db_tx) -> None:
    _require_mrd_schema()
    period = unique_report_period()
    user_id = int(seed["initiator_user_id"])
    closed_mrd_id = int(
        db_tx.execute(
            text(
                """
                INSERT INTO public.hr_monthly_references (
                    report_period, version, status, created_by, closed_at, closed_by
                )
                VALUES (:period, 1, 'CLOSED', :user_id, NOW(), :user_id)
                RETURNING mrd_id
                """
            ),
            {"period": period, "user_id": user_id},
        ).scalar_one()
    )
    seed_active_mrd(db_tx, report_period=period, created_by=user_id, version=2)
    repo = SqlAlchemyMrdRepository(db_tx)
    diff = repo.insert_difference(
        CreateDifferenceCommand(
            report_period=period,
            mrd_id=closed_mrd_id,
            logical_key=build_logical_key(
                report_period=period,
                mrd_id=closed_mrd_id,
                entity_scope="emp:9006",
                attribute="position_raw",
                record_kind="roster",
            ),
            entity_scope="emp:9006",
            attribute="position_raw",
            business_type=DIFFERENCE_BUSINESS_PERIOD_CHANGED,
            difference_origin_code=ORIGIN_IMPORT_COMPARE,
            origin_context={"batch_id": 1, "match_key": "emp:9006"},
            old_value="A",
            new_value="B",
            record_kind="roster",
            technical_diff_class="CHANGED",
        )
    )
    with pytest.raises(MrdNotFoundError):
        ConfirmDifferenceService(repo).confirm(
            ConfirmDifferenceCommand(
                difference_id=diff.difference_id,
                confirmed_by=user_id,
                expected_row_version=1,
            )
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_confirm_reject_not_from_detected(seed, db_tx) -> None:
    _require_mrd_schema()
    period = unique_report_period()
    user_id = int(seed["initiator_user_id"])
    mrd_id = seed_active_mrd(db_tx, report_period=period, created_by=user_id)
    repo = SqlAlchemyMrdRepository(db_tx)
    diff = repo.insert_difference(
        CreateDifferenceCommand(
            report_period=period,
            mrd_id=mrd_id,
            logical_key=build_logical_key(
                report_period=period,
                mrd_id=mrd_id,
                entity_scope="emp:9007",
                attribute="position_raw",
                record_kind="roster",
            ),
            entity_scope="emp:9007",
            attribute="position_raw",
            business_type=DIFFERENCE_BUSINESS_PERIOD_CHANGED,
            difference_origin_code=ORIGIN_IMPORT_COMPARE,
            origin_context={"batch_id": 1, "match_key": "emp:9007"},
            old_value="A",
            new_value="B",
            record_kind="roster",
            technical_diff_class="CHANGED",
        )
    )
    repo.mark_rejected(
        diff.difference_id,
        expected_row_version=1,
        rejected_by=user_id,
        rejected_at=datetime.now(timezone.utc),
        basis=None,
    )
    with pytest.raises(DifferenceStateConflictError):
        ConfirmDifferenceService(repo).confirm(
            ConfirmDifferenceCommand(
                difference_id=diff.difference_id,
                confirmed_by=user_id,
                expected_row_version=2,
            )
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_confirm_conflict_technical_class_forbidden(seed, db_tx) -> None:
    _require_mrd_schema()
    period = unique_report_period()
    user_id = int(seed["initiator_user_id"])
    mrd_id = seed_active_mrd(db_tx, report_period=period, created_by=user_id)
    repo = SqlAlchemyMrdRepository(db_tx)
    diff = repo.insert_difference(
        CreateDifferenceCommand(
            report_period=period,
            mrd_id=mrd_id,
            logical_key=build_logical_key(
                report_period=period,
                mrd_id=mrd_id,
                entity_scope="emp:9008",
                attribute="__conflict__",
                record_kind="roster",
            ),
            entity_scope="emp:9008",
            attribute="__conflict__",
            business_type=DIFFERENCE_BUSINESS_PERIOD_CHANGED,
            difference_origin_code=ORIGIN_IMPORT_COMPARE,
            origin_context={"batch_id": 1, "match_key": "emp:9008"},
            old_value={},
            new_value={},
            record_kind="roster",
            technical_diff_class=TECHNICAL_DIFF_CONFLICT,
        )
    )
    with pytest.raises(DifferenceConfirmForbiddenError):
        ConfirmDifferenceService(repo).confirm(
            ConfirmDifferenceCommand(
                difference_id=diff.difference_id,
                confirmed_by=user_id,
                expected_row_version=1,
            )
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_compare_does_not_mutate_mrd_entries(seed, db_tx) -> None:
    _require_mrd_schema()
    period = unique_report_period()
    user_id = int(seed["initiator_user_id"])
    unit_id = int(seed["unit_id"])
    mrd_id = seed_active_mrd(db_tx, report_period=period, created_by=user_id)

    batch_id = seed_import_batch(db_tx, imported_by=user_id, report_period=period)
    row_id = seed_import_row(
        db_tx,
        batch_id=batch_id,
        full_name="Compare User",
        iin="901001350123",
        position="Senior",
        org_unit_id=unit_id,
    )
    match_key = _row_match_key(db_tx, row_id)
    seed_mrd_entry(
        db_tx,
        mrd_id=mrd_id,
        match_key=match_key,
        payload={"position_raw": "Nurse"},
    )
    before = SqlAlchemyMrdRepository(db_tx).load_mrd_entries(mrd_id)
    run_automatic_import_comparison(db_tx, batch_id, started_by=user_id)
    after = SqlAlchemyMrdRepository(db_tx).load_mrd_entries(mrd_id)
    assert before[0].effective_payload == after[0].effective_payload


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_confirm_transaction_rollback_on_mrd_entry_conflict(seed, db_tx) -> None:
    _require_mrd_schema()
    period = unique_report_period()
    user_id = int(seed["initiator_user_id"])
    mrd_id = seed_active_mrd(db_tx, report_period=period, created_by=user_id)
    match_key = "emp:9011"
    seed_mrd_entry(
        db_tx,
        mrd_id=mrd_id,
        match_key=match_key,
        payload={"position_raw": "Nurse"},
    )
    repo = SqlAlchemyMrdRepository(db_tx)
    diff = repo.insert_difference(
        CreateDifferenceCommand(
            report_period=period,
            mrd_id=mrd_id,
            logical_key=build_logical_key(
                report_period=period,
                mrd_id=mrd_id,
                entity_scope=match_key,
                attribute="position_raw",
                record_kind="roster",
            ),
            entity_scope=match_key,
            attribute="position_raw",
            business_type=DIFFERENCE_BUSINESS_PERIOD_CHANGED,
            difference_origin_code=ORIGIN_IMPORT_COMPARE,
            origin_context={"batch_id": 1, "match_key": match_key},
            old_value="Nurse",
            new_value="Senior",
            record_kind="roster",
            technical_diff_class="CHANGED",
        )
    )
    entry = repo.load_entry_by_match_key(mrd_id=mrd_id, match_key=match_key)
    assert entry is not None
    stale_entry = MrdEntryRow(
        entry_id=entry.entry_id,
        mrd_id=entry.mrd_id,
        match_key=entry.match_key,
        entity_scope=entry.entity_scope,
        record_kind=entry.record_kind,
        canonical_hash=entry.canonical_hash,
        effective_payload=dict(entry.effective_payload),
        row_version=entry.row_version,
    )
    db_tx.execute(
        text(
            """
            UPDATE public.hr_monthly_reference_entries
            SET row_version = row_version + 1
            WHERE mrd_id = :mrd_id AND match_key = :match_key
            """
        ),
        {"mrd_id": mrd_id, "match_key": match_key},
    )
    original_load = repo.load_entry_by_match_key

    def stale_load(*, mrd_id: int, match_key: str) -> MrdEntryRow | None:
        row = original_load(mrd_id=mrd_id, match_key=match_key)
        if row is not None and row.entry_id == stale_entry.entry_id:
            return stale_entry
        return row

    repo.load_entry_by_match_key = stale_load  # type: ignore[method-assign]

    nested = db_tx.begin_nested()
    with pytest.raises(MrdOptimisticConcurrencyConflictError):
        ConfirmDifferenceService(repo).confirm(
            ConfirmDifferenceCommand(
                difference_id=diff.difference_id,
                confirmed_by=user_id,
                expected_row_version=1,
            )
        )
    nested.rollback()

    reloaded = repo.load_difference(diff.difference_id)
    assert reloaded is not None
    assert reloaded.lifecycle_status == DIFFERENCE_LIFECYCLE_DETECTED
    assert repo.count_confirmed_changes_for_mrd(mrd_id) == 0
