"""Reviewed server subset: no network, server connection, or historical inserts."""
import json
from pathlib import Path
import pytest
from sqlalchemy import create_engine,text
from app.services import job_catalog_service as catalog
from app.services import job_catalog_server_policy as policy

ROOT=Path(__file__).resolve().parents[1]
ROWS=catalog.read_catalog(ROOT/'reference-data/job-positions/server-catalog-v1.json')
REVIEW=policy.read_review(ROOT/'reference-data/job-positions/server-link-review-v1.json')
POSITIONS=[{'position_id':row['position_id'],'name':row['server_name']} for row in REVIEW['approved_links']]+REVIEW['unmapped_server_positions']

def plan(positions=POSITIONS,links=()):
    return policy.plan_server_catalog(ROWS,REVIEW,positions,links=links,catalog_planner=catalog.plan_catalog)

def test_preserves_all_88_approved_professions_and_explicit_89_ids():
    original=catalog.read_catalog(ROOT/'reference-data/job-positions/catalog-v1.json')
    assert len(ROWS)==88 and sum(len(r['legacy_position_ids']) for r in ROWS)==89
    assert [{k:v for k,v in r.items() if k!='legacy_position_ids'} for r in ROWS]==[{k:v for k,v in r.items() if k!='legacy_position_ids'} for r in original]
    assert len(REVIEW['skipped_missing_links'])==19 and REVIEW['withheld_links']==[]
    approved={row['position_id']:row for row in REVIEW['approved_links']}
    assert approved[71]['job_code']=='CLINICAL_DEPARTMENT_HEAD'
    assert approved[61]['job_code']=='PHYSICIAN_STATISTICIAN'
    assert all(approved[pid]['job_code']=='EXPERT_PHYSICIAN' for pid in range(93,97))
    assert all('Пользователь явно подтвердил' in approved[pid]['review_basis'] for pid in (61,93,94,95,96))

def test_original_missing_ids_no_longer_block_and_are_reported():
    assert len(POSITIONS)==111
    original= catalog.plan_catalog(catalog.read_catalog(ROOT/'reference-data/job-positions/catalog-v1.json'),POSITIONS)
    assert len(original['missing_ids'])==19 and not original['can_apply']
    result=plan();assert result['can_apply'] and result['rows']==88 and result['active_link_count']==89
    assert result['skipped_missing_ids']==original['missing_ids']
    assert result['planned_changes']['position_updates']==0 and result['planned_changes']['assignment_updates']==0
    assert len(result['unmapped_existing_ids'])==22

def test_further_absent_reviewed_id_is_skipped_and_never_inserted():
    result=plan([r for r in POSITIONS if r['position_id']!=71])
    assert result['can_apply'] and result['rows']==88 and result['active_link_count']==88
    assert 71 in result['skipped_missing_ids'] and result['missing_ids']==[]
    assert all(71 not in row['legacy_position_ids'] for row in result['mappings'])

def test_changed_meaning_at_same_id_blocks_instead_of_name_matching():
    changed=[{**row,'name':'Кассир'} if row['position_id']==6 else row for row in POSITIONS]
    result=plan(changed);assert not result['can_apply']
    assert result['name_conflicts']==[{'position_id':6,'expected_name':'Врач','actual_name':'Кассир','job_code':'PHYSICIAN'}]
    assert next(r for r in result['mappings'] if r['job_code']=='PHYSICIAN')['legacy_position_ids']==[6]

def test_equal_name_at_different_id_and_newly_present_unreviewed_id_are_not_mapped():
    result=plan(POSITIONS+[{'position_id':717,'name':'Медицинский статистик'}])
    assert result['can_apply'] and result['active_link_count']==89
    assert [row['position_id'] for row in result['unreviewed_now_present']]==[717]
    ids={pid for row in result['mappings'] for pid in row['legacy_position_ids']}
    assert not {24,47,52,99,100,101,102,104,105,106,107,108,109,110,111,112,113,114,115,717}&ids

