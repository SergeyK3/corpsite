"""Real PostgreSQL, rollback-only coverage in the separate local corpsite_test."""
import copy
import json
import os
from pathlib import Path
import pytest
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from scripts import transfer_personnel_templates as transfer

ROOT=Path(__file__).resolve().parents[1]
BUNDLE=ROOT/'reference-data/personnel-templates/transfer-181e750e.json'
URL=os.environ.get('TEST_DATABASE_URL','')
pytestmark=pytest.mark.skipif(not URL or make_url(URL).database!='corpsite_test',reason='requires separate local corpsite_test')

@pytest.fixture
def bundle():return json.loads(BUNDLE.read_text(encoding='utf8'))

@pytest.fixture
def db():
    url=make_url(URL);assert url.host in ('localhost','127.0.0.1') and url.database=='corpsite_test'
    engine=create_engine(url,hide_parameters=True)
    with engine.connect() as conn:
        tx=conn.begin()
        # Isolate this fixture from independently seeded default identities.
        conn.execute(text("UPDATE personnel_order_templates SET is_default=FALSE,name_ru='Unrelated test identity '||template_id,name_kk='Unrelated KK '||template_id WHERE item_type_code IN ('SUPPLEMENTARY_PAY','CONCURRENT_DUTY_START','CONCURRENT_DUTY_END')"))
        actor=conn.execute(text("SELECT login FROM users WHERE is_active AND login IS NOT NULL AND btrim(login)<>'' ORDER BY user_id LIMIT 1")).scalar_one()
        try:yield conn,actor
        finally:tx.rollback()
    engine.dispose()

def paths(tmp_path):return tmp_path/'backup.json',tmp_path/'receipt.json'

def insert_identity(conn,e,*,names=None):
    i={**e['identity'],**(names or {})}
    return conn.execute(text('INSERT INTO personnel_order_templates(item_type_code,name_ru,name_kk,is_default) VALUES(:item_type_code,:name_ru,:name_kk,:is_default) RETURNING template_id'),i).scalar_one()

def insert_version(conn,tid,e,number,status,extra=''):
    values={**e['version']['texts']};values['title_ru']+=extra
    return conn.execute(text('''INSERT INTO personnel_order_template_versions(template_id,item_type_code,version_number,status,
      title_ru,title_kk,preamble_ru,preamble_kk,body_template_ru,body_template_kk,basis_template_ru,basis_template_kk,based_on_built_in)
      VALUES(:tid,:code,:number,:status,:title_ru,:title_kk,:preamble_ru,:preamble_kk,:body_template_ru,:body_template_kk,
      :basis_template_ru,:basis_template_kk,:built_in) RETURNING template_version_id'''),{**values,'tid':tid,'code':e['identity']['item_type_code'],'number':number,'status':status,'built_in':e['version']['based_on_built_in']}).scalar_one()

def resign(bundle):
    for e in bundle['entries']:e['sha256']=transfer.digest({k:v for k,v in e.items() if k!='sha256'})
    bundle['sha256']=transfer.digest({k:v for k,v in bundle.items() if k!='sha256'})

def test_export_contains_only_templates_and_current_variable_bindings(bundle):
    transfer.validate_bundle(bundle)
    assert len(bundle['entries'])==6
    assert [e['version']['status'] for e in bundle['entries']].count('PUBLISHED')==5
    for entry in bundle['entries']:
        assert not {'orders','employees','assignments','salary','created_by_user_id'}&entry.keys()
        assert entry['contract']['field_bindings']['body_template_ru']
        assert set(entry['version']['texts'])==set(transfer.FIELDS)

def test_every_transferred_version_has_compatible_ru_kk_preview(bundle):
    from app.services.personnel_order_template_draft_service import preview_draft
    for entry in bundle['entries']:
        preview=preview_draft(entry['identity']['item_type_code'],entry['version']['texts'])
        assert set(preview)=={'ru','kk'}
        for lang in ('ru','kk'):
            assert all(preview[lang][field].strip() for field in ('title','preamble','body','basis'))
            assert '{{' not in preview[lang]['body'] and '}}' not in preview[lang]['basis']

def test_server_snapshot_plan_uses_code_names_content_and_not_local_ids(bundle):
    state={'templates':[{'template_id':4,'item_type_code':'TERMINATION','name_ru':'О расторжении трудового договора',
                        'name_kk':'Еңбек шартын бұзу туралы','is_default':True}],
           'versions':[],'references':{},'schema':{'columns':{'personnel_order_template_versions':['template_id']}}}
    plan=transfer.prepare_plan(bundle,state)
    assert plan['ready'] and [r['action'] for r in plan['rows']]==['CREATE']*6
    # Server ID 4 is TERMINATION, and must never become the local simple allowance.
    assert next(t for t in state['templates'] if t['template_id']==4)['item_type_code']=='TERMINATION'
    assert all(r['server_template_id'] is None for r in plan['rows'])

