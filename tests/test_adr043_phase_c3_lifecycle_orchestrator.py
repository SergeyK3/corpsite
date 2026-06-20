# tests/test_adr043_phase_c3_lifecycle_orchestrator.py
"""Tests for ADR-043 Phase C3 lifecycle orchestrator."""
from __future__ import annotations

import json
from contextlib import contextmanager
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.hr_effective_monthly_diff_service import EffectiveMonthlyDiffError
from app.services.hr_personnel_lifecycle_service import (
    PersonnelLifecycleError,
    run_monthly_personnel_lifecycle,
)
from tests.conftest import insert_returning_id, table_exists

PHASE_C3_TABLES = (
    "hr_personnel_lifecycle_runs",
    "hr_personnel_change_events",
    "hr_snapshot_effective_entries",
    "hr_canonical_snapshots",
    "hr_canonical_snapshot_entries",
    "persons",
    "person_assignments",
)


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _require_c3() -> None:
    with engine.begin() as conn:
        if not all(table_exists(conn, table) for table in PHASE_C3_TABLES):
            pytest.skip("ADR-043 Phase C3 tables missing — run: alembic upgrade head")


@contextmanager
def _isolated_conn():
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            yield conn
        finally:
            trans.rollback()


def _insert_batch(conn, user_id: int) -> int:
    return conn.execute(
        text(
            """
            INSERT INTO public.hr_import_batches (
                source_type, file_name, imported_by, status,
                total_rows, valid_rows, error_rows
            )
            VALUES ('HR_CONTROL_LIST', :file_name, :uid, 'PARSED', 1, 1, 0)
            RETURNING batch_id
            """
        ),
        {"file_name": f"c3_{uuid4().hex[:8]}.xlsx", "uid": user_id},
    ).scalar_one()


def _insert_snapshot(conn, *, user_id: int, version: int) -> int:
    return insert_returning_id(
        conn,
        table="hr_canonical_snapshots",
        id_col="snapshot_id",
        values={
            "source_batch_id": _insert_batch(conn, user_id),
            "source_type": "HR_CONTROL_LIST",
            "version": version,
            "status": "superseded",
            "entry_count": 0,
            "promoted_by": user_id,
        },
    )


def _insert_roster_entry(conn, *, snapshot_id: int, match_key: str, payload: dict) -> int:
    return insert_returning_id(
        conn,
        table="hr_canonical_snapshot_entries",
        id_col="entry_id",
        values={
            "snapshot_id": snapshot_id,
            "entity_scope": match_key,
            "record_kind": "roster",
            "match_key": match_key,
            "canonical_hash": "c3" + uuid4().hex,
            "payload": json.dumps(payload),
        },
    )


def _setup_snapshot_pair(
    conn,
    *,
    user_id: int,
    prior_entries: dict[str, dict],
    new_entries: dict[str, dict],
) -> tuple[int, int]:
    base_version = 920_000 + int(uuid4().hex[:3], 16)
    prior_id = _insert_snapshot(conn, user_id=user_id, version=base_version)
    new_id = _insert_snapshot(conn, user_id=user_id, version=base_version + 1)
    for match_key, payload in prior_entries.items():
        _insert_roster_entry(conn, snapshot_id=prior_id, match_key=match_key, payload=payload)
    for match_key, payload in new_entries.items():
        _insert_roster_entry(conn, snapshot_id=new_id, match_key=match_key, payload=payload)
    return prior_id, new_id


def _count_table(conn, table: str) -> int:
    return int(conn.execute(text(f"SELECT COUNT(*) FROM public.{table}")).scalar_one())


