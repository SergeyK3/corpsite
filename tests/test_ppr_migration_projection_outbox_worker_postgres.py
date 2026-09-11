"""WP-PPR-MIG-005F-B PostgreSQL contracts for targeted outbox processing."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import text

from app.db.engine import engine
from app.services import ppr_migration_projection_outbox_worker as worker
from app.services import ppr_migration_status_projection_service as projection
from app.services.ppr_manual_correction_event_service import (
    ManualCorrectionAppend,
    append_correction_event_and_outbox,
)
from tests.test_ppr_migration_status_projection_postgres import _seed


def _create_job() -> dict[str, int]:
    """Commit a unique fixture because the worker intentionally uses new UoWs."""
    with engine.begin() as conn:
        assert conn.execute(text("select current_database()")).scalar_one() == "corpsite_test"
        actor, person, employee, _row, cohort = _seed(conn, suffix=f"wp005fb-{uuid4().hex}")
        universe = projection.ensure_universe(conn, base_cohort_run_id=cohort)
        fact = worker._fact_for_target(conn, universe_id=universe, person_id=person, cohort_run_id=cohort)
        assert fact is not None
        result = projection._status(conn, fact, "general")
        event = append_correction_event_and_outbox(conn, request=ManualCorrectionAppend(
            idempotency_key=uuid4(), actor_user_id=actor, person_id=person,
            employee_context_id=employee, universe_id=universe, cohort_run_id=cohort,
            section_code="general", origin_status="REVIEW_REQUIRED",
            origin_reason_code="CONFLICT_NAME_PARSE",
            before_source_fingerprint=result["source_fingerprint"],
            before_target_fingerprint=result["target_fingerprint"],
            before_binding_fingerprint=result["binding_fingerprint"],
            after_source_fingerprint=result["source_fingerprint"],
            after_target_fingerprint=result["target_fingerprint"],
            after_binding_fingerprint=result["binding_fingerprint"],
            policy_version="WP005F-B/v1", optimistic_version=1,
            occurred_at=datetime.now(timezone.utc),
        ))
        return {**event, "universe_id": universe, "person_id": person, "employee_id": employee,
                "cohort_run_id": cohort}


def _cleanup(seed: dict[str, int]) -> None:
    """Test-only removal of committed fixture graph, including immutable log rows."""
    with engine.begin() as conn:
        conn.execute(text("delete from ppr_migration_projection_outbox where outbox_id=:id"), {"id": seed["outbox_id"]})
        conn.execute(text("alter table ppr_section_manual_correction_events disable trigger trg_ppr_section_manual_correction_events_immutable"))
        try:
            conn.execute(text("delete from ppr_section_manual_correction_events where event_id=:id"), {"id": seed["event_id"]})
        finally:
            conn.execute(text("alter table ppr_section_manual_correction_events enable trigger trg_ppr_section_manual_correction_events_immutable"))
        conn.execute(text("delete from ppr_migration_section_status_projection where universe_id=:u and person_id=:p"), {"u": seed["universe_id"], "p": seed["person_id"]})
        conn.execute(text("delete from ppr_migration_status_universe_cohorts where universe_id=:u"), {"u": seed["universe_id"]})
        conn.execute(text("delete from ppr_migration_status_universes where universe_id=:u"), {"u": seed["universe_id"]})
        conn.execute(text("delete from ppr_stage0_cohort_participants where stage0_cohort_run_id=:c"), {"c": seed["cohort_run_id"]})
        conn.execute(text("delete from ppr_stage0_cohort_runs where stage0_cohort_run_id=:c"), {"c": seed["cohort_run_id"]})
        batch_id = conn.execute(text("select batch_id from hr_import_rows where employee_id=:e"), {"e": seed["employee_id"]}).scalar_one()
        conn.execute(text("delete from hr_import_rows where batch_id=:b"), {"b": batch_id})
        conn.execute(text("delete from hr_import_batches where batch_id=:b"), {"b": batch_id})
        conn.execute(text("delete from employees where employee_id=:e"), {"e": seed["employee_id"]})
        conn.execute(text("delete from persons where person_id=:p"), {"p": seed["person_id"]})


def test_targeted_success_and_repeat_are_idempotent():
    seed = _create_job()
    try:
        result = worker.run_outbox_batch(engine, worker_id="wp005fb-success", retry_delay_seconds=0)
        assert result == {"claimed": 1, "completed": 1, "retry": 0, "dead": 0, "recovered": 0}
        with engine.connect() as conn:
            cell = conn.execute(text("""select status_code,reason_code,row_version from ppr_migration_section_status_projection
              where universe_id=:u and person_id=:p and section_code='general'"""), {"u": seed["universe_id"], "p": seed["person_id"]}).one()
            assert cell == ("CORRECTED_BY_HR", "MANUAL_CORRECTION_PENDING_RECHECK", 1)
        assert worker.run_outbox_batch(engine, worker_id="wp005fb-repeat", retry_delay_seconds=0)["claimed"] == 0
        with engine.connect() as conn:
            assert conn.execute(text("select count(*) from ppr_migration_section_status_projection where universe_id=:u and person_id=:p and section_code='general'"), {"u": seed["universe_id"], "p": seed["person_id"]}).scalar_one() == 1
    finally:
        _cleanup(seed)


def test_retry_then_completion():
    seed = _create_job()
    try:
        failed = worker.run_outbox_batch(engine, worker_id="wp005fb-retry", retry_delay_seconds=0, projector=lambda _conn: (_ for _ in ()).throw(RuntimeError("test")))
        assert failed["retry"] == 1
        assert worker.run_outbox_batch(engine, worker_id="wp005fb-retry", retry_delay_seconds=0)["completed"] == 1
    finally:
        _cleanup(seed)


def test_exhausted_attempts_become_dead():
    seed = _create_job()
    try:
        fail = lambda _conn: (_ for _ in ()).throw(RuntimeError("test"))
        assert worker.run_outbox_batch(engine, worker_id="wp005fb-dead", max_attempts=2, retry_delay_seconds=0, projector=fail)["retry"] == 1
        assert worker.run_outbox_batch(engine, worker_id="wp005fb-dead", max_attempts=2, retry_delay_seconds=0, projector=fail)["dead"] == 1
        with engine.connect() as conn:
            assert conn.execute(text("select state_code,last_error_code from ppr_migration_projection_outbox where outbox_id=:id"), {"id": seed["outbox_id"]}).one() == ("DEAD", "PROJECTOR_INTERNAL")
    finally:
        _cleanup(seed)


def test_competing_workers_skip_locked_job():
    seed = _create_job()
    first = engine.connect()
    second = engine.connect()
    first_tx = first.begin()
    second_tx = second.begin()
    try:
        assert len(worker.claim_ready_jobs(first, worker_id="wp005fb-one", limit=1)) == 1
        assert worker.claim_ready_jobs(second, worker_id="wp005fb-two", limit=1) == []
    finally:
        first_tx.rollback(); second_tx.rollback(); first.close(); second.close()
        _cleanup(seed)


def test_expired_processing_lease_is_recovered_and_completed():
    seed = _create_job()
    try:
        with engine.begin() as conn:
            conn.execute(text("""update ppr_migration_projection_outbox
              set state_code='PROCESSING',attempts=1,claimed_at=now() - interval '10 minutes',claimed_by='lost-worker'
              where outbox_id=:id"""), {"id": seed["outbox_id"]})
        result = worker.run_outbox_batch(engine, worker_id="wp005fb-recover", lease_seconds=60, retry_delay_seconds=0)
        assert result["recovered"] == 1
        assert result["completed"] == 1
    finally:
        _cleanup(seed)
