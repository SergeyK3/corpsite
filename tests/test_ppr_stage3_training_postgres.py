"""PostgreSQL contracts for immutable Stage-3 TrainingCandidate snapshots."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import HTTPException
from sqlalchemy import text

from app.api import ppr_stage3_training_router as router
from app.db.engine import engine
from app.services import ppr_stage3_training_service as service
from app.services.ppr_stage0_cohort_service import freeze_stage0_cohort, preview_stage0_cohort


def _seed(conn, marker: str, *, duplicate_fragment: bool = False, second_employee_same_training: bool = False):
    actor = int(conn.execute(text("SELECT min(user_id) FROM public.users WHERE is_active")).scalar_one())
    person = int(conn.execute(text("INSERT INTO public.persons(full_name,match_key,person_status,source) VALUES(:v,:v,'active','migration') RETURNING person_id"), {"v": marker}).scalar_one())
    employee = int(conn.execute(text("INSERT INTO public.employees(full_name,person_id,is_active,operational_status) VALUES(:v,:p,true,'active') RETURNING employee_id"), {"v": marker, "p": person}).scalar_one())
    batch = int(conn.execute(text("INSERT INTO public.hr_import_batches(source_type,file_name,import_code,imported_by,status) VALUES('HR_CONTROL_LIST',:v,:v,:a,'APPLY_PENDING') RETURNING batch_id"), {"v": marker, "a": actor}).scalar_one())
    row = int(conn.execute(text("INSERT INTO public.hr_import_rows(batch_id,source_sheet,source_row_number,raw_payload,normalized_payload,employee_id) VALUES(:b,'Training',1,'{}'::jsonb,'{}'::jsonb,:e) RETURNING row_id"), {"b": batch, "e": employee}).scalar_one())
    source = "Курс: ACLS; Организатор: Provider; 36 часов; 01.03.2024; № AB-1"
    conn.execute(text("""INSERT INTO public.hr_import_normalized_records
        (batch_id,row_id,employee_id,fragment_index,source_field,source_text,source_record_key,record_kind,title,provider,hours,end_date,document_number,parse_method,review_status)
        VALUES(:b,:r,:e,0,'training',:source,'training-0','training','ACLS','Provider',36,'2024-03-01','AB-1','regex_v1','approved')"""), {"b": batch, "r": row, "e": employee, "source": source})
    if duplicate_fragment:
        conn.execute(text("""INSERT INTO public.hr_import_normalized_records
            (batch_id,row_id,employee_id,fragment_index,source_field,source_text,source_record_key,record_kind,title,provider,hours,end_date,document_number,parse_method,review_status)
            VALUES(:b,:r,:e,1,'training',:source,'training-1','training','ACLS','Provider',36,'2024-03-01','AB-1','regex_v1','approved')"""), {"b": batch, "r": row, "e": employee, "source": source})
    if second_employee_same_training:
        second_person = int(conn.execute(text("INSERT INTO public.persons(full_name,match_key,person_status,source) VALUES(:v,:v,'active','migration') RETURNING person_id"), {"v": marker + "-second"}).scalar_one())
        second_employee = int(conn.execute(text("INSERT INTO public.employees(full_name,person_id,is_active,operational_status) VALUES(:v,:p,true,'active') RETURNING employee_id"), {"v": marker + "-second", "p": second_person}).scalar_one())
        second_row = int(conn.execute(text("INSERT INTO public.hr_import_rows(batch_id,source_sheet,source_row_number,raw_payload,normalized_payload,employee_id) VALUES(:b,'Training',2,'{}'::jsonb,'{}'::jsonb,:e) RETURNING row_id"), {"b": batch, "e": second_employee}).scalar_one())
        conn.execute(text("""INSERT INTO public.hr_import_normalized_records
            (batch_id,row_id,employee_id,fragment_index,source_field,source_text,source_record_key,record_kind,title,provider,hours,end_date,document_number,parse_method,review_status)
            VALUES(:b,:r,:e,0,'training',:source,'training-second-0','training','ACLS','Provider',36,'2024-03-01','AB-1','regex_v1','approved')"""), {"b": batch, "r": second_row, "e": second_employee, "source": source})
    preview = preview_stage0_cohort(conn, source_batch_id=batch)
    cohort = freeze_stage0_cohort(conn, source_batch_id=batch, preview_fingerprint=preview["preview_fingerprint"], actor_user_id=actor)
    return actor, int(cohort["stage0_cohort_run_id"]), person, row, source


@pytest.fixture(autouse=True)
def _stage3_flags(monkeypatch):
    monkeypatch.setenv("PPR_STAGE3_TRAINING_PREVIEW_ENABLED", "true")
    monkeypatch.setenv("PPR_STAGE3_TRAINING_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("PPR_STAGE3_TRAINING_ACCEPT_ENABLED", "true")
    monkeypatch.setenv("PPR_PMF_BRIDGE_ENABLED", "true")
    monkeypatch.setenv("PPR_STAGE3_CERTIFICATE_HMAC_SECRET", "stage3-postgres-test-secret")


def _create(conn, actor, cohort):
    preview = service.compute_preview_stage3(conn, stage0_cohort_run_id=cohort)
    return service.persist_preview_stage3(conn, stage0_cohort_run_id=cohort, actor_user_id=actor, expected_preview_fingerprint=preview["preview_fingerprint"])


def test_training_snapshot_is_immutable_and_full_flow_uses_it(monkeypatch):
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            assert conn.execute(text("SELECT current_database()")).scalar_one() == "corpsite_test"
            actor, cohort, person, _row, source = _seed(conn, "stage3-snapshot-flow")
            actor, cohort, person, _row, _source = _seed(conn, "stage3-canonical-before-accept")
            run = _create(conn, actor, cohort)
            run_id = int(run["run"]["stage_run_id"])
            snapshot = conn.execute(text("SELECT safe_snapshot FROM public.ppr_stage_runs WHERE stage_run_id=:id"), {"id": run_id}).scalar_one()
            fragment = snapshot["training_candidates"][str(run["participants"][0]["stage0_participant_id"])]["fragments"][0]
            assert fragment["training_candidate"]["provider_name"] == "Provider"
            assert fragment["training_candidate"]["training_type"] == "COURSE"
            assert fragment["training_candidate"]["duration_hours"] == "36"
            assert source not in str(snapshot) and "raw_fragment" not in str(snapshot)
            # A later parser implementation must not affect a frozen run.
            monkeypatch.setattr(service, "parse_training_fragment", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("must not parse frozen source")))
            service.approve_stage3(conn, run_id=run_id, actor_user_id=actor)
            executed = service.execute_next_stage3(conn, run_id=run_id, actor_user_id=actor)
            participant = executed["participants"][0]
            assert participant["pmf_run_id"] is not None
            assert conn.execute(text("SELECT count(*) FROM public.person_training WHERE person_id=:p"), {"p": person}).scalar_one() == 0
            service.execute_next_stage3(conn, run_id=run_id, actor_user_id=actor)
            summary = service.acceptance_summary(conn, run_id=run_id)
            accepted = service.accept_stage3(conn, run_id=run_id, actor_user_id=actor, acceptance_fingerprint=summary["acceptance_fingerprint"])
            assert accepted["run"]["status"] == "ACCEPTED"
            assert conn.execute(text("SELECT count(*) FROM public.person_training WHERE person_id=:p"), {"p": person}).scalar_one() == 1
            events = conn.execute(text("SELECT count(*) FROM public.personnel_record_events WHERE person_id=:p AND event_payload->>'section_code'='PPR-TRAINING'"), {"p": person}).scalar_one()
            assert events == 1
            service.accept_stage3(conn, run_id=run_id, actor_user_id=actor, acceptance_fingerprint="0" * 64)
            assert conn.execute(text("SELECT count(*) FROM public.personnel_record_events WHERE person_id=:p AND event_payload->>'section_code'='PPR-TRAINING'"), {"p": person}).scalar_one() == events
        finally:
            tx.rollback()


def test_training_source_change_is_stale_and_exact_dedup_is_not_reapplied():
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            actor, cohort, person, row, _source = _seed(conn, "stage3-stale-dedup")
            run = _create(conn, actor, cohort)
            run_id = int(run["run"]["stage_run_id"])
            service.approve_stage3(conn, run_id=run_id, actor_user_id=actor)
            conn.execute(text("UPDATE public.hr_import_normalized_records SET source_text=source_text || ' changed',updated_at=clock_timestamp() WHERE row_id=:row"), {"row": row})
            paused = service.execute_next_stage3(conn, run_id=run_id, actor_user_id=actor)
            assert paused["run"]["status"] == "PAUSED_ON_ERROR"
            assert paused["run"]["last_error_code"] == "STAGE3_RESUME_STALE"
            # Canonical exact duplicate remains a no-write outcome on a new source row.
            conn.execute(text("UPDATE public.hr_import_normalized_records SET source_text='Курс: ACLS; Организатор: Provider; 36 часов; 01.03.2024; № AB-1',updated_at=clock_timestamp() WHERE row_id=:row"), {"row": row})
            # Isolated-fixture exception: this test needs a pre-existing
            # canonical row to exercise exact dedup before Stage 3 creates a
            # PMF item.  It runs inside a rolled-back corpsite_test transaction
            # and never exercises or changes the production Stage-3 write path.
            conn.execute(text("""INSERT INTO public.person_training(person_id,employee_context_id,training_kind,title,organization_name,hours,completed_at,certificate_number,lifecycle_status,metadata)
                VALUES(:p,(SELECT employee_id FROM employees WHERE person_id=:p),'course','ACLS','Provider',36,'2024-03-01','AB-1','active','{}'::jsonb)"""), {"p": person})
            # A fresh preview sees exact canonical identity and has no READY proposal.
            preview = service.compute_preview_stage3(conn, stage0_cohort_run_id=cohort)
            assert preview["participant_count"] == 1
            fresh = _create(conn, actor, cohort)
            assert fresh["participants"][0]["fragments"][0]["outcome"] == "ALREADY_APPLIED"
        finally:
            tx.rollback()


def test_training_in_run_exact_duplicate_creates_one_pmf_item_and_one_record():
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            actor, cohort, person, _row, _source = _seed(conn, "stage3-in-run-dedup", duplicate_fragment=True)
            run = _create(conn, actor, cohort)
            run_id = int(run["run"]["stage_run_id"])
            views = run["participants"][0]["fragments"]
            assert [view["outcome"] for view in views] == ["READY_TO_ADD", "DUPLICATE_IN_RUN"]
            service.approve_stage3(conn, run_id=run_id, actor_user_id=actor)
            executed = service.execute_next_stage3(conn, run_id=run_id, actor_user_id=actor)
            pmf_run_id = executed["participants"][0]["pmf_run_id"]
            assert conn.execute(text("SELECT count(*) FROM public.personnel_migration_items WHERE run_id=:id"), {"id": pmf_run_id}).scalar_one() == 1
            service.execute_next_stage3(conn, run_id=run_id, actor_user_id=actor)
            summary = service.acceptance_summary(conn, run_id=run_id)
            service.accept_stage3(conn, run_id=run_id, actor_user_id=actor, acceptance_fingerprint=summary["acceptance_fingerprint"])
            assert conn.execute(text("SELECT count(*) FROM public.person_training WHERE person_id=:p"), {"p": person}).scalar_one() == 1
        finally:
            tx.rollback()


def test_training_in_run_dedup_is_scoped_to_matched_person():
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            actor, cohort, person, _row, _source = _seed(
                conn, "stage3-in-run-per-person", second_employee_same_training=True,
            )
            run = _create(conn, actor, cohort)
            run_id = int(run["run"]["stage_run_id"])
            assert len(run["participants"]) == 2
            assert all(
                [fragment["outcome"] for fragment in participant["fragments"]] == ["READY_TO_ADD"]
                for participant in run["participants"]
            )
            person_ids = [int(participant["person_id"]) for participant in run["participants"]]
            service.approve_stage3(conn, run_id=run_id, actor_user_id=actor)
            service.execute_next_stage3(conn, run_id=run_id, actor_user_id=actor)
            service.execute_next_stage3(conn, run_id=run_id, actor_user_id=actor)
            service.execute_next_stage3(conn, run_id=run_id, actor_user_id=actor)
            assert conn.execute(text("""SELECT count(*) FROM public.personnel_migration_items i
                JOIN public.ppr_stage_run_participants p ON p.pmf_run_id=i.run_id
                WHERE p.stage_run_id=:run"""), {"run": run_id}).scalar_one() == 2
            summary = service.acceptance_summary(conn, run_id=run_id)
            service.accept_stage3(conn, run_id=run_id, actor_user_id=actor, acceptance_fingerprint=summary["acceptance_fingerprint"])
            assert conn.execute(text("SELECT count(*) FROM public.person_training WHERE person_id = ANY(:people)"), {"people": person_ids}).scalar_one() == 2
            assert person in person_ids
        finally:
            tx.rollback()


def test_skip_is_an_approval_decision_and_reapproval_allows_accepting_other_people():
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            actor, cohort, _person, _row, _source = _seed(
                conn, "stage3-skip-reapproval", second_employee_same_training=True,
            )
            run = _create(conn, actor, cohort)
            run_id = int(run["run"]["stage_run_id"])
            first, second = run["participants"]
            # Skip before approval is part of the first approved decision set.
            service.skip_stage3_participant(conn, run_id=run_id, participant_id=first["stage_run_participant_id"], actor_user_id=actor, reason="manual skip")
            service.approve_stage3(conn, run_id=run_id, actor_user_id=actor)
            service.execute_next_stage3(conn, run_id=run_id, actor_user_id=actor)
            service.execute_next_stage3(conn, run_id=run_id, actor_user_id=actor)
            summary = service.acceptance_summary(conn, run_id=run_id)
            service.accept_stage3(conn, run_id=run_id, actor_user_id=actor, acceptance_fingerprint=summary["acceptance_fingerprint"])
            states = conn.execute(text("SELECT status FROM public.ppr_stage_run_participants WHERE stage_run_id=:run ORDER BY position"), {"run": run_id}).scalars().all()
            assert states == ["SKIPPED_BY_DECISION", "COMPLETED"]

            # A decision after approval invalidates it and execution is blocked
            # until HR explicitly approves the new decision set.
            actor, cohort, _person, _row, _source = _seed(
                conn, "stage3-skip-after-approve", second_employee_same_training=True,
            )
            run = _create(conn, actor, cohort)
            run_id = int(run["run"]["stage_run_id"])
            first, second = run["participants"]
            service.approve_stage3(conn, run_id=run_id, actor_user_id=actor)
            service.skip_stage3_participant(conn, run_id=run_id, participant_id=first["stage_run_participant_id"], actor_user_id=actor, reason="changed decision")
            invalidated = service._run(conn, run_id)
            assert invalidated["status"] == "DRY_RUN_COMPLETED"
            assert service._approved_decision_fingerprint(invalidated) is None
            with pytest.raises(service.Stage3ConflictError, match="STAGE3_INVALID_STATE"):
                service.execute_next_stage3(conn, run_id=run_id, actor_user_id=actor)
            with pytest.raises(service.Stage3ConflictError, match="STAGE3_ACCEPTANCE_NOT_READY"):
                service.accept_stage3(conn, run_id=run_id, actor_user_id=actor)
            service.approve_stage3(conn, run_id=run_id, actor_user_id=actor)
            service.execute_next_stage3(conn, run_id=run_id, actor_user_id=actor)
            service.execute_next_stage3(conn, run_id=run_id, actor_user_id=actor)
            summary = service.acceptance_summary(conn, run_id=run_id)
            service.accept_stage3(conn, run_id=run_id, actor_user_id=actor, acceptance_fingerprint=summary["acceptance_fingerprint"])
        finally:
            tx.rollback()


def test_accept_revalidates_snapshot_match_source_and_canonical_after_execute():
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            actor, cohort, person, row, _source = _seed(conn, "stage3-accept-stale")
            run = _create(conn, actor, cohort)
            run_id = int(run["run"]["stage_run_id"])
            snapshot = conn.execute(text("SELECT safe_snapshot FROM public.ppr_stage_runs WHERE stage_run_id=:id"), {"id": run_id}).scalar_one()
            fragment = snapshot["training_candidates"][str(run["participants"][0]["stage0_participant_id"])]["fragments"][0]
            assert fragment["training_candidate"]["matched_person_id"] == person
            service.approve_stage3(conn, run_id=run_id, actor_user_id=actor)
            service.execute_next_stage3(conn, run_id=run_id, actor_user_id=actor)
            service.execute_next_stage3(conn, run_id=run_id, actor_user_id=actor)
            summary = service.acceptance_summary(conn, run_id=run_id)
            conn.execute(text("UPDATE public.hr_import_normalized_records SET title='changed',updated_at=clock_timestamp() WHERE row_id=:row"), {"row": row})
            with pytest.raises(service.Stage3ConflictError, match="STAGE3_ACCEPTANCE_STALE"):
                service.accept_stage3(conn, run_id=run_id, actor_user_id=actor, acceptance_fingerprint=summary["acceptance_fingerprint"])
            assert conn.execute(text("SELECT count(*) FROM public.person_training WHERE person_id=:p"), {"p": person}).scalar_one() == 0
            # A frozen candidate/person mismatch is independently fail-closed.
            conn.execute(text("""UPDATE public.ppr_stage_runs
                SET safe_snapshot=jsonb_set(safe_snapshot, '{training_candidates,""" + str(run["participants"][0]["stage0_participant_id"]) + """,fragments,0,training_candidate,matched_person_id}', '0'::jsonb)
                WHERE stage_run_id=:id"""), {"id": run_id})
            with pytest.raises(service.Stage3ConflictError, match="STAGE3_ACCEPTANCE_STALE"):
                service.accept_stage3(conn, run_id=run_id, actor_user_id=actor, acceptance_fingerprint=summary["acceptance_fingerprint"])
        finally:
            tx.rollback()


def test_snapshot_person_mismatch_blocks_approve_and_canonical_change_blocks_accept():
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            actor, cohort, person, _row, _source = _seed(conn, "stage3-match-canonical")
            run = _create(conn, actor, cohort)
            run_id = int(run["run"]["stage_run_id"])
            stage0_id = int(run["participants"][0]["stage0_participant_id"])
            conn.execute(text("""UPDATE public.ppr_stage_runs
                SET safe_snapshot=jsonb_set(safe_snapshot, CAST(:path AS text[]), '0'::jsonb)
                WHERE stage_run_id=:id"""), {"id": run_id, "path": ["training_candidates", str(stage0_id), "fragments", "0", "training_candidate", "matched_person_id"]})
            with pytest.raises(service.Stage3ConflictError, match="STAGE3_APPROVAL_BLOCKED"):
                service.approve_stage3(conn, run_id=run_id, actor_user_id=actor)

            # Fresh run: an unrelated canonical projection change immediately
            # before accept must prevent PMF draft commit.  This isolated test
            # fixture is rolled back and does not use the Stage-3 write path.
            actor, cohort, person, _row, _source = _seed(conn, "stage3-canonical-before-accept")
            run = _create(conn, actor, cohort)
            run_id = int(run["run"]["stage_run_id"])
            service.approve_stage3(conn, run_id=run_id, actor_user_id=actor)
            service.execute_next_stage3(conn, run_id=run_id, actor_user_id=actor)
            service.execute_next_stage3(conn, run_id=run_id, actor_user_id=actor)
            summary = service.acceptance_summary(conn, run_id=run_id)
            conn.execute(text("""INSERT INTO public.person_training(person_id,employee_context_id,training_kind,title,organization_name,hours,completed_at,lifecycle_status,metadata)
                VALUES(:p,(SELECT employee_id FROM employees WHERE person_id=:p),'course','external change','Provider',1,'2024-01-01','active','{}'::jsonb)"""), {"p": person})
            with pytest.raises(service.Stage3ConflictError, match="STAGE3_ACCEPTANCE_STALE"):
                service.accept_stage3(conn, run_id=run_id, actor_user_id=actor, acceptance_fingerprint=summary["acceptance_fingerprint"])
            assert conn.execute(text("SELECT count(*) FROM public.person_training WHERE person_id=:p AND title='ACLS'"), {"p": person}).scalar_one() == 0
        finally:
            tx.rollback()


def test_training_snapshot_migration_upgrade_downgrade_upgrade():
    """Run only on the dedicated test database; no application data is created."""
    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", os.environ["TEST_DATABASE_URL"])
    try:
        command.upgrade(cfg, "head")
        command.downgrade(cfg, "ppr3training001")
        command.upgrade(cfg, "ppr3trainingsnap01")
        with engine.connect() as conn:
            assert conn.execute(text("SELECT current_database()")).scalar_one() == "corpsite_test"
            assert conn.execute(text("SELECT 1 FROM pg_constraint WHERE conname='chk_ppr_stage3_training_candidate_snapshot'")).scalar_one() == 1
    finally:
        command.upgrade(cfg, "head")


def test_training_flags_scope_and_certificate_redaction_fail_closed(monkeypatch):
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            actor, cohort, _person, _row, _source = _seed(conn, "stage3-access-contract")
            monkeypatch.delenv("PPR_STAGE3_TRAINING_PREVIEW_ENABLED")
            with pytest.raises(service.Stage3ValidationError, match="STAGE3_PREVIEW_DISABLED"):
                service.compute_preview_stage3(conn, stage0_cohort_run_id=cohort)
            monkeypatch.setenv("PPR_STAGE3_TRAINING_PREVIEW_ENABLED", "true")
            run = _create(conn, actor, cohort)
            with pytest.raises(HTTPException) as scope_error:
                router._scope_cohort(conn, cohort, {"privileged": False, "scope_unit_ids": []})
            assert scope_error.value.status_code == 403
            monkeypatch.setattr(service, "can_view_training_certificate_details", lambda _: False)
            redacted = service.redacted_view_run_stage3(conn, run_id=int(run["run"]["stage_run_id"]), user={})
            assert "certificate_number" not in str(redacted)
        finally:
            tx.rollback()
