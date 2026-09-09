"""PostgreSQL contract for Stage 1 draft, pause/resume and atomic acceptance."""
from __future__ import annotations
from uuid import uuid4
from sqlalchemy import text
from app.db.engine import engine
from app.services.ppr_stage0_cohort_service import preview_stage0_cohort, freeze_stage0_cohort
from app.services.ppr_stage1_general_service import preview_stage1, approve_stage1, execute_next_stage1, accept_stage1_run, Stage1ConflictError
from app.api.ppr_stage1_general_router import _scope_run
from fastapi import HTTPException


def _seed(conn, *, org_unit_id=None):
    marker=uuid4().hex[:10]; actor=int(conn.execute(text("SELECT min(user_id) FROM public.users WHERE is_active")).scalar_one())
    batch=int(conn.execute(text("INSERT INTO public.hr_import_batches(source_type,file_name,import_code,imported_by,status) VALUES('HR_CONTROL_LIST',:f,:c,:a,'APPLY_PENDING') RETURNING batch_id"),{'f':f'stage1-{marker}.xlsx','c':f'stage1-{marker}','a':actor}).scalar_one())
    employees=[]
    for position in (1,2):
        name=f'Stage One {marker}{position}'
        person=int(conn.execute(text("INSERT INTO public.persons(full_name,match_key,person_status,source) VALUES(:n,:k,'active','migration') RETURNING person_id"),{'n':name,'k':f's1-{marker}-{position}'}).scalar_one())
        employee=int(conn.execute(text("INSERT INTO public.employees(full_name,person_id,org_unit_id,is_active,operational_status) VALUES(:n,:p,:unit,true,'active') RETURNING employee_id"),{'n':name,'p':person,'unit':org_unit_id}).scalar_one())
        conn.execute(text("INSERT INTO public.hr_import_rows(batch_id,source_sheet,source_row_number,raw_payload,normalized_payload,employee_id) VALUES(:b,'Synthetic',:pos,'{}'::jsonb,CAST(:payload AS jsonb),:e)"),{'b':batch,'pos':position,'e':employee,'payload':'{"full_name":"'+name+'","iin":"90010100000'+str(position)+'","birth_date":"1990-01-0'+str(position)+'"}'})
        employees.append((employee,person))
    p=preview_stage0_cohort(conn,source_batch_id=batch); frozen=freeze_stage0_cohort(conn,source_batch_id=batch,preview_fingerprint=p['preview_fingerprint'],actor_user_id=actor)
    return actor,frozen['stage0_cohort_run_id'],employees