def _count_lifecycle_runs(conn, prior_id: int, new_id: int) -> int:
    return int(
        conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.hr_personnel_lifecycle_runs
                WHERE previous_snapshot_id = :prior AND snapshot_id = :new
                """
            ),
            {"prior": prior_id, "new": new_id},
        ).scalar_one()
    )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_dry_run_changes_nothing(seed):
    _require_c3()
    suffix = uuid4().hex[:8]
    existing = f"name:c3-dry-existing-{suffix}"
    newcomer = f"name:c3-dry-new-{suffix}"
    base = {"full_name": "Existing", "department": "A", "position_raw": "Doc", "org_unit_id": seed["unit_id"]}

    with _isolated_conn() as conn:
        prior_id, new_id = _setup_snapshot_pair(
            conn,
            user_id=seed["executor_user_id"],
            prior_entries={existing: base},
            new_entries={
                existing: base,
                newcomer: {"full_name": "New", "department": "B", "position_raw": "Nurse", "org_unit_id": seed["unit_id"]},
            },
        )
        persons_before = _count_table(conn, "persons")
        events_before = _count_table(conn, "hr_personnel_change_events")
        enrollment_before = _count_table(conn, "enrollment_queue") if table_exists(conn, "enrollment_queue") else 0

        report = run_monthly_personnel_lifecycle(
            conn=conn,
            previous_snapshot_id=prior_id,
            snapshot_id=new_id,
            dry_run=True,
            refresh_cache=True,
            enqueue=True,
            sync_persons=True,
            actor_user_id=seed["executor_user_id"],
        )

        assert report["dry_run"] is True
        assert report["run_status"] == "completed"
        assert _count_table(conn, "persons") == persons_before
        assert _count_table(conn, "hr_personnel_change_events") == events_before
        if table_exists(conn, "enrollment_queue"):
            assert _count_table(conn, "enrollment_queue") == enrollment_before
        assert report["personnel_events"]["planned_count"] > 0


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_execute_creates_lifecycle_run(seed):
    _require_c3()
    suffix = uuid4().hex[:8]
    person = f"name:c3-run-{suffix}"

    with _isolated_conn() as conn:
        prior_id, new_id = _setup_snapshot_pair(
            conn,
            user_id=seed["executor_user_id"],
            prior_entries={},
            new_entries={
                person: {
                    "full_name": "Run Person",
                    "department": "A",
                    "position_raw": "Doc",
                    "org_unit_id": seed["unit_id"],
                }
            },
        )
        before = _count_lifecycle_runs(conn, prior_id, new_id)
        report = run_monthly_personnel_lifecycle(
            conn=conn,
            previous_snapshot_id=prior_id,
            snapshot_id=new_id,
            dry_run=False,
            refresh_cache=True,
            enqueue=False,
            sync_persons=False,
            actor_user_id=seed["executor_user_id"],
        )
        after = _count_lifecycle_runs(conn, prior_id, new_id)
        assert after == before + 1
        assert report["run_id"] is not None
        row = conn.execute(
            text(
                """
                SELECT status, dry_run, refresh_cache, enqueue, sync_persons
                FROM public.hr_personnel_lifecycle_runs
                WHERE run_id = :rid
                """
            ),
            {"rid": int(report["run_id"])},
        ).mappings().one()
        assert row["status"] == "completed"
        assert row["dry_run"] is False


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_execute_populates_lifecycle_report(seed):
    _require_c3()
    suffix = uuid4().hex[:8]
    person = f"name:c3-report-{suffix}"

    with _isolated_conn() as conn:
        prior_id, new_id = _setup_snapshot_pair(
            conn,
            user_id=seed["executor_user_id"],
            prior_entries={},
            new_entries={
                person: {
                    "full_name": "Report Person",
                    "department": "A",
                    "position_raw": "Doc",
                    "org_unit_id": seed["unit_id"],
                }
            },
        )
        report = run_monthly_personnel_lifecycle(
            conn=conn,
            previous_snapshot_id=prior_id,
            snapshot_id=new_id,
            dry_run=False,
            refresh_cache=True,
            enqueue=True,
            sync_persons=True,
            actor_user_id=seed["executor_user_id"],
        )
        assert "effective_cache" in report
        assert "monthly_diff" in report
        assert "personnel_events" in report
        assert "enrollment" in report
        assert "person_sync" in report
        assert "validation" in report
        assert report["duration_ms"] >= 0
        assert report["personnel_events"]["events_created"] > 0


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_rerun_does_not_duplicate_events(seed):
    _require_c3()
    suffix = uuid4().hex[:8]
    person = f"name:c3-idem-events-{suffix}"

    with _isolated_conn() as conn:
        prior_id, new_id = _setup_snapshot_pair(
            conn,
            user_id=seed["executor_user_id"],
            prior_entries={},
            new_entries={
                person: {
                    "full_name": "Once",
                    "department": "A",
                    "position_raw": "Doc",
                    "org_unit_id": seed["unit_id"],
                }
            },
        )
        first = run_monthly_personnel_lifecycle(
            conn=conn,
            previous_snapshot_id=prior_id,
            snapshot_id=new_id,
            dry_run=False,
            refresh_cache=True,
            enqueue=False,
            sync_persons=False,
            actor_user_id=seed["executor_user_id"],
        )
        events_after_first = _count_table(conn, "hr_personnel_change_events")
        second = run_monthly_personnel_lifecycle(
            conn=conn,
            previous_snapshot_id=prior_id,
            snapshot_id=new_id,
            dry_run=False,
            refresh_cache=True,
            enqueue=False,
            sync_persons=False,
            actor_user_id=seed["executor_user_id"],
        )
        assert first["personnel_events"]["events_created"] > 0
        assert second["personnel_events"]["events_created"] == 0
        assert second["personnel_events"]["events_existing"] >= first["personnel_events"]["events_created"]
        assert _count_table(conn, "hr_personnel_change_events") == events_after_first


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_rerun_does_not_duplicate_enrollment(seed):
    _require_c3()
    suffix = uuid4().hex[:8]
    person = f"name:c3-idem-enroll-{suffix}"

    with _isolated_conn() as conn:
        if not table_exists(conn, "enrollment_queue"):
            pytest.skip("enrollment_queue missing")
        prior_id, new_id = _setup_snapshot_pair(
            conn,
            user_id=seed["executor_user_id"],
            prior_entries={},
            new_entries={
                person: {
                    "full_name": "Enroll Once",
                    "department": "A",
                    "position_raw": "Doc",
                    "org_unit_id": seed["unit_id"],
                }
            },
        )
        first = run_monthly_personnel_lifecycle(
            conn=conn,
            previous_snapshot_id=prior_id,
            snapshot_id=new_id,
            dry_run=False,
            refresh_cache=True,
            enqueue=True,
            sync_persons=False,
            actor_user_id=seed["executor_user_id"],
        )
        enrollment_after_first = _count_table(conn, "enrollment_queue")
        second = run_monthly_personnel_lifecycle(
            conn=conn,
            previous_snapshot_id=prior_id,
            snapshot_id=new_id,
            dry_run=False,
            refresh_cache=True,
            enqueue=True,
            sync_persons=False,
            actor_user_id=seed["executor_user_id"],
        )
        assert first["enrollment"]["created"] >= 1
        assert second["enrollment"]["existing"] >= 1
        assert _count_table(conn, "enrollment_queue") == enrollment_after_first


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_rerun_does_not_duplicate_assignments(seed):
    _require_c3()
    suffix = uuid4().hex[:8]
    person = f"name:c3-idem-assign-{suffix}"

    with _isolated_conn() as conn:
        prior_id, new_id = _setup_snapshot_pair(
            conn,
            user_id=seed["executor_user_id"],
            prior_entries={},
            new_entries={
                person: {
                    "full_name": "Assign Once",
                    "department": "A",
                    "position_raw": "Doc",
                    "org_unit_id": seed["unit_id"],
                }
            },
        )
        first = run_monthly_personnel_lifecycle(
            conn=conn,
            previous_snapshot_id=prior_id,
            snapshot_id=new_id,
            dry_run=False,
            refresh_cache=True,
            enqueue=False,
            sync_persons=True,
            actor_user_id=seed["executor_user_id"],
        )
        assignments_after_first = _count_table(conn, "person_assignments")
        second = run_monthly_personnel_lifecycle(
            conn=conn,
            previous_snapshot_id=prior_id,
            snapshot_id=new_id,
            dry_run=False,
            refresh_cache=True,
            enqueue=False,
            sync_persons=True,
            actor_user_id=seed["executor_user_id"],
        )
        assert first["person_sync"]["assignments_created"] >= 1
        assert second["person_sync"]["assignments_created"] == 0
        assert _count_table(conn, "person_assignments") == assignments_after_first


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_failed_stage_marks_run_failed(seed, monkeypatch):
    _require_c3()
    suffix = uuid4().hex[:8]
    person = f"name:c3-fail-{suffix}"

    def _boom(*args, **kwargs):
        raise EffectiveMonthlyDiffError("synthetic monthly diff failure")

    monkeypatch.setattr(
        "app.services.hr_personnel_lifecycle_service.run_effective_monthly_diff",
        _boom,
    )

    with _isolated_conn() as conn:
        prior_id, new_id = _setup_snapshot_pair(
            conn,
            user_id=seed["executor_user_id"],
            prior_entries={},
            new_entries={
                person: {
                    "full_name": "Fail Person",
                    "department": "A",
                    "position_raw": "Doc",
                    "org_unit_id": seed["unit_id"],
                }
            },
        )
        with pytest.raises(PersonnelLifecycleError) as exc_info:
            run_monthly_personnel_lifecycle(
                conn=conn,
                previous_snapshot_id=prior_id,
                snapshot_id=new_id,
                dry_run=False,
                refresh_cache=True,
                enqueue=False,
                sync_persons=False,
                actor_user_id=seed["executor_user_id"],
            )
        assert exc_info.value.stage == "monthly_diff"
        row = conn.execute(
            text(
                """
                SELECT status, errors_count
                FROM public.hr_personnel_lifecycle_runs
                WHERE previous_snapshot_id = :prior AND snapshot_id = :new
                ORDER BY run_id DESC
                LIMIT 1
                """
            ),
            {"prior": prior_id, "new": new_id},
        ).mappings().one()
        assert row["status"] == "failed"
        assert int(row["errors_count"]) >= 1


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_partial_pipeline_enqueue_without_sync(seed):
    _require_c3()
    suffix = uuid4().hex[:8]
    person = f"name:c3-partial-{suffix}"

    with _isolated_conn() as conn:
        if not table_exists(conn, "enrollment_queue"):
            pytest.skip("enrollment_queue missing")
        prior_id, new_id = _setup_snapshot_pair(
            conn,
            user_id=seed["executor_user_id"],
            prior_entries={},
            new_entries={
                person: {
                    "full_name": "Partial",
                    "department": "A",
                    "position_raw": "Doc",
                    "org_unit_id": seed["unit_id"],
                }
            },
        )
        persons_before = _count_table(conn, "persons")
        report = run_monthly_personnel_lifecycle(
            conn=conn,
            previous_snapshot_id=prior_id,
            snapshot_id=new_id,
            dry_run=False,
            refresh_cache=True,
            enqueue=True,
            sync_persons=False,
            actor_user_id=seed["executor_user_id"],
        )
        assert report["enrollment"]["created"] >= 1
        assert report["person_sync"].get("skipped") is True
        assert _count_table(conn, "persons") == persons_before


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_refresh_cache_false_works(seed):
    _require_c3()
    suffix = uuid4().hex[:8]
    person = f"name:c3-nocache-{suffix}"

    with _isolated_conn() as conn:
        prior_id, new_id = _setup_snapshot_pair(
            conn,
            user_id=seed["executor_user_id"],
            prior_entries={},
            new_entries={
                person: {
                    "full_name": "No Cache",
                    "department": "A",
                    "position_raw": "Doc",
                    "org_unit_id": seed["unit_id"],
                }
            },
        )
        report = run_monthly_personnel_lifecycle(
            conn=conn,
            previous_snapshot_id=prior_id,
            snapshot_id=new_id,
            dry_run=True,
            refresh_cache=False,
            enqueue=False,
            sync_persons=False,
            actor_user_id=seed["executor_user_id"],
        )
        assert report["effective_cache"].get("skipped") is True
        assert report["monthly_diff"]["cache_refreshed"] is False


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_sync_persons_false_works(seed):
    _require_c3()
    suffix = uuid4().hex[:8]
    person = f"name:c3-nosync-{suffix}"

    with _isolated_conn() as conn:
        prior_id, new_id = _setup_snapshot_pair(
            conn,
            user_id=seed["executor_user_id"],
            prior_entries={},
            new_entries={
                person: {
                    "full_name": "No Sync",
                    "department": "A",
                    "position_raw": "Doc",
                    "org_unit_id": seed["unit_id"],
                }
            },
        )
        persons_before = _count_table(conn, "persons")
        report = run_monthly_personnel_lifecycle(
            conn=conn,
            previous_snapshot_id=prior_id,
            snapshot_id=new_id,
            dry_run=False,
            refresh_cache=True,
            enqueue=False,
            sync_persons=False,
            actor_user_id=seed["executor_user_id"],
        )
        assert report["person_sync"].get("skipped") is True
        assert _count_table(conn, "persons") == persons_before
        assert report["personnel_events"]["events_created"] > 0


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_validation_summary_generated(seed):
    _require_c3()
    suffix = uuid4().hex[:8]
    person = f"name:c3-validate-{suffix}"

    with _isolated_conn() as conn:
        prior_id, new_id = _setup_snapshot_pair(
            conn,
            user_id=seed["executor_user_id"],
            prior_entries={},
            new_entries={
                person: {
                    "full_name": "Validate",
                    "department": "A",
                    "position_raw": "Doc",
                    "org_unit_id": seed["unit_id"],
                }
            },
        )
        report = run_monthly_personnel_lifecycle(
            conn=conn,
            previous_snapshot_id=prior_id,
            snapshot_id=new_id,
            dry_run=True,
            refresh_cache=True,
            enqueue=False,
            sync_persons=False,
            actor_user_id=seed["executor_user_id"],
        )
        validation = report["validation"]
        assert "checks" in validation
        assert len(validation["checks"]) >= 4
        codes = {c["code"] for c in validation["checks"]}
        assert "duplicate_active_overrides" in codes
        assert "duplicate_active_assignments" in codes
        assert "personnel_events_stuck_detected" in codes
        assert "outdated_effective_cache" in codes
