"""PostgreSQL contracts for the Stage 2 thin envelope (corpsite_test only)."""
from __future__ import annotations

from uuid import uuid4

from sqlalchemy import text

from app.db.engine import engine
from app.services.ppr_stage0_cohort_service import freeze_stage0_cohort, preview_stage0_cohort
from app.services.ppr_stage2_education_service import (
    Stage2ConflictError,
    approve_stage2,
    compute_preview_stage2,
    execute_next_stage2,
    acceptance_summary,
    accept_stage2,
    persist_preview_stage2,
    pause_acceptance_after_rollback,
)


def _seed(conn):
    actor = int(conn.execute(text("SELECT min(user_id) FROM public.users WHERE is_active")).scalar_one())
    marker = "stage2-contract"
    person = int(conn.execute(text("""INSERT INTO public.persons(full_name,match_key,person_status,source)
        VALUES(:name,:key,'active','migration') RETURNING person_id"""), {"name": marker, "key": marker}).scalar_one())
    employee = int(conn.execute(text("""INSERT INTO public.employees(full_name,person_id,is_active,operational_status)
        VALUES(:name,:person,true,'active') RETURNING employee_id"""), {"name": marker, "person": person}).scalar_one())
    batch = int(conn.execute(text("""INSERT INTO public.hr_import_batches(source_type,file_name,import_code,imported_by,status)
        VALUES('HR_CONTROL_LIST','stage2-contract.xlsx','stage2-contract',:actor,'APPLY_PENDING') RETURNING batch_id"""), {"actor": actor}).scalar_one())
    row = int(conn.execute(text("""INSERT INTO public.hr_import_rows(batch_id,source_sheet,source_row_number,raw_payload,normalized_payload,employee_id)
        VALUES(:batch,'Synthetic',1,'{}'::jsonb,'{}'::jsonb,:employee) RETURNING row_id"""), {"batch": batch, "employee": employee}).scalar_one())
    conn.execute(text("""INSERT INTO public.hr_import_normalized_records(batch_id,row_id,employee_id,fragment_index,source_field,source_text,source_record_key,record_kind,title,parse_method,review_status)
        VALUES(:batch,:row,:employee,0,'education','',:key,'education',:title,'manual','approved'),
              (:batch,:row,:employee,1,'education','',:key2,'education',:title2,'manual','approved')"""),
        {"batch": batch, "row": row, "employee": employee, "key": "edu-0", "key2": "edu-1", "title": "\u0414\u0438\u043f\u043b\u043e\u043c A", "title2": "\u0414\u0438\u043f\u043b\u043e\u043c B"})
    preview = preview_stage0_cohort(conn, source_batch_id=batch)
    frozen = freeze_stage0_cohort(conn, source_batch_id=batch, preview_fingerprint=preview["preview_fingerprint"], actor_user_id=actor)
    return actor, int(frozen["stage0_cohort_run_id"]), person


def _stage2_cohort_for_employee(conn, *, actor: int, employee: int, fragments: list[dict[str, object]]) -> int:
    """Create one isolated Stage-0 cohort with approved normalized fragments."""
    token = uuid4().hex
    batch = int(conn.execute(text("""INSERT INTO public.hr_import_batches(source_type,file_name,import_code,imported_by,status)
        VALUES('HR_CONTROL_LIST',:file,:code,:actor,'APPLY_PENDING') RETURNING batch_id"""),
        {"file": f"stage2-{token}.xlsx", "code": f"stage2-{token}", "actor": actor}).scalar_one())
    row = int(conn.execute(text("""INSERT INTO public.hr_import_rows(batch_id,source_sheet,source_row_number,raw_payload,normalized_payload,employee_id)
        VALUES(:batch,'Synthetic',1,'{}'::jsonb,'{}'::jsonb,:employee) RETURNING row_id"""),
        {"batch": batch, "employee": employee}).scalar_one())
    for index, fragment in enumerate(fragments):
        conn.execute(text("""INSERT INTO public.hr_import_normalized_records(
            batch_id,row_id,employee_id,fragment_index,source_field,source_text,source_record_key,
            record_kind,title,specialty_text,document_number,end_date,parse_method,review_status)
            VALUES(:batch,:row,:employee,:index,'education','',:source_key,:record_kind,
                   :title,:specialty,:number,:end_date,'manual','approved')"""), {
            "batch": batch, "row": row, "employee": employee, "index": index,
            "source_key": str(fragment.get("source_key") or f"education-{index}"),
            "record_kind": str(fragment.get("record_kind") or "education"),
            "title": str(fragment.get("title") or "\u0414\u0438\u043f\u043b\u043e\u043c University"),
            "specialty": fragment.get("specialty"), "number": fragment.get("number"),
            "end_date": fragment.get("end_date"),
        })
    preview = preview_stage0_cohort(conn, source_batch_id=batch)
    frozen = freeze_stage0_cohort(conn, source_batch_id=batch, preview_fingerprint=preview["preview_fingerprint"], actor_user_id=actor)
    return int(frozen["stage0_cohort_run_id"])


