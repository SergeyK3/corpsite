"""Tests for persisted initial baseline source batch selection lifecycle."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.main import app
from app.services.hr_import_analytics_service import BatchDeleteBlockedError, assess_batch_delete, delete_batch
from app.services.hr_import_service import import_control_list
from app.services.hr_initial_baseline_source_service import (
    SELECTION_STATUS_CONSUMED,
    InitialBaselineSourceBatchPeriodMismatchError,
    InitialBaselineSourceSelectionFrozenError,
    consume_initial_baseline_source_selection,
    get_initial_baseline_source_selection,
    initial_baseline_source_table_available,
    list_initial_baseline_source_selections,
    set_initial_baseline_source_selection,
)
from tests.conftest import auth_headers, table_exists
from tests.hr_import_fixtures import cleanup_import_batch, write_control_list_workbook
from tests.mrd_helpers import purge_mrd_report_period, seed_active_mrd

client = TestClient(app)
JUNE_PERIOD = date(2026, 6, 1)


def _purge_initial_baseline_source_selections(conn, report_period: date) -> None:
    if not initial_baseline_source_table_available(conn):
        return
    conn.execute(
        text(
            """
            DELETE FROM public.hr_initial_baseline_source_selections
            WHERE report_period = :report_period
            """
        ),
        {"report_period": report_period},
    )


def _schema_available() -> bool:
    with engine.begin() as conn:
        return table_exists(conn, "hr_import_batches") and initial_baseline_source_table_available(conn)


def _lifecycle_available() -> bool:
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'hr_initial_baseline_source_selections'
                  AND column_name = 'lifecycle_status'
                """
            ),
        ).first()
        return row is not None


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def june_batches(seed, tmp_path: Path):
    if not _schema_available():
        pytest.skip("initial baseline source schema not applied")
    source = write_control_list_workbook(tmp_path, yymm="2606")
    batch_ids: list[int] = []
    with engine.begin() as conn:
        _purge_initial_baseline_source_selections(conn, JUNE_PERIOD)
        purge_mrd_report_period(conn, JUNE_PERIOD)
        for _ in range(2):
            batch_id, import_code, _ = import_control_list(
                conn,
                file_path=source,
                imported_by=int(seed["initiator_user_id"]),
            )
            batch_ids.append(int(batch_id))
    yield batch_ids
    with engine.begin() as conn:
        _purge_initial_baseline_source_selections(conn, JUNE_PERIOD)
        purge_mrd_report_period(conn, JUNE_PERIOD)
        for batch_id in batch_ids:
            cleanup_import_batch(conn, batch_id)


def test_set_initial_baseline_source_switches_between_batches(june_batches, seed):
    if not _lifecycle_available():
        pytest.skip("initial baseline source lifecycle columns missing")
    first_batch_id, second_batch_id = june_batches
    user_id = int(seed["initiator_user_id"])
    report_period = JUNE_PERIOD.isoformat()

    with engine.begin() as conn:
        first = set_initial_baseline_source_selection(
            conn,
            report_period=report_period,
            source_batch_id=first_batch_id,
            selected_by=user_id,
        )
        assert first["source_batch_id"] == first_batch_id
        assert first["lifecycle_status"] == "ACTIVE"
        assert first["mutable"] is True

        second = set_initial_baseline_source_selection(
            conn,
            report_period=report_period,
            source_batch_id=second_batch_id,
            selected_by=user_id,
        )
        assert second["source_batch_id"] == second_batch_id

        current = get_initial_baseline_source_selection(conn, report_period)
        assert current is not None
        assert current["source_batch_id"] == second_batch_id


def test_set_initial_baseline_source_rejects_period_mismatch(june_batches, seed):
    batch_id = june_batches[0]
    user_id = int(seed["initiator_user_id"])
    with engine.begin() as conn:
        with pytest.raises(InitialBaselineSourceBatchPeriodMismatchError):
            set_initial_baseline_source_selection(
                conn,
                report_period="2026-07-01",
                source_batch_id=batch_id,
                selected_by=user_id,
            )


def test_set_initial_baseline_source_blocked_when_active_mrd_exists(june_batches, seed):
    if not _lifecycle_available():
        pytest.skip("initial baseline source lifecycle columns missing")
    batch_id = june_batches[0]
    user_id = int(seed["initiator_user_id"])
    with engine.begin() as conn:
        set_initial_baseline_source_selection(
            conn,
            report_period=JUNE_PERIOD.isoformat(),
            source_batch_id=batch_id,
            selected_by=user_id,
        )
        seed_active_mrd(conn, report_period=JUNE_PERIOD, created_by=user_id)
        with pytest.raises(InitialBaselineSourceSelectionFrozenError):
            set_initial_baseline_source_selection(
                conn,
                report_period=JUNE_PERIOD.isoformat(),
                source_batch_id=june_batches[1],
                selected_by=user_id,
            )


