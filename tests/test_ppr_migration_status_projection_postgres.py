"""WP-PPR-MIG-005B isolated PostgreSQL contracts (each test rolls back)."""
from __future__ import annotations
import json
from uuid import uuid4
import pytest
from sqlalchemy import text
from app.db.engine import engine
from app.services.ppr_stage0_cohort_service import preview_stage0_cohort, freeze_stage0_cohort
from app.services import ppr_migration_status_projection_service as projection

def _seed(conn, *, suffix: str | None = None):
    token=suffix or uuid4().hex; actor=int(conn.execute(text("select min(user_id) from users where is_active")).scalar_one())
    person=int(conn.execute(text("insert into persons(full_name,match_key,person_status,source) values(:n,:n,'active','migration') returning person_id"),{"n":f"wp005b-{token}"}).scalar_one())
    employee=int(conn.execute(text("insert into employees(full_name,person_id,is_active,operational_status) values(:n,:p,true,'active') returning employee_id"),{"n":f"wp005b-{token}","p":person}).scalar_one())
    batch=int(conn.execute(text("insert into hr_import_batches(source_type,file_name,import_code,imported_by,status) values('HR_CONTROL_LIST',:n,:n,:a,'APPLY_PENDING') returning batch_id"),{"n":f"wp005b-{token}","a":actor}).scalar_one())
    row=int(conn.execute(text("insert into hr_import_rows(batch_id,source_sheet,source_row_number,raw_payload,normalized_payload,employee_id) values(:b,'T',1,'{}'::jsonb,cast(:payload as jsonb),:e) returning row_id"),{"b":batch,"payload":json.dumps({"full_name":"Test Person"}),"e":employee}).scalar_one())
    preview=preview_stage0_cohort(conn,source_batch_id=batch)
    cohort=int(freeze_stage0_cohort(conn,source_batch_id=batch,preview_fingerprint=preview['preview_fingerprint'],actor_user_id=actor)['stage0_cohort_run_id'])
    return actor,person,employee,row,cohort

def _accepted_general(conn, actor, person, employee, row, cohort, *, policy='PPR_STAGE1_GENERAL_V1', cancelled=False):
    status='CANCELLED' if cancelled else 'ACCEPTED'; accepted="now()" if not cancelled else "NULL"
    run=int(conn.execute(text(f"insert into ppr_stage1_general_runs(stage0_cohort_run_id,status,preview_fingerprint,policy_version,created_by_user_id,accepted_by_user_id,accepted_at) values(:c,'{status}',:f,:v,:a,{':a' if not cancelled else 'NULL'},{accepted}) returning stage1_run_id"),{"c":cohort,"f":uuid4().hex+uuid4().hex,"v":policy,"a":actor}).scalar_one())
    conn.execute(text("insert into ppr_stage1_general_participants(stage1_run_id,position,employee_id,person_id,source_row_id,source_fingerprint,proposed_values,status,completed_at) values(:r,1,:e,:p,:row,:f,'{}'::jsonb,'COMPLETED',now())"),{"r":run,"e":employee,"p":person,"row":row,"f":"a"*64})
    if not cancelled:
        conn.execute(text("insert into personnel_record_events(person_id,employee_context_id,domain_code,record_table_name,record_id,event_type,event_payload) values(:p,:e,'general_information','persons',:p,'PPR_STAGE1_GENERAL_ACCEPTED',cast(:payload as jsonb))"),{"p":person,"e":employee,"payload":json.dumps({"stage1_run_id":run})})
    return run

def _tx():
    conn=engine.connect(); tx=conn.begin(); assert conn.execute(text("select current_database()")).scalar_one()=="corpsite_test"; return conn,tx

def test_universe_identity_explicit_supplemental_and_idempotent():
    conn,tx=_tx()
    try:
        actor,person,employee,row,base=_seed(conn); _,_,_,_,supp=_seed(conn)
        conn.execute(text("update ppr_stage0_cohort_runs set run_kind='SUPPLEMENTAL',supplemental_of_run_id=:base where stage0_cohort_run_id=:supp"),{"base":base,"supp":supp})
        one=projection.ensure_universe(conn,base_cohort_run_id=base,supplemental_cohort_run_ids=[supp]); two=projection.ensure_universe(conn,base_cohort_run_id=base,supplemental_cohort_run_ids=[supp])
        assert one==two
        assert conn.execute(text("select count(*) from ppr_migration_status_universe_cohorts where universe_id=:u"),{"u":one}).scalar_one()==2
    finally: tx.rollback(); conn.close()

