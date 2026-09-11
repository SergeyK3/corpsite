"""WP-PPR-MIG-005F-A PostgreSQL contracts for immutable event and outbox."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.db.engine import engine
from app.services.ppr_manual_correction_event_service import (
    ManualCorrectionAppend,
    ManualCorrectionIdempotencyConflictError,
    append_correction_event_and_outbox,
)
from app.services.ppr_migration_status_projection_service import ensure_universe
from tests.alembic_test_helpers import alembic_config, assert_revision_on_chain, exclusive_migration_cycle, get_alembic_heads
from tests.test_ppr_migration_status_projection_postgres import _seed

REVISION = "ppr005fevent01"
PARENT = "ppr005cread01"
FP = "a" * 64


def _tx():
    conn = engine.connect()
    tx = conn.begin()
    assert conn.execute(text("select current_database()")).scalar_one() == "corpsite_test"
    return conn, tx


def _request(conn, *, key=None, section="general", reason="CONFLICT_NAME_PARSE") -> ManualCorrectionAppend:
    actor, person, employee, _row, cohort = _seed(conn, suffix=f"wp005fa-{uuid4().hex}")
    universe = ensure_universe(conn, base_cohort_run_id=cohort)
    return ManualCorrectionAppend(
        idempotency_key=key or uuid4(), actor_user_id=actor, person_id=person,
        employee_context_id=employee, universe_id=universe, cohort_run_id=cohort,
        section_code=section, origin_status="REVIEW_REQUIRED", origin_reason_code=reason,
        before_source_fingerprint=FP, before_target_fingerprint=FP, before_binding_fingerprint=FP,
        after_source_fingerprint="b" * 64, after_target_fingerprint="c" * 64,
        after_binding_fingerprint="d" * 64, policy_version="WP005F-A/v1",
        optimistic_version=1, occurred_at=datetime.now(timezone.utc),
    )


def test_valid_event_is_immutable_and_pii_free():
    conn, tx = _tx()
    try:
        result = append_correction_event_and_outbox(conn, request=_request(conn))
        assert conn.execute(text("select event_type,origin_status from ppr_section_manual_correction_events where event_id=:id"), {"id": result["event_id"]}).one() == ("PPR_SECTION_MANUAL_CORRECTED", "REVIEW_REQUIRED")
        with pytest.raises(DBAPIError):
            conn.execute(text("update ppr_section_manual_correction_events set policy_version='x' where event_id=:id"), {"id": result["event_id"]})
        conn.rollback()
        tx = conn.begin()
        result = append_correction_event_and_outbox(conn, request=_request(conn))
        with pytest.raises(DBAPIError):
            conn.execute(text("delete from ppr_section_manual_correction_events where event_id=:id"), {"id": result["event_id"]})
        conn.rollback()
    finally:
        if tx.is_active:
            tx.rollback()
        conn.close()


def test_event_constraints_and_no_pii_or_raw_payload_columns():
    conn, tx = _tx()
    try:
        request = _request(conn)
        with pytest.raises(IntegrityError):
            append_correction_event_and_outbox(conn, request=ManualCorrectionAppend(**{**request.__dict__, "section_code": "family"}))
        conn.rollback(); tx = conn.begin()
        request = _request(conn)
        with pytest.raises(IntegrityError):
            append_correction_event_and_outbox(conn, request=ManualCorrectionAppend(**{**request.__dict__, "origin_reason_code": "UNSAFE"}))
        conn.rollback(); tx = conn.begin()
        request = _request(conn)
        with pytest.raises(IntegrityError):
            append_correction_event_and_outbox(conn, request=ManualCorrectionAppend(**{**request.__dict__, "after_target_fingerprint": "bad"}))
        conn.rollback(); tx = conn.begin()
        columns = set(conn.execute(text("select column_name from information_schema.columns where table_name='ppr_section_manual_correction_events'")).scalars())
        assert not columns & {"full_name", "iin", "raw_payload", "payload", "document", "comment", "stack_trace"}
    finally:
        if tx.is_active:
            tx.rollback()
        conn.close()


def test_idempotency_conflict_and_atomic_rollback():
    conn, tx = _tx()
    try:
        request = _request(conn)
        one = append_correction_event_and_outbox(conn, request=request)
        assert append_correction_event_and_outbox(conn, request=request) == one
        assert conn.execute(text("select count(*) from ppr_section_manual_correction_events where idempotency_key=:key"), {"key": request.idempotency_key}).scalar_one() == 1
        assert conn.execute(text("select count(*) from ppr_migration_projection_outbox where event_id=:event_id"), {"event_id": one["event_id"]}).scalar_one() == 1
        with pytest.raises(ManualCorrectionIdempotencyConflictError):
            append_correction_event_and_outbox(conn, request=ManualCorrectionAppend(**{**request.__dict__, "policy_version": "other"}))
        with pytest.raises(ManualCorrectionIdempotencyConflictError):
            append_correction_event_and_outbox(conn, request=ManualCorrectionAppend(**{**request.__dict__, "job_kind": "TARGETED_INVALIDATE"}))
        nested = conn.begin_nested()
        append_correction_event_and_outbox(conn, request=_request(conn))
        nested.rollback()
        assert conn.execute(text("select count(*) from ppr_section_manual_correction_events where idempotency_key=:key"), {"key": request.idempotency_key}).scalar_one() == 1
        assert conn.execute(text("select count(*) from ppr_migration_projection_outbox where event_id=:event_id"), {"event_id": one["event_id"]}).scalar_one() == 1
    finally:
        tx.rollback(); conn.close()


def test_outbox_lifecycle_constraints_and_ready_claim_index():
    conn, tx = _tx()
    try:
        result = append_correction_event_and_outbox(conn, request=_request(conn))
        outbox_id = result["outbox_id"]
        with pytest.raises(IntegrityError):
            conn.execute(text("update ppr_migration_projection_outbox set state_code='PROCESSING' where outbox_id=:id"), {"id": outbox_id})
        conn.rollback(); tx = conn.begin()
        # The previous row rolled back with the failed statement's transaction; create a fresh valid job.
        result = append_correction_event_and_outbox(conn, request=_request(conn))
        outbox_id = result["outbox_id"]
        conn.execute(text("update ppr_migration_projection_outbox set state_code='PROCESSING',claimed_at=now(),claimed_by='worker-1',attempts=attempts+1 where outbox_id=:id"), {"id": outbox_id})
        conn.execute(text("update ppr_migration_projection_outbox set state_code='COMPLETED',processed_at=now() where outbox_id=:id"), {"id": outbox_id})
        with pytest.raises(DBAPIError):
            conn.execute(text("update ppr_migration_projection_outbox set person_id=person_id+1 where outbox_id=:id"), {"id": outbox_id})
        conn.rollback(); tx = conn.begin()
        indexes = conn.execute(text("select indexdef from pg_indexes where tablename='ppr_migration_projection_outbox'")).scalars().all()
        assert any("PENDING" in index and "RETRY" in index and "next_attempt_at" in index for index in indexes)
    finally:
        if tx.is_active:
            tx.rollback()
        conn.close()


def test_upgrade_downgrade_upgrade_and_guarded_downgrade():
    cfg = alembic_config()
    assert get_alembic_heads(cfg) == {REVISION}
    with exclusive_migration_cycle() as conn:
        conn.commit()
        command.upgrade(cfg, REVISION)
        command.downgrade(cfg, PARENT)
        command.upgrade(cfg, REVISION)
        # Seed a minimal durable row directly so downgrade must refuse before DROP.
        token = uuid4().hex
        actor = int(conn.execute(text("select min(user_id) from users where is_active")).scalar_one())
        person = int(conn.execute(text("insert into persons(full_name,match_key,person_status,source) values(:label,:label,'active','migration') returning person_id"), {"label": f"wp005fa-guard-{token}"}).scalar_one())
        employee = int(conn.execute(text("insert into employees(full_name,person_id,is_active,operational_status) values(:label,:p,true,'active') returning employee_id"), {"label": f"wp005fa-guard-{token}", "p": person}).scalar_one())
        batch = int(conn.execute(text("insert into hr_import_batches(source_type,file_name,import_code,imported_by,status) values('HR_CONTROL_LIST',:file_name,:import_code,:a,'APPLY_PENDING') returning batch_id"), {"file_name": f"wp005fa-{token}", "import_code": f"wp005fa-{token}", "a": actor}).scalar_one())
        row = int(conn.execute(text("insert into hr_import_rows(batch_id,source_sheet,source_row_number,raw_payload,normalized_payload,employee_id) values(:b,'T',1,'{}','{}',:e) returning row_id"), {"b":batch,"e":employee}).scalar_one())
        from app.services.ppr_stage0_cohort_service import preview_stage0_cohort, freeze_stage0_cohort
        preview = preview_stage0_cohort(conn, source_batch_id=batch)
        cohort = int(freeze_stage0_cohort(conn, source_batch_id=batch, preview_fingerprint=preview["preview_fingerprint"], actor_user_id=actor)["stage0_cohort_run_id"])
        universe = ensure_universe(conn, base_cohort_run_id=cohort)
        request = ManualCorrectionAppend(idempotency_key=uuid4(),actor_user_id=actor,person_id=person,employee_context_id=employee,universe_id=universe,cohort_run_id=cohort,section_code='general',origin_status='REVIEW_REQUIRED',origin_reason_code='CONFLICT_NAME_PARSE',before_source_fingerprint=FP,before_target_fingerprint=FP,before_binding_fingerprint=FP,after_source_fingerprint='b'*64,after_target_fingerprint='c'*64,after_binding_fingerprint='d'*64,policy_version='WP005F-A/guard',optimistic_version=1,occurred_at=datetime.now(timezone.utc))
        result = append_correction_event_and_outbox(conn, request=request)
        conn.commit()
        with pytest.raises(Exception, match="Cannot downgrade ppr005fevent01"):
            command.downgrade(cfg, PARENT)
        # Test-only administrative cleanup is required because the production
        # contract correctly prohibits ordinary DELETE from the immutable log.
        conn.execute(text("alter table ppr_section_manual_correction_events disable trigger trg_ppr_section_manual_correction_events_immutable"))
        conn.execute(text("delete from ppr_migration_projection_outbox where outbox_id=:id"), {"id": result["outbox_id"]})
        conn.execute(text("delete from ppr_section_manual_correction_events where event_id=:id"), {"id": result["event_id"]})
        conn.execute(text("alter table ppr_section_manual_correction_events enable trigger trg_ppr_section_manual_correction_events_immutable"))
        conn.commit()
        command.downgrade(cfg, PARENT)
        command.upgrade(cfg, REVISION)
        # The durable row is needed only to prove guarded downgrade. Remove the
        # minimal Stage-0 fixture graph after the successful cycle.
        conn.execute(text("delete from ppr_migration_status_universe_cohorts where universe_id=:u"), {"u": universe})
        conn.execute(text("delete from ppr_migration_status_universes where universe_id=:u"), {"u": universe})
        conn.execute(text("delete from ppr_stage0_cohort_participants where stage0_cohort_run_id=:c"), {"c": cohort})
        conn.execute(text("delete from ppr_stage0_cohort_runs where stage0_cohort_run_id=:c"), {"c": cohort})
        conn.execute(text("delete from hr_import_rows where batch_id=:b"), {"b": batch})
        conn.execute(text("delete from hr_import_batches where batch_id=:b"), {"b": batch})
        conn.execute(text("delete from employees where employee_id=:e"), {"e": employee})
        conn.execute(text("delete from persons where person_id=:p"), {"p": person})
        conn.commit()
    assert assert_revision_on_chain(REVISION) == REVISION
