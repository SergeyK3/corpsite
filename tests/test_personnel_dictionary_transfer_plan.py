"""Pure synthetic reconciliation tests. No database or network connections."""
from copy import deepcopy
import json
from scripts.plan_personnel_dictionary_transfer import make_plan,update_approved_positions,FIELDS


TABLES=('positions','position_aliases','position_job_catalog','job_positions_catalog','medical_specialties','medical_specialty_groups')
def fixture():
    pos={'name':'TEST variant','category':'medical','name_kk':None,'document_nominative_ru':'TEST variant',
         'document_possessive_kk':None,'translation_status':'needs_review','document_form_status':'needs_review','record_kind':'variant'}
    rows={t:[] for t in TABLES}
    rows.update(positions=[{'position_id':1,**pos}],job_positions_catalog=[{'job_code':'TEST','job_nameru':'TEST family','job_namekk':'TEST KK','job_namekk_doc':'TEST KK doc'}],
        position_job_catalog=[{'position_id':1,'job_code':'TEST'}],position_aliases=[{'position_id':1,'alias_text':'TEST synonym','normalized_alias':'test synonym'}],
        medical_specialty_groups=[{'group_id':1,'code':'TEST','name':'TEST group','is_active':True}],
        medical_specialties=[{'medical_specialty_id':1,'group_id':1,'code':'SPECIALTY','name':'TEST specialty','name_kk':'TEST KK specialty','is_active':True}])
    source={'dictionaries':{t:{'rows':r} for t,r in rows.items()}}
    target=deepcopy(source);target['database_revision']=['poprint001']
    for table in ('positions','position_aliases','position_job_catalog'):
        for r in target['dictionaries'][table]['rows']:r['position_id']=900
    target['dictionaries']['medical_specialty_groups']['rows'][0]['group_id']=700
    target['dictionaries']['medical_specialties']['rows'][0].update(group_id=700,medical_specialty_id=800)
    cols={**FIELDS,'position_aliases':('position_id','alias_text','normalized_alias'),'position_job_catalog':('position_id','job_code')}
    schema={'dictionary_columns':[{'table_name':t,'column_name':k} for t,ks in cols.items() for k in ks]}
    return source,target,schema


def test_different_local_and_target_ids_match_semantically_and_emit_no_id_writes():
    s,t,c=fixture();p=make_plan(s,t,c)
    assert p['expected_operations']=={'SKIP':6}
    assert p['global_blockers']==[]
    assert all(e['status']=='MATCH' for e in p['records'])
    assert not any(k in json.dumps(p['records']) for k in ('position_id','group_id','medical_specialty_id'))


def test_pending_translations_are_not_promoted_and_confirmed_target_cannot_be_erased():
    s,t,c=fixture();t['dictionaries']['positions']['rows'][0].update(name_kk='TEST confirmed',translation_status='confirmed')
    p=make_plan(s,t,c)
    pos=next(e for e in p['records'] if e['table']=='positions')
    assert pos['status']=='CONFLICT' and pos['desired']['translation_status']=='needs_review'
    assert all(e['operation']=='NONE' for e in p['records'] if e['table'] in ('positions','position_job_catalog','position_aliases'))


def test_category_mismatch_is_manual_and_target_only_records_are_retained():
    s,t,c=fixture();t['dictionaries']['positions']['rows'][0]['category']='other'
    p=make_plan(s,t,c)
    assert next(e for e in p['records'] if e['table']=='positions')['status']=='MANUAL'
    assert all(e['operation']=='KEEP_UNCHANGED' for e in p['production_only_keep'])
    assert not any(e['operation']=='DELETE' for e in p['records'])


def test_schema_gate_missing_columns_and_idempotent_replanning():
    s,t,c=fixture();t['database_revision']=['podup001']
    t['dictionaries']['medical_specialties']['rows'][0].pop('name_kk')
    c['dictionary_columns']=[r for r in c['dictionary_columns'] if (r['table_name'],r['column_name'])!=('medical_specialties','name_kk')]
    first=make_plan(s,t,c)
    assert first['global_blockers']
    e=next(e for e in first['records'] if e['table']=='medical_specialties')
    assert e['blockers']==[{'schema_columns_missing':['name_kk']}]
    assert first==make_plan(s,t,c)
    # Simulate an approved result entirely in memory, then rerun the same planner.
    _,t,c=fixture()
    assert make_plan(s,t,c)['expected_operations']=={'SKIP':6}