def _employee_for_cohort(conn, cohort: int) -> int:
    return int(conn.execute(text("SELECT employee_id FROM public.ppr_stage0_cohort_participants WHERE stage0_cohort_run_id=:cohort"), {"cohort": cohort}).scalar_one())


def _stage2_run(conn, *, actor: int, cohort: int) -> dict:
    preview = compute_preview_stage2(conn, stage0_cohort_run_id=cohort)
    return persist_preview_stage2(conn, stage0_cohort_run_id=cohort, actor_user_id=actor, expected_preview_fingerprint=preview["preview_fingerprint"])


def _accept_ready_stage2(conn, *, actor: int, run: dict) -> None:
    run_id = int(run["run"]["stage_run_id"])
    approve_stage2(conn, run_id=run_id, actor_user_id=actor)
    execute_next_stage2(conn, run_id=run_id, actor_user_id=actor)
    completed = execute_next_stage2(conn, run_id=run_id, actor_user_id=actor)
    summary = acceptance_summary(conn, run_id=int(completed["run"]["stage_run_id"]))
    accept_stage2(conn, run_id=run_id, actor_user_id=actor, acceptance_fingerprint=summary["acceptance_fingerprint"])


def test_stage2_preview_is_replayable_and_draft_only_on_corpsite_test():
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            assert conn.execute(text("SELECT current_database()")).scalar_one() == "corpsite_test"
            actor, cohort, person = _seed(conn)
            item_count_before = conn.execute(text("SELECT count(*) FROM public.personnel_migration_items")).scalar_one()
            preview = compute_preview_stage2(conn, stage0_cohort_run_id=cohort)
            run = persist_preview_stage2(conn, stage0_cohort_run_id=cohort, actor_user_id=actor, expected_preview_fingerprint=preview["preview_fingerprint"])
            replay = persist_preview_stage2(conn, stage0_cohort_run_id=cohort, actor_user_id=actor, expected_preview_fingerprint=preview["preview_fingerprint"])
            assert replay["run"]["stage_run_id"] == run["run"]["stage_run_id"]
            assert len(run["participants"][0]["fragments"]) == 2
            assert conn.execute(text("SELECT count(*) FROM public.personnel_migration_items")).scalar_one() == item_count_before
            assert conn.execute(text("SELECT count(*) FROM public.person_education WHERE person_id=:person"), {"person": person}).scalar_one() == 0
            run = approve_stage2(conn, run_id=run["run"]["stage_run_id"], actor_user_id=actor)
            assert run["run"]["status"] == "APPROVED"
            run = execute_next_stage2(conn, run_id=run["run"]["stage_run_id"], actor_user_id=actor)
            participant = run["participants"][0]
            assert participant["status"] == "COMPLETED", participant
            assert participant["pmf_run_id"] is not None
            provenance = conn.execute(text("SELECT import_batch_id,import_row_id FROM public.personnel_migration_items WHERE run_id=:run ORDER BY item_id"), {"run": participant["pmf_run_id"]}).mappings().all()
            assert len(provenance) == 2 and all(row["import_batch_id"] is not None and row["import_row_id"] is not None for row in provenance)
            run = execute_next_stage2(conn, run_id=run["run"]["stage_run_id"], actor_user_id=actor)
            assert run["run"]["status"] == "COMPLETED_PENDING_REVIEW"
            summary = acceptance_summary(conn, run_id=run["run"]["stage_run_id"])
            accepted = accept_stage2(conn, run_id=run["run"]["stage_run_id"], actor_user_id=actor, acceptance_fingerprint=summary["acceptance_fingerprint"])
            assert accepted["run"]["status"] == "ACCEPTED"
            assert conn.execute(text("SELECT count(*) FROM public.person_education WHERE person_id=:person"), {"person": person}).scalar_one() == 2
            assert conn.execute(text("SELECT run_status FROM public.personnel_migration_runs WHERE run_id=:run"), {"run": participant["pmf_run_id"]}).scalar_one() == "committed"
            event_count = conn.execute(text("SELECT count(*) FROM public.personnel_record_events WHERE domain_code='education' AND person_id=:person"), {"person": person}).scalar_one()
            replay = accept_stage2(conn, run_id=run["run"]["stage_run_id"], actor_user_id=actor, acceptance_fingerprint="0" * 64)
            assert replay["run"]["status"] == "ACCEPTED"
            assert conn.execute(text("SELECT count(*) FROM public.personnel_record_events WHERE domain_code='education' AND person_id=:person"), {"person": person}).scalar_one() == event_count
        finally:
            tx.rollback()