def test_existing_wrong_or_unreviewed_link_blocks_without_overwriting():
    result=plan(links=[{'position_id':71,'job_code':'ECONOMIST'}]);assert not result['can_apply']
    assert any('already mapped' in message for message in result['conflicts'])
    result=plan(links=[{'position_id':105,'job_code':'MEDICAL_STATISTICIAN'}]);assert not result['can_apply']
    assert result['unreviewed_existing_links']==[{'position_id':105,'job_code':'MEDICAL_STATISTICIAN'}]

def test_import_keeps_111_historical_positions_assignments_texts_and_is_idempotent():
    engine=create_engine('sqlite://')
    with engine.begin() as conn:
        conn.execute(text("ATTACH DATABASE ':memory:' AS public"))
        conn.connection.driver_connection.create_function('to_regclass',1,lambda _: 'job_positions_catalog')
        conn.execute(text('CREATE TABLE public.positions(position_id INTEGER PRIMARY KEY,name TEXT)'))
        conn.execute(text('CREATE TABLE public.job_positions_catalog(job_code TEXT PRIMARY KEY,job_nameru TEXT,job_namekk TEXT,job_namekk_doc TEXT)'))
        conn.execute(text('CREATE TABLE public.position_job_catalog(position_id INTEGER PRIMARY KEY,job_code TEXT)'))
        conn.execute(text('CREATE TABLE public.person_assignments(assignment_id INTEGER PRIMARY KEY,position_id INTEGER)'))
        conn.execute(text('CREATE TABLE public.personnel_orders(order_id INTEGER PRIMARY KEY,saved_text TEXT)'))
        conn.execute(text('INSERT INTO public.positions VALUES (:position_id,:name)'),POSITIONS)
        conn.execute(text('INSERT INTO public.person_assignments VALUES (151,71)'))
        conn.execute(text("INSERT INTO public.personnel_orders VALUES (1,'Утверждённый исторический RU/KZ-текст')"))
        before=conn.execute(text('SELECT * FROM public.positions ORDER BY position_id')).all();calls=[]
        class Adapter:
            def execute(self,query,params=None):
                calls.append(str(query))
                if str(query).startswith('LOCK TABLE'):return None
                return conn.execute(query,params or {})
        adapter=Adapter()
        policy.apply_catalog(adapter,ROWS,REVIEW,catalog_module=catalog)
        again=policy.apply_catalog(adapter,ROWS,REVIEW,catalog_module=catalog)
        assert again['planned_changes']['total']==0
        assert conn.execute(text('SELECT count(*) FROM public.job_positions_catalog')).scalar_one()==88
        assert conn.execute(text('SELECT count(*) FROM public.position_job_catalog')).scalar_one()==89
        assert conn.execute(text('SELECT * FROM public.positions ORDER BY position_id')).all()==before
        assert conn.execute(text('SELECT position_id FROM public.person_assignments')).scalar_one()==71
        assert conn.execute(text('SELECT saved_text FROM public.personnel_orders')).scalar_one()=='Утверждённый исторический RU/KZ-текст'
        assert not any(query.lstrip().startswith(('INSERT INTO public.positions','UPDATE public.positions','DELETE','UPDATE public.person_assignments')) for query in calls)
        conn.execute(text("UPDATE public.job_positions_catalog SET job_namekk_doc='Ручная форма' WHERE job_code='NURSE'"))
        with pytest.raises(ValueError):policy.apply_catalog(adapter,ROWS,REVIEW,catalog_module=catalog)
        assert conn.execute(text("SELECT job_namekk_doc FROM public.job_positions_catalog WHERE job_code='NURSE'")).scalar_one()=='Ручная форма'

def test_reviewed_ids_cannot_be_extended_by_catalog_alone():
    changed=json.loads(json.dumps(ROWS));next(row for row in changed if row['job_code']=='LAUNDRY_MACHINE_OPERATOR')['legacy_position_ids']=[24]
    with pytest.raises(ValueError,match='explicit reviewed IDs'):
        policy.plan_server_catalog(changed,REVIEW,POSITIONS,catalog_planner=catalog.plan_catalog)