def test_duplicate_position_keys_do_not_merge_source_identities():
    s,t,c=fixture();s['dictionaries']['positions']['rows'].append({**s['dictionaries']['positions']['rows'][0],'position_id':2})
    p=make_plan(s,t,c)
    assert all(e['status']=='MANUAL' for e in p['records'] if e['table']=='positions')


def approval():
    return {'position_category_decisions':[{'approval_id':'TEST-owner-category','source_key':{'name':'TEST variant','category':'medical'},
        'target_category':'other','required_job_code':'TEST','require_existing_target':True,'preserve_existing_target_id':True}]}


def test_owner_approval_reuses_existing_identity_and_checks_missing_family_link():
    s,t,c=fixture();t['dictionaries']['positions']['rows'][0]['category']='other'
    t['dictionaries']['position_job_catalog']['rows']=[]
    original_s,original_t=deepcopy(s),deepcopy(t)
    previous=make_plan(s,t,c)
    updated=update_approved_positions(previous,s,t,c,approval())
    position=next(r for r in updated['records'] if r['table']=='positions')
    link=next(r for r in updated['records'] if r['table']=='position_job_catalog')
    assert position['key']['category']==position['desired']['category']=='other'
    assert position['status']=='MATCH' and position['preserve_existing_target_identity']
    assert link['status']=='ADD' and link['desired']=={'job_code':'TEST'}
    assert link['key']['position']['category']=='other'
    assert s==original_s and t==original_t
    assert t['dictionaries']['positions']['rows'][0]['position_id']==900
    assert not any(r['table']=='positions' and r['operation']=='INSERT' for r in updated['records'])
    assert update_approved_positions(updated,s,t,c,approval())==updated
    assert all(r in updated['records'] for r in previous['records'] if r['table'] in ('job_positions_catalog','medical_specialties','medical_specialty_groups'))


def test_approved_target_must_exist_and_existing_wrong_family_is_not_rebound():
    s,t,c=fixture();t['dictionaries']['positions']['rows']=[]
    t['dictionaries']['position_job_catalog']['rows']=[]
    t['dictionaries']['position_aliases']['rows']=[]
    p=make_plan(s,t,c,approval())
    assert next(r for r in p['records'] if r['table']=='positions')['status']=='MANUAL'
    s,t,c=fixture();t['dictionaries']['positions']['rows'][0]['category']='other'
    t['dictionaries']['position_job_catalog']['rows'][0]['job_code']='DIFFERENT'
    p=make_plan(s,t,c,approval())
    assert next(r for r in p['records'] if r['table']=='position_job_catalog')['status']=='CONFLICT'


def category_change_approval():
    return {'position_category_decisions':[{'approval_id':'TEST-approved-technical','source_key':{'name':'TEST variant','category':'medical'},
        'existing_key':{'name':'TEST variant','category':'other'},'expected_target_position_id':900,
        'target_category':'technical','required_job_code':'TEST','require_existing_target':True,'preserve_existing_target_id':True}]}


def test_category_change_preserves_target_identity_old_category_and_existing_link():
    s,t,c=fixture();t['dictionaries']['positions']['rows'][0]['category']='other'
    before_s,before_t=deepcopy(s),deepcopy(t)
    p=make_plan(s,t,c,category_change_approval())
    pos=next(r for r in p['records'] if r['table']=='positions')
    link=next(r for r in p['records'] if r['table']=='position_job_catalog')
    assert pos['status']=='UPDATE' and pos['before']['category']=='other'
    assert pos['changes']['category']=={'before':'other','after':'technical','column_present':True}
    assert pos['match_key']['category']=='other' and pos['post_update_key']['category']=='technical'
    assert pos['target_identity_guard']['expected_target_position_id']==900
    assert 'position_id' not in pos['desired']
    assert link['status']=='MATCH' and link['before']=={'job_code':'TEST'}
    assert next(r for r in p['records'] if r['table']=='position_aliases')['status']=='MATCH'
    assert s==before_s and t==before_t
    assert not any(e['table'] in ('positions','position_job_catalog') for e in p['production_only_keep'])