def test_stage2_accepts_two_diplomas_with_same_kind_and_institution_when_numbers_differ():
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            actor, initial_cohort, person = _seed(conn)
            cohort = _stage2_cohort_for_employee(conn, actor=actor, employee=_employee_for_cohort(conn, initial_cohort), fragments=[
                {"source_key": "same-school-1", "title": "\u0414\u0438\u043f\u043b\u043e\u043c University", "number": "AB 001", "specialty": "Cardiology"},
                {"source_key": "same-school-2", "title": "\u0414\u0438\u043f\u043b\u043e\u043c University", "number": "AB 002", "specialty": "Cardiology"},
            ])
            run = _stage2_run(conn, actor=actor, cohort=cohort)
            assert [item["outcome"] for item in run["participants"][0]["fragments"]] == ["READY_TO_ADD", "READY_TO_ADD"]
            _accept_ready_stage2(conn, actor=actor, run=run)
            numbers = conn.execute(text("SELECT diploma_number FROM public.person_education WHERE person_id=:person ORDER BY diploma_number"), {"person": person}).scalars().all()
            assert numbers == ["AB 001", "AB 002"]
        finally:
            tx.rollback()


def test_stage2_exact_diploma_reimport_in_new_batch_is_already_applied():
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            actor, initial_cohort, person = _seed(conn)
            employee = _employee_for_cohort(conn, initial_cohort)
            first = _stage2_cohort_for_employee(conn, actor=actor, employee=employee, fragments=[
                {"source_key": "first-diploma", "title": "\u0414\u0438\u043f\u043b\u043e\u043c University", "number": "AB 001", "specialty": "Cardiology", "end_date": "2020-06-30"},
            ])
            _accept_ready_stage2(conn, actor=actor, run=_stage2_run(conn, actor=actor, cohort=first))
            second = _stage2_cohort_for_employee(conn, actor=actor, employee=employee, fragments=[
                {"source_key": "second-batch-same-diploma", "title": "  \u0414\u0418\u041f\u041b\u041e\u041c   University ", "number": " ab 001 ", "specialty": " cardiology ", "end_date": "2020-06-30"},
            ])
            replay = _stage2_run(conn, actor=actor, cohort=second)
            fragment = replay["participants"][0]["fragments"][0]
            assert fragment["outcome"] == "ALREADY_APPLIED"
            assert fragment["reason_code"] == "STAGE2_EXACT_CANONICAL_MATCH"
            _accept_ready_stage2(conn, actor=actor, run=replay)
            assert conn.execute(text("SELECT count(*) FROM public.person_education WHERE person_id=:person"), {"person": person}).scalar_one() == 1
        finally:
            tx.rollback()