def test_create_six_distinct_identities_bilingual_status_repeat_and_restore(db,bundle,tmp_path):
    conn,actor=db;before=transfer.snapshot(conn)
    plan=transfer.prepare_plan(bundle,before);assert plan['ready'],plan['ambiguities']
    backup_path,receipt_path=paths(tmp_path)
    receipt=transfer.apply_plan(conn,bundle,plan,actor,backup_path,receipt_path)
    after=transfer.snapshot(conn)
    assert len(receipt['created_templates'])==6 and len(set(receipt['created_templates']))==6
    assert len(receipt['created_versions'])==6
    for e,change in zip(bundle['entries'],receipt['changes']):
        row=next(v for v in after['versions'] if v['template_version_id']==change['server_version_id'])
        assert transfer.version_equal(row,e) and row['status']==e['version']['status']
    repeat=transfer.prepare_plan(bundle,after)
    assert repeat['ready'] and all(r['action']=='NO_CHANGE' for r in repeat['rows'])
    second=transfer.apply_plan(conn,bundle,repeat,actor,tmp_path/'backup2.json',tmp_path/'receipt2.json')
    assert not second['created_templates'] and not second['created_versions']
    assert transfer.snapshot(conn)==after
    backup=json.loads(backup_path.read_text(encoding='utf8'))
    assert transfer.rollback(conn,backup,receipt)['restore_ready']
    transfer.rollback(conn,backup,receipt,apply=True)
    assert transfer.snapshot(conn)==before

def test_update_keeps_used_published_history_and_pending_draft(db,bundle,tmp_path):
    conn,actor=db;e=bundle['entries'][0]
    tid=insert_identity(conn,e);old=insert_version(conn,tid,e,7,'PUBLISHED',' OLD')
    pending=insert_version(conn,tid,e,8,'DRAFT',' PENDING')
    uid=conn.execute(text('SELECT user_id FROM users WHERE login=:l'),{'l':actor}).scalar_one()
    oid=conn.execute(text("INSERT INTO personnel_orders(order_type_code,status,source_mode,created_by,selected_template_version_id) VALUES('SUPPLEMENTARY_PAY','DRAFT','MANUAL',:u,:v) RETURNING order_id"),{'u':uid,'v':old}).scalar_one()
    conn.execute(text("INSERT INTO personnel_order_editorial_blocks(order_id,locale,block_type,generated_text) VALUES(:o,'ru','title','UNCHANGED HISTORICAL ORDER TEXT')"),{'o':oid})
    employee=conn.execute(text('SELECT employee_id FROM employees ORDER BY employee_id LIMIT 1')).scalar_one()
    item=conn.execute(text("INSERT INTO personnel_order_items(order_id,item_number,item_type_code,employee_id,effective_date,item_status,payload) VALUES(:o,1,'SUPPLEMENTARY_PAY',:e,'2026-02-02','ACTIVE','{}'::jsonb) RETURNING item_id"),{'o':oid,'e':employee}).scalar_one()
    conn.execute(text("INSERT INTO personnel_order_template_applications(order_id,order_item_id,template_version_id,applied_by_user_id,template_snapshot,rendered_snapshot,previous_editorial_blocks) VALUES(:o,:i,:v,:u,CAST(:t AS jsonb),CAST(:r AS jsonb),'[]'::jsonb)"),{'o':oid,'i':item,'v':old,'u':uid,'t':json.dumps(e['version']['texts']),'r':json.dumps({'ru':'UNCHANGED HISTORICAL ORDER TEXT','kk':'UNCHANGED KK'})})
    original_order=dict(conn.execute(text('SELECT * FROM personnel_orders WHERE order_id=:id'),{'id':oid}).mappings().one())
    original_application=dict(conn.execute(text('SELECT * FROM personnel_order_template_applications WHERE order_id=:id'),{'id':oid}).mappings().one())
    old_row=dict(conn.execute(text('SELECT * FROM personnel_order_template_versions WHERE template_version_id=:id'),{'id':old}).mappings().one())
    plan=transfer.prepare_plan(bundle,transfer.snapshot(conn));assert plan['ready'],plan['ambiguities']
    row=next(r for r in plan['rows'] if r['key']=='4')
    assert row['action']=='UPDATE' and row['new_version_number']==9 and row['archive_version_ids']==[old]
    bp,rp=paths(tmp_path);receipt=transfer.apply_plan(conn,bundle,plan,actor,bp,rp)
    now=dict(conn.execute(text('SELECT * FROM personnel_order_template_versions WHERE template_version_id=:id'),{'id':old}).mappings().one())
    assert now['status']=='ARCHIVED'
    assert all(now[k]==v for k,v in old_row.items() if k not in ('status','updated_at'))
    assert conn.execute(text('SELECT status FROM personnel_order_template_versions WHERE template_version_id=:id'),{'id':pending}).scalar_one()=='DRAFT'
    assert dict(conn.execute(text('SELECT * FROM personnel_orders WHERE order_id=:id'),{'id':oid}).mappings().one())==original_order
    assert dict(conn.execute(text('SELECT * FROM personnel_order_template_applications WHERE order_id=:id'),{'id':oid}).mappings().one())==original_application
    assert conn.execute(text('SELECT generated_text FROM personnel_order_editorial_blocks WHERE order_id=:id'),{'id':oid}).scalar_one()=='UNCHANGED HISTORICAL ORDER TEXT'
    transfer.rollback(conn,json.loads(bp.read_text(encoding='utf8')),receipt,apply=True)
    restored=dict(conn.execute(text('SELECT * FROM personnel_order_template_versions WHERE template_version_id=:id'),{'id':old}).mappings().one())
    assert restored==old_row