def test_stage1_drafts_pause_resume_and_accept_atomically_on_corpsite_test():
    with engine.connect() as conn:
        tx=conn.begin()
        try:
            assert conn.execute(text('SELECT current_database()')).scalar_one()=='corpsite_test'
            actor,cohort,employees=_seed(conn)
            run=preview_stage1(conn,stage0_cohort_run_id=cohort,actor_user_id=actor)
            assert run['run']['status']=='DRY_RUN_COMPLETED'
            assert all(p['status']=='PENDING' for p in run['participants'])
            # Preview is draft-only: no canonical identity and no PPR envelope yet.
            assert conn.execute(text('SELECT iin FROM public.persons WHERE person_id=:p'),{'p':employees[0][1]}).scalar_one() is None
            assert conn.execute(text('SELECT count(*) FROM public.personnel_record_metadata WHERE person_id=:p'),{'p':employees[0][1]}).scalar_one()==0
            run=approve_stage1(conn,run_id=run['run']['stage1_run_id'])
            run=execute_next_stage1(conn,run_id=run['run']['stage1_run_id']); assert run['participants'][0]['status']=='COMPLETED'
            # Drift only the second employee after approval: it stops at that same position.
            conn.execute(text("UPDATE public.persons SET last_name='Conflicting' WHERE person_id=:p"),{'p':employees[1][1]})
            run=execute_next_stage1(conn,run_id=run['run']['stage1_run_id']); assert run['run']['status']=='PAUSED_ON_ERROR'; assert run['participants'][1]['status']=='ERROR'
            conflict=run['participants'][1]
            assert conflict['conflicts']==[{'field':'last_name','code':'STAGE1_CANONICAL_VALUE_CONFLICT'}]
            assert conflict['source']['last_name']=='Stage' and conflict['current']['last_name']=='Conflicting'
            conn.execute(text('UPDATE public.persons SET last_name=NULL WHERE person_id=:p'),{'p':employees[1][1]})
            run=execute_next_stage1(conn,run_id=run['run']['stage1_run_id']); assert run['participants'][1]['status']=='COMPLETED'
            run=execute_next_stage1(conn,run_id=run['run']['stage1_run_id']); assert run['run']['status']=='COMPLETED_PENDING_REVIEW'
            run=accept_stage1_run(conn,run_id=run['run']['stage1_run_id'],actor_user_id=actor); assert run['run']['status']=='ACCEPTED'
            events_before=conn.execute(text("SELECT count(*) FROM public.personnel_record_events WHERE event_type='PPR_STAGE1_GENERAL_ACCEPTED' AND event_payload->>'stage1_run_id'=:run"),{'run':str(run['run']['stage1_run_id'])}).scalar_one()
            try: accept_stage1_run(conn,run_id=run['run']['stage1_run_id'],actor_user_id=actor)
            except Stage1ConflictError as exc: assert str(exc)=='STAGE1_RUN_NOT_READY_FOR_ACCEPTANCE'
            else: raise AssertionError('accepted Stage 1 run must not be accepted twice')
            assert conn.execute(text("SELECT count(*) FROM public.personnel_record_events WHERE event_type='PPR_STAGE1_GENERAL_ACCEPTED' AND event_payload->>'stage1_run_id'=:run"),{'run':str(run['run']['stage1_run_id'])}).scalar_one()==events_before
            values=conn.execute(text('SELECT iin,birth_date,last_name,first_name FROM public.persons WHERE person_id=:p'),{'p':employees[0][1]}).mappings().one()
            assert values['iin']=='900101000001' and str(values['birth_date'])=='1990-01-01' and values['last_name']=='Stage' and values['first_name']=='One'
            assert conn.execute(text('SELECT ppr_lifecycle_state FROM public.personnel_record_metadata WHERE person_id=:p'),{'p':employees[0][1]}).scalar_one()=='COLLECTING'
        finally: tx.rollback()


def test_stage1_acceptance_rejects_stale_canonical_values_without_writes():
    with engine.connect() as conn:
        tx=conn.begin()
        try:
            actor,cohort,employees=_seed(conn); run=preview_stage1(conn,stage0_cohort_run_id=cohort,actor_user_id=actor); run=approve_stage1(conn,run_id=run['run']['stage1_run_id'])
            run=execute_next_stage1(conn,run_id=run['run']['stage1_run_id']); run=execute_next_stage1(conn,run_id=run['run']['stage1_run_id']); run=execute_next_stage1(conn,run_id=run['run']['stage1_run_id'])
            conn.execute(text("UPDATE public.persons SET first_name='Stale' WHERE person_id=:p"),{'p':employees[0][1]})
            try: accept_stage1_run(conn,run_id=run['run']['stage1_run_id'],actor_user_id=actor)
            except Stage1ConflictError as exc: assert str(exc)=='STAGE1_ACCEPTANCE_STALE_OR_CONFLICT'
            else: raise AssertionError('acceptance must fail closed')
            assert conn.execute(text('SELECT iin FROM public.persons WHERE person_id=:p'),{'p':employees[1][1]}).scalar_one() is None
        finally: tx.rollback()


def test_stage1_scope_is_fail_closed_and_uses_russian_message():
    with engine.connect() as conn:
        tx=conn.begin()
        try:
            unit=conn.execute(text('SELECT min(unit_id) FROM public.org_units WHERE COALESCE(is_active,true)')).scalar_one()
            assert unit is not None
            _,cohort,_=_seed(conn,org_unit_id=int(unit))
            _scope_run(conn,cohort,{'privileged':False,'scope_unit_ids':[int(unit)]})
            try:
                _scope_run(conn,cohort,{'privileged':False,'scope_unit_ids':[]})
            except HTTPException as exc:
                assert exc.status_code==404
                assert exc.detail=={'code':'STAGE1_RUN_OUT_OF_SCOPE','message':'Данные этого этапа находятся вне разрешённого для вас подразделения.'}
            else: raise AssertionError('out-of-scope Stage 1 run must fail closed')
        finally: tx.rollback()