def test_stage2_blocks_same_normalized_diploma_number_when_requisites_change():
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            actor, initial_cohort, _ = _seed(conn)
            employee = _employee_for_cohort(conn, initial_cohort)
            first = _stage2_cohort_for_employee(conn, actor=actor, employee=employee, fragments=[
                {"source_key": "first", "title": "\u0414\u0438\u043f\u043b\u043e\u043c University", "number": "AB 001", "specialty": "Cardiology"},
            ])
            _accept_ready_stage2(conn, actor=actor, run=_stage2_run(conn, actor=actor, cohort=first))
            second = _stage2_cohort_for_employee(conn, actor=actor, employee=employee, fragments=[
                {"source_key": "changed", "title": "\u0414\u0438\u043f\u043b\u043e\u043c University", "number": " ab 001 ", "specialty": "Neurology"},
            ])
            conflict = _stage2_run(conn, actor=actor, cohort=second)
            fragment = conflict["participants"][0]["fragments"][0]
            assert fragment["outcome"] == "CANONICAL_CONFLICT"
            assert fragment["reason_code"] == "STAGE2_CANONICAL_IDENTITY_AMBIGUOUS"
            try:
                approve_stage2(conn, run_id=int(conflict["run"]["stage_run_id"]), actor_user_id=actor)
            except Stage2ConflictError as exc:
                assert str(exc) == "STAGE2_APPROVAL_BLOCKED"
            else:
                raise AssertionError("same diploma number with changed requisites must block acceptance")
        finally:
            tx.rollback()


def test_stage2_accepts_unnumbered_diplomas_when_specialty_or_date_proves_difference():
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            actor, initial_cohort, person = _seed(conn)
            cohort = _stage2_cohort_for_employee(conn, actor=actor, employee=_employee_for_cohort(conn, initial_cohort), fragments=[
                {"source_key": "unnumbered-1", "title": "\u0414\u0438\u043f\u043b\u043e\u043c University", "specialty": "Cardiology", "end_date": "2020-06-30"},
                {"source_key": "unnumbered-2", "title": "\u0414\u0438\u043f\u043b\u043e\u043c University", "specialty": "Neurology", "end_date": "2021-06-30"},
            ])
            run = _stage2_run(conn, actor=actor, cohort=cohort)
            assert [item["outcome"] for item in run["participants"][0]["fragments"]] == ["READY_TO_ADD", "READY_TO_ADD"]
            _accept_ready_stage2(conn, actor=actor, run=run)
            assert conn.execute(text("SELECT count(*) FROM public.person_education WHERE person_id=:person"), {"person": person}).scalar_one() == 2
        finally:
            tx.rollback()


def test_stage2_ignores_training_normalized_records():
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            actor, initial_cohort, person = _seed(conn)
            cohort = _stage2_cohort_for_employee(conn, actor=actor, employee=_employee_for_cohort(conn, initial_cohort), fragments=[
                {"source_key": "education", "title": "\u0414\u0438\u043f\u043b\u043e\u043c University", "number": "AB 001"},
                {"source_key": "training", "record_kind": "training", "title": "ACLS", "number": "T 001"},
            ])
            run = _stage2_run(conn, actor=actor, cohort=cohort)
            assert len(run["participants"][0]["fragments"]) == 1
            _accept_ready_stage2(conn, actor=actor, run=run)
            assert conn.execute(text("SELECT count(*) FROM public.person_education WHERE person_id=:person"), {"person": person}).scalar_one() == 1
            assert conn.execute(text("SELECT count(*) FROM public.person_training WHERE person_id=:person"), {"person": person}).scalar_one() == 0
        finally:
            tx.rollback()


def test_stage2_preview_fails_closed_when_fingerprint_is_stale():
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            actor, cohort, _ = _seed(conn)
            preview = compute_preview_stage2(conn, stage0_cohort_run_id=cohort)
            conn.execute(text("UPDATE public.employees SET operational_status='suspended' WHERE employee_id=(SELECT employee_id FROM public.ppr_stage0_cohort_participants WHERE stage0_cohort_run_id=:id)"), {"id": cohort})
            try:
                persist_preview_stage2(conn, stage0_cohort_run_id=cohort, actor_user_id=actor, expected_preview_fingerprint=preview["preview_fingerprint"])
            except Stage2ConflictError as exc:
                assert str(exc) == "STAGE2_PREVIEW_STALE"
            else:
                raise AssertionError("stale preview must be rejected")
        finally:
            tx.rollback()


