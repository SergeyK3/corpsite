"""PostgreSQL integration coverage for Stage 0 safe PREVIEW/FREEZE."""
from __future__ import annotations

from uuid import uuid4

from sqlalchemy import text

from app.db.engine import engine
from app.services.ppr_stage0_cohort_service import (
    Stage0ConflictError,
    freeze_stage0_cohort,
    preview_stage0_cohort,
)


def _seed_synthetic_candidate(conn):
    marker = uuid4().hex[:12]
    actor = conn.execute(text("SELECT min(user_id) FROM public.users WHERE is_active=true")).scalar_one()
    assert actor is not None
    person_id = conn.execute(text("""
        INSERT INTO public.persons(iin,full_name,match_key,person_status,source)
        VALUES(NULL,:name,:key,'active','migration') RETURNING person_id
    """), {"name": f"Stage Zero Test {marker}", "key": f"stage0-{marker}"}).scalar_one()
    employee_id = conn.execute(text("""
        INSERT INTO public.employees(full_name,person_id,is_active,operational_status)
        VALUES(:name,:person_id,true,'active') RETURNING employee_id
    """), {"name": f"Stage Zero Test {marker}", "person_id": person_id}).scalar_one()
    batch_id = conn.execute(text("""
        INSERT INTO public.hr_import_batches(source_type,file_name,import_code,imported_by,status)
        VALUES('HR_CONTROL_LIST',:file,:code,:actor,'APPLY_PENDING') RETURNING batch_id
    """), {"file": f"stage0-{marker}.xlsx", "code": f"stage0-{marker}", "actor": actor}).scalar_one()
    conn.execute(text("""
        INSERT INTO public.hr_import_rows(batch_id,source_sheet,source_row_number,raw_payload,normalized_payload,employee_id)
        VALUES(:batch_id,'Synthetic',1,'{}'::jsonb,'{}'::jsonb,:employee_id)
    """), {"batch_id": batch_id, "employee_id": employee_id})
    return int(actor), int(batch_id), int(employee_id)


def test_preview_is_read_only_and_freeze_is_replayable_on_corpsite_test():
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            assert conn.execute(text("SELECT current_database()")).scalar_one() == "corpsite_test"
            actor, batch_id, _ = _seed_synthetic_candidate(conn)
            ppr_before = conn.execute(text("SELECT count(*) FROM public.personnel_record_metadata")).scalar_one()
            preview = preview_stage0_cohort(conn, source_batch_id=batch_id)
            assert len(preview["eligible"]) == 1
            assert conn.execute(text("SELECT count(*) FROM public.ppr_stage0_cohort_runs WHERE source_batch_id=:batch"), {"batch": batch_id}).scalar_one() == 0
            frozen = freeze_stage0_cohort(conn, source_batch_id=batch_id, preview_fingerprint=preview["preview_fingerprint"], actor_user_id=actor)
            replay = freeze_stage0_cohort(conn, source_batch_id=batch_id, preview_fingerprint=preview["preview_fingerprint"], actor_user_id=actor)
            assert frozen["replay"] is False
            assert replay["stage0_cohort_run_id"] == frozen["stage0_cohort_run_id"]
            assert replay["replay"] is True
            assert conn.execute(text("SELECT count(*) FROM public.personnel_record_metadata")).scalar_one() == ppr_before
        finally:
            tx.rollback()


def test_freeze_rejects_a_stale_preview_on_corpsite_test():
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            actor, batch_id, employee_id = _seed_synthetic_candidate(conn)
            preview = preview_stage0_cohort(conn, source_batch_id=batch_id)
            conn.execute(text("UPDATE public.employees SET operational_status='suspended' WHERE employee_id=:employee_id"), {"employee_id": employee_id})
            try:
                freeze_stage0_cohort(conn, source_batch_id=batch_id, preview_fingerprint=preview["preview_fingerprint"], actor_user_id=actor)
            except Stage0ConflictError as exc:
                assert str(exc) == "STAGE0_PREVIEW_STALE"
            else:
                raise AssertionError("FREEZE must reject changed source state")
        finally:
            tx.rollback()