def test_category_change_missing_link_is_insert_only_and_after_key_is_repeatable():
    s,t,c=fixture();t['dictionaries']['positions']['rows'][0]['category']='other'
    t['dictionaries']['position_job_catalog']['rows']=[]
    t['dictionaries']['position_aliases']['rows']=[]
    p=make_plan(s,t,c,category_change_approval())
    assert next(r for r in p['records'] if r['table']=='position_job_catalog')['operation']=='INSERT'
    # Simulate the approved state solely in memory. Existing target ID stays 900.
    pos=t['dictionaries']['positions']['rows'][0];pos['category']='technical'
    t['dictionaries']['position_job_catalog']['rows']=[{'position_id':900,'job_code':'TEST'}]
    p=make_plan(s,t,c,category_change_approval())
    assert next(r for r in p['records'] if r['table']=='positions')['status']=='MATCH'
    assert next(r for r in p['records'] if r['table']=='position_job_catalog')['status']=='MATCH'


def test_category_change_rejects_wrong_target_id_and_duplicate_before_after_identities():
    s,t,c=fixture();t['dictionaries']['positions']['rows'][0]['category']='other'
    t['dictionaries']['positions']['rows'][0]['position_id']=901
    t['dictionaries']['position_job_catalog']['rows']=[];t['dictionaries']['position_aliases']['rows']=[]
    assert next(r for r in make_plan(s,t,c,category_change_approval())['records'] if r['table']=='positions')['status']=='CONFLICT'
    s,t,c=fixture();t['dictionaries']['positions']['rows'][0]['category']='other'
    t['dictionaries']['positions']['rows'].append({**t['dictionaries']['positions']['rows'][0],'position_id':901,'category':'technical'})
    assert next(r for r in make_plan(s,t,c,category_change_approval())['records'] if r['table']=='positions')['status']=='MANUAL'


def test_imported_legacy_confirmed_is_not_promoted_and_target_human_review_is_preserved():
    s,t,c=fixture()
    for collection in (s,t):
        collection['dictionaries']['positions']['rows'][0].update(name_kk='TEST KK',document_possessive_kk='TEST KK form')
    s['dictionaries']['positions']['rows'][0].update(translation_status='confirmed',document_form_status='confirmed')
    t['policy_receipt']='posdir001:forms-needs-review:v2'
    p=make_plan(s,t,c)
    pos=next(r for r in p['records'] if r['table']=='positions')
    assert pos['desired']['translation_status']==pos['desired']['document_form_status']=='needs_review'
    assert pos['status']=='MATCH'
    t['dictionaries']['positions']['rows'][0].update(translation_status='confirmed',document_form_status='confirmed')
    pos=next(r for r in make_plan(s,t,c)['records'] if r['table']=='positions')
    assert pos['status']=='MATCH' and pos['desired']['translation_status']=='confirmed'
    s['dictionaries']['positions']['rows'][0]['document_nominative_ru']='TEST changed RU form'
    pos=next(r for r in make_plan(s,t,c)['records'] if r['table']=='positions')
    assert pos['status']=='CONFLICT' and pos['desired']['document_form_status']=='needs_review'


def test_replacement_of_unreviewed_migration_text_needs_policy_receipt():
    s,t,c=fixture();s['dictionaries']['positions']['rows'][0]['name_kk']='TEST approved source text'
    t['dictionaries']['positions']['rows'][0]['name_kk']='TEST automatic old text'
    assert next(r for r in make_plan(s,t,c)['records'] if r['table']=='positions')['status']=='CONFLICT'
    t['policy_receipt']='posdir001:forms-needs-review:v2'
    pos=next(r for r in make_plan(s,t,c)['records'] if r['table']=='positions')
    assert pos['status']=='UPDATE' and pos['desired']['translation_status']=='needs_review'
    s['dictionaries']['positions']['rows'][0]['name_kk']=None
    assert next(r for r in make_plan(s,t,c)['records'] if r['table']=='positions')['status']=='CONFLICT'