def test_existing_draft_is_archived_not_overwritten(db,bundle,tmp_path):
    conn,actor=db;e=next(e for e in bundle['entries'] if e['key']=='24')
    tid=insert_identity(conn,e);old=insert_version(conn,tid,e,3,'DRAFT',' OLD')
    before=dict(conn.execute(text('SELECT * FROM personnel_order_template_versions WHERE template_version_id=:id'),{'id':old}).mappings().one())
    plan=transfer.prepare_plan(bundle,transfer.snapshot(conn));bp,rp=paths(tmp_path)
    receipt=transfer.apply_plan(conn,bundle,plan,actor,bp,rp)
    row=dict(conn.execute(text('SELECT * FROM personnel_order_template_versions WHERE template_version_id=:id'),{'id':old}).mappings().one())
    assert row['status']=='ARCHIVED' and all(row[k]==v for k,v in before.items() if k not in ('status','updated_at'))
    imported=next(r for r in receipt['changes'] if r['key']=='24')
    assert imported['status']=='DRAFT'

def test_ambiguous_identity_requires_explicit_evidence_and_no_writes(db,bundle):
    conn,_=db;e=next(e for e in bundle['entries'] if e['key']=='28')
    a=insert_identity(conn,e);b=insert_identity(conn,e)
    state=transfer.snapshot(conn);plan=transfer.prepare_plan(bundle,state)
    assert not plan['ready'] and any(len(x['candidates'])==2 for x in plan['ambiguities'])
    t=next(t for t in state['templates'] if t['template_id']==b)
    mapping={'28':{'server_template_id':b,'candidate_sha256':transfer.digest(transfer.candidate(t,state['versions']))}}
    reviewed=transfer.prepare_plan(bundle,state,mapping)
    assert reviewed['ready'] and next(r for r in reviewed['rows'] if r['key']=='28')['server_template_id']==b
    mapping['28']['candidate_sha256']='stale'
    with pytest.raises(transfer.TransferError,match='stale'):transfer.prepare_plan(bundle,state,mapping)

def test_reviewed_ambiguous_match_import_and_repeat(db,bundle,tmp_path):
    conn,actor=db;e=next(e for e in bundle['entries'] if e['key']=='28')
    first=insert_identity(conn,e);second=insert_identity(conn,e)
    state=transfer.snapshot(conn)
    target=next(t for t in state['templates'] if t['template_id']==second)
    mapping={e['key']:{'server_template_id':second,'candidate_sha256':transfer.digest(transfer.candidate(target,state['versions']))}}
    plan=transfer.prepare_plan(bundle,state,mapping)
    bp,rp=paths(tmp_path);receipt=transfer.apply_plan(conn,bundle,plan,actor,bp,rp)
    assert not any(v['template_id']==first for v in transfer.snapshot(conn)['versions'])
    repeated=transfer.prepare_plan(bundle,transfer.snapshot(conn),receipt['repeat_mapping'])
    assert repeated['ready'] and all(r['action']=='NO_CHANGE' for r in repeated['rows'])
    again=transfer.apply_plan(conn,bundle,repeated,actor,tmp_path/'backup2.json',tmp_path/'receipt2.json')
    assert not again['created_versions'] and not again['created_templates']