def test_rebuild_membership_idempotency_scope_and_no_pii():
    conn,tx=_tx()
    try:
        actor,person,employee,row,base=_seed(conn); _,outside,_,_,_=_seed(conn)
        u=projection.ensure_universe(conn,base_cohort_run_id=base); assert projection.rebuild_universe(conn,universe_id=u)==3; assert projection.rebuild_universe(conn,universe_id=u)==3
        rows=projection.list_projection_for_scope(conn,universe_id=u,org_unit_ids=None)
        assert {(r['person_id'],r['section_code']) for r in rows} == {(person,s) for s in projection.SECTIONS}
        assert outside not in {r['person_id'] for r in rows}; assert projection.list_projection_for_scope(conn,universe_id=u,org_unit_ids=[])==[]
        cols=set(conn.execute(text("select column_name from information_schema.columns where table_name='ppr_migration_section_status_projection'")).scalars())
        assert not cols & {'full_name','iin','raw_payload','normalized_payload','source_text','document'}
    finally: tx.rollback(); conn.close()

def test_multiple_runs_cancelled_latest_and_fingerprint_invalidation():
    conn,tx=_tx()
    try:
        actor,person,employee,row,base=_seed(conn); old=_accepted_general(conn,actor,person,employee,row,base)
        _accepted_general(conn,actor,person,employee,row,base,cancelled=True)
        u=projection.ensure_universe(conn,base_cohort_run_id=base); projection.rebuild_universe(conn,universe_id=u)
        status=conn.execute(text("select status_code,stage1_run_id from ppr_migration_section_status_projection where universe_id=:u and person_id=:p and section_code='general'"),{"u":u,"p":person}).one()
        assert status==( 'ACCEPTED',old )
        conn.execute(text("update hr_import_rows set normalized_payload=cast(:x as jsonb) where row_id=:r"),{"x":json.dumps({"full_name":"changed"}),"r":row})
        projection.rebuild_universe(conn,universe_id=u)
        assert conn.execute(text("select status_code from ppr_migration_section_status_projection where universe_id=:u and person_id=:p and section_code='general'"),{"u":u,"p":person}).scalar_one()=="STALE"
    finally: tx.rollback(); conn.close()

def test_policy_stale_and_general_acceptance_requires_event(monkeypatch):
    conn,tx=_tx()
    try:
        actor,person,employee,row,base=_seed(conn); run=_accepted_general(conn,actor,person,employee,row,base)
        u=projection.ensure_universe(conn,base_cohort_run_id=base); projection.rebuild_universe(conn,universe_id=u)
        conn.execute(text("update ppr_stage1_general_runs set policy_version='PPR_STAGE1_GENERAL_V2' where stage1_run_id=:r"),{"r":run})
        projection.rebuild_universe(conn,universe_id=u)
        assert conn.execute(text("select status_code,reason_code from ppr_migration_section_status_projection where universe_id=:u and person_id=:p and section_code='general'"),{"u":u,"p":person}).one()==('STALE','FINGERPRINT_POLICY_CHANGED')
    finally: tx.rollback(); conn.close()

def test_rebuild_rollback_preserves_previous_projection(monkeypatch):
    conn,tx=_tx()
    try:
        actor,person,employee,row,base=_seed(conn); _accepted_general(conn,actor,person,employee,row,base)
        u=projection.ensure_universe(conn,base_cohort_run_id=base); projection.rebuild_universe(conn,universe_id=u)
        before=conn.execute(text("select count(*) from ppr_migration_section_status_projection where universe_id=:u"),{"u":u}).scalar_one()
        nested=conn.begin_nested(); monkeypatch.setattr(projection,'_status',lambda *_a,**_k: (_ for _ in ()).throw(RuntimeError('injected')))
        with pytest.raises(RuntimeError): projection.rebuild_universe(conn,universe_id=u)
        nested.rollback()
        assert conn.execute(text("select count(*) from ppr_migration_section_status_projection where universe_id=:u"),{"u":u}).scalar_one()==before
    finally: tx.rollback(); conn.close()