def test_resume_stale_keeps_specific_safe_code_and_creates_no_side_effects():
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            actor, cohort, person = _seed(conn)
            preview = compute_preview_stage2(conn, stage0_cohort_run_id=cohort)
            run = persist_preview_stage2(conn, stage0_cohort_run_id=cohort, actor_user_id=actor, expected_preview_fingerprint=preview["preview_fingerprint"])
            run_id = int(run["run"]["stage_run_id"])
            approve_stage2(conn, run_id=run_id, actor_user_id=actor)
            # Real fingerprinted source change after the frozen preview.
            conn.execute(text("UPDATE public.hr_import_normalized_records SET title='Диплом changed',source_text='changed',updated_at=clock_timestamp() WHERE batch_id=(SELECT source_batch_id FROM public.ppr_stage0_cohort_runs WHERE stage0_cohort_run_id=:cohort)"), {"cohort": cohort})
            before = (
                conn.execute(text("SELECT count(*) FROM public.personnel_migration_runs WHERE metadata #>> '{stage2,envelope_run_id}'=:run"), {"run": str(run_id)}).scalar_one(),
                conn.execute(text("SELECT count(*) FROM public.person_education WHERE person_id=:person"), {"person": person}).scalar_one(),
                conn.execute(text("SELECT count(*) FROM public.personnel_record_events WHERE person_id=:person"), {"person": person}).scalar_one(),
            )
            first = execute_next_stage2(conn, run_id=run_id, actor_user_id=actor)
            assert first["run"]["status"] == "PAUSED_ON_ERROR"
            assert first["run"]["last_error_code"] == "STAGE2_RESUME_STALE"
            replay = execute_next_stage2(conn, run_id=run_id, actor_user_id=actor, resume=True)
            assert replay["run"]["last_error_code"] == "STAGE2_RESUME_STALE"
            after = (
                conn.execute(text("SELECT count(*) FROM public.personnel_migration_runs WHERE metadata #>> '{stage2,envelope_run_id}'=:run"), {"run": str(run_id)}).scalar_one(),
                conn.execute(text("SELECT count(*) FROM public.person_education WHERE person_id=:person"), {"person": person}).scalar_one(),
                conn.execute(text("SELECT count(*) FROM public.personnel_record_events WHERE person_id=:person"), {"person": person}).scalar_one(),
            )
            assert after == before == (0, 0, 0)
        finally:
            tx.rollback()


def test_acceptance_pause_is_conditional_and_never_overwrites_cancelled():
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            actor, cohort, _ = _seed(conn)
            preview = compute_preview_stage2(conn, stage0_cohort_run_id=cohort)
            run = persist_preview_stage2(conn, stage0_cohort_run_id=cohort, actor_user_id=actor, expected_preview_fingerprint=preview["preview_fingerprint"])
            run_id = int(run["run"]["stage_run_id"])
            conn.execute(text("UPDATE public.ppr_stage_runs SET status='COMPLETED_PENDING_REVIEW', approved_by_user_id=:actor, approved_at=now() WHERE stage_run_id=:id"), {"actor": actor, "id": run_id})
            assert pause_acceptance_after_rollback(conn, run_id=run_id, exc=RuntimeError("synthetic")) is True
            paused = conn.execute(text("SELECT status,paused_operation,stopped_participant_id FROM public.ppr_stage_runs WHERE stage_run_id=:id"), {"id": run_id}).mappings().one()
            assert dict(paused) == {"status": "PAUSED_ON_ERROR", "paused_operation": "ACCEPTANCE", "stopped_participant_id": None}
            conn.execute(text("UPDATE public.ppr_stage_runs SET status='CANCELLED',cancelled_by_user_id=:actor,cancelled_at=now(),cancel_reason='test',paused_operation=NULL,paused_at=NULL,last_error_code=NULL,last_error_reference=NULL WHERE stage_run_id=:id"), {"actor": actor, "id": run_id})
            assert pause_acceptance_after_rollback(conn, run_id=run_id, exc=RuntimeError("retry")) is False
        finally:
            tx.rollback()