def test_atomic_rollback_on_receipt_failure_and_stale_plan(db,bundle,tmp_path,monkeypatch):
    conn,actor=db;before=transfer.snapshot(conn);plan=transfer.prepare_plan(bundle,before);bp,rp=paths(tmp_path)
    original=transfer.write_json
    def fail(path,value):
        if Path(path)==rp:raise OSError('receipt unavailable')
        original(path,value)
    monkeypatch.setattr(transfer,'write_json',fail)
    with pytest.raises(OSError),conn.begin_nested():transfer.apply_plan(conn,bundle,plan,actor,bp,rp)
    assert transfer.snapshot(conn)==before
    conn.execute(text("UPDATE personnel_order_templates SET name_ru=name_ru||' changed' WHERE template_id=(SELECT min(template_id) FROM personnel_order_templates)"))
    with pytest.raises(transfer.TransferError,match='changed since preview'):
        transfer.apply_plan(conn,bundle,plan,actor,tmp_path/'backup3.json',tmp_path/'receipt3.json')

def test_restore_refuses_versions_used_after_import(db,bundle,tmp_path):
    conn,actor=db;bp,rp=paths(tmp_path);plan=transfer.prepare_plan(bundle,transfer.snapshot(conn))
    receipt=transfer.apply_plan(conn,bundle,plan,actor,bp,rp)
    change=receipt['changes'][0]
    uid=conn.execute(text('SELECT user_id FROM users WHERE login=:l'),{'l':actor}).scalar_one()
    conn.execute(text("INSERT INTO personnel_orders(order_type_code,status,source_mode,created_by,selected_template_version_id) VALUES('SUPPLEMENTARY_PAY','DRAFT','MANUAL',:u,:v)"),{'u':uid,'v':change['server_version_id']})
    with pytest.raises(transfer.TransferError,match='already used'):
        transfer.rollback(conn,json.loads(bp.read_text(encoding='utf8')),receipt,apply=True)

def test_podup001_migration_preserves_rows_and_enforces_normalized_number_date(db,monkeypatch):
    import importlib.util
    from uuid import uuid4
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    conn,actor=db
    path=ROOT/'alembic/versions/podup001_active_order_header_uniqueness.py'
    spec=importlib.util.spec_from_file_location('transfer_podup001',path)
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    monkeypatch.setattr(migration,'op',Operations(MigrationContext.configure(conn)))
    existing=[dict(row) for row in conn.execute(text('SELECT * FROM personnel_orders ORDER BY order_id')).mappings()]
    migration.upgrade()
    assert [dict(row) for row in conn.execute(text('SELECT * FROM personnel_orders ORDER BY order_id')).mappings()]==existing
    uid=conn.execute(text('SELECT user_id FROM users WHERE login=:l'),{'l':actor}).scalar_one()
    number='TRANSFER-CHECK-'+uuid4().hex
    for day in ('2026-02-02','2026-02-03'):
        conn.execute(text("INSERT INTO personnel_orders(order_number,order_date,order_type_code,status,source_mode,created_by) VALUES(:n,CAST(:d AS date),'SUPPLEMENTARY_PAY','DRAFT','MANUAL',:u)"),{'n':number,'d':day,'u':uid})
    with pytest.raises(IntegrityError),conn.begin_nested():
        conn.execute(text("INSERT INTO personnel_orders(order_number,order_date,order_type_code,status,source_mode,created_by) VALUES(:n,'2026-02-02','SUPPLEMENTARY_PAY','DRAFT','MANUAL',:u)"),{'n':' '+number.lower().replace('-','—')+' ','u':uid})
    with pytest.raises(RuntimeError,match='without changing retained orders'):migration.downgrade()

@pytest.mark.parametrize('mutation',['unknown_variable','unknown_cyrillic','checksum','foreign_table','contract'])
def test_export_rejects_tampering_and_incompatible_variables(bundle,mutation):
    bundle=copy.deepcopy(bundle)
    if mutation=='unknown_variable':bundle['entries'][0]['version']['texts']['body_template_ru']='{{unsupported.variable}}';resign(bundle)
    elif mutation=='unknown_cyrillic':bundle['entries'][0]['version']['texts']['body_template_ru']='{{неизвестная.переменная}}';resign(bundle)
    elif mutation=='checksum':bundle['entries'][0]['identity']['name_ru']+='tampered'
    elif mutation=='foreign_table':bundle['orders']=[];resign(bundle)
    else:bundle['entries'][0]['contract']['allowed_variables']=['wrong'];resign(bundle)
    with pytest.raises(ValueError):transfer.validate_bundle(bundle)