def test_set_initial_baseline_source_blocked_when_period_has_only_closed_mrd(
    june_batches,
    seed,
):
    """Regression: freeze must not depend on ACTIVE status (CLOSED-only must stay frozen)."""
    if not _lifecycle_available():
        pytest.skip("initial baseline source lifecycle columns missing")
    batch_id = june_batches[0]
    user_id = int(seed["initiator_user_id"])
    with engine.begin() as conn:
        set_initial_baseline_source_selection(
            conn,
            report_period=JUNE_PERIOD.isoformat(),
            source_batch_id=batch_id,
            selected_by=user_id,
        )
        mrd_id = seed_active_mrd(conn, report_period=JUNE_PERIOD, created_by=user_id)
        conn.execute(
            text(
                """
                UPDATE public.hr_monthly_references
                SET status = 'CLOSED',
                    closed_at = NOW(),
                    closed_by = :closed_by
                WHERE mrd_id = :mrd_id
                """
            ),
            {"mrd_id": mrd_id, "closed_by": user_id},
        )
        active_count = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.hr_monthly_references
                WHERE report_period = :report_period
                  AND status = 'ACTIVE'
                """
            ),
            {"report_period": JUNE_PERIOD},
        ).scalar_one()
        assert int(active_count) == 0

        with pytest.raises(InitialBaselineSourceSelectionFrozenError):
            set_initial_baseline_source_selection(
                conn,
                report_period=JUNE_PERIOD.isoformat(),
                source_batch_id=june_batches[1],
                selected_by=user_id,
            )


def test_consume_initial_baseline_source_selection(june_batches, seed):
    if not _lifecycle_available():
        pytest.skip("initial baseline source lifecycle columns missing")
    batch_id = june_batches[0]
    user_id = int(seed["initiator_user_id"])
    with engine.begin() as conn:
        set_initial_baseline_source_selection(
            conn,
            report_period=JUNE_PERIOD.isoformat(),
            source_batch_id=batch_id,
            selected_by=user_id,
        )
        mrd_id = seed_active_mrd(conn, report_period=JUNE_PERIOD, created_by=user_id)
        consumed = consume_initial_baseline_source_selection(
            conn,
            report_period=JUNE_PERIOD.isoformat(),
            mrd_id=mrd_id,
        )
        assert consumed["lifecycle_status"] == SELECTION_STATUS_CONSUMED
        assert consumed["consumed_mrd_id"] == mrd_id
        assert consumed["mutable"] is False
        with pytest.raises(InitialBaselineSourceSelectionFrozenError):
            set_initial_baseline_source_selection(
                conn,
                report_period=JUNE_PERIOD.isoformat(),
                source_batch_id=june_batches[1],
                selected_by=user_id,
            )


def test_batch_delete_blocked_for_active_initial_baseline_source(june_batches, seed):
    if not _lifecycle_available():
        pytest.skip("initial baseline source lifecycle columns missing")
    batch_id = june_batches[0]
    user_id = int(seed["initiator_user_id"])
    with engine.begin() as conn:
        set_initial_baseline_source_selection(
            conn,
            report_period=JUNE_PERIOD.isoformat(),
            source_batch_id=batch_id,
            selected_by=user_id,
        )
        assessment = assess_batch_delete(conn, batch_id)
        assert assessment["blocked"] is True
        assert assessment["reasons"]
        with pytest.raises(BatchDeleteBlockedError):
            delete_batch(conn, batch_id)


def test_batch_delete_allowed_after_selection_consumed(june_batches, seed):
    if not _lifecycle_available():
        pytest.skip("initial baseline source lifecycle columns missing")
    batch_id = june_batches[0]
    user_id = int(seed["initiator_user_id"])
    with engine.begin() as conn:
        set_initial_baseline_source_selection(
            conn,
            report_period=JUNE_PERIOD.isoformat(),
            source_batch_id=batch_id,
            selected_by=user_id,
        )
        mrd_id = seed_active_mrd(conn, report_period=JUNE_PERIOD, created_by=user_id)
        consume_initial_baseline_source_selection(
            conn,
            report_period=JUNE_PERIOD.isoformat(),
            mrd_id=mrd_id,
        )
        assessment = assess_batch_delete(conn, batch_id)
        assert assessment["blocked"] is False


def test_initial_baseline_source_api_roundtrip(june_batches, privileged_headers):
    if not _lifecycle_available():
        pytest.skip("initial baseline source lifecycle columns missing")
    first_batch_id, second_batch_id = june_batches
    report_period = JUNE_PERIOD.isoformat()

    first_response = client.post(
        "/directory/personnel/import/initial-baseline-source",
        json={"report_period": report_period, "source_batch_id": first_batch_id},
        headers=privileged_headers,
    )
    assert first_response.status_code == 200
    assert first_response.json()["source_batch_id"] == first_batch_id
    assert first_response.json()["mutable"] is True

    second_response = client.post(
        "/directory/personnel/import/initial-baseline-source",
        json={"report_period": report_period, "source_batch_id": second_batch_id},
        headers=privileged_headers,
    )
    assert second_response.status_code == 200
    assert second_response.json()["source_batch_id"] == second_batch_id

    list_response = client.get(
        "/directory/personnel/import/initial-baseline-source",
        headers=privileged_headers,
    )
    assert list_response.status_code == 200
    june_items = [
        item
        for item in list_response.json()["items"]
        if item["report_period"] == report_period
    ]
    assert len(june_items) == 1
    assert june_items[0]["source_batch_id"] == second_batch_id
