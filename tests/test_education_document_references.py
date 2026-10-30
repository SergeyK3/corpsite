"""Run exclusively on a disposable synthetic PostgreSQL database."""
from uuid import uuid4
import pytest
from sqlalchemy import text
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.db.engine import engine
from app.db.education_document_references_migration import upgrade,LEVELS
from app.services.education_document_references_service import save_value,list_values,selection_value

@pytest.fixture(scope='module',autouse=True)
def migrated():
    assert engine.url.database.startswith('corpsite_education_refs_') and engine.url.database.endswith('_test')
    import ast
    from pathlib import Path
    source=ast.parse(Path('alembic/versions/d9e8f71a2b05_add_employee_documents_phase_1a.py').read_text(encoding='utf-8'))
    with engine.begin() as c:
        for node in ast.walk(source):
            if isinstance(node,ast.FunctionDef) and node.name=='upgrade':
                for call in ast.walk(node):
                    if isinstance(call,ast.Call) and isinstance(call.func,ast.Attribute) and call.func.attr=='execute' and call.args and isinstance(call.args[0],ast.Constant):
                        sql=call.args[0].value
                        if sql.strip().startswith('INSERT INTO public.'):
                            c.execute(text(sql.split('ON CONFLICT')[0]+' ON CONFLICT DO NOTHING'))
        c.execute(text("UPDATE document_types SET tracks_hours=true WHERE code IN ('CONTINUING_EDUCATION','CONFERENCE_PARTICIPATION','MASTERCLASS_PARTICIPATION','SEMINAR_PARTICIPATION')"))
        protected=['person_education','employee_documents','education_program_kinds','education_program_kind_audit','document_types','personnel_order_template_versions','personnel_orders','personnel_order_items']
        def snapshot():return {t:list(c.execute(text(f'SELECT to_jsonb(t)::text FROM {t} t ORDER BY to_jsonb(t)::text')).scalars()) for t in protected}
        before=snapshot()
        legacy=list(c.execute(text('SELECT document_kind_id,code,name,is_active,sort_order FROM document_kinds ORDER BY code')))
        upgrade(c)
        assert snapshot()==before
        assert list(c.execute(text("SELECT document_kind_id,code,name,is_active,sort_order FROM document_kinds WHERE code<>'SCHOOL_ATTESTATE' ORDER BY code")))==[r for r in legacy if r.code!='SCHOOL_ATTESTATE']

def test_migration_preserves_all_existing_data_and_seed_names():
    import hashlib
    def fingerprint(conn):
        tables=['person_education','person_training','persons','employees','personnel_record_metadata','personnel_record_events','employee_documents','document_types','education_program_kinds','education_program_kind_audit','personnel_order_templates','personnel_order_template_versions','personnel_orders','personnel_order_items','personnel_order_template_applications']
        result={table:hashlib.sha256('\n'.join(conn.execute(text(f'SELECT to_jsonb(t)::text FROM {table} t ORDER BY to_jsonb(t)::text')).scalars()).encode()).hexdigest() for table in tables}
        result['legacy_document_kinds']=hashlib.sha256('\n'.join(conn.execute(text("SELECT jsonb_build_array(document_kind_id,code,name,is_active,sort_order)::text FROM document_kinds WHERE code<>'SCHOOL_ATTESTATE' ORDER BY code")).scalars()).encode()).hexdigest()
        return result
    with engine.begin() as c:
        before=fingerprint(c);upgrade(c);assert fingerprint(c)==before
        rows=c.execute(text('SELECT code,name_ru,name_kk,description_ru,description_kk,sort_order FROM education_levels WHERE code=ANY(:codes) ORDER BY sort_order'),{'codes':[r[0] for r in LEVELS]}).all()
        assert [tuple(r) for r in rows]==list(LEVELS)
        assert c.execute(text("SELECT name FROM document_kinds WHERE code='ATTESTATION'")).scalar_one()=='Свидетельство'
        assert c.execute(text("SELECT name FROM document_kinds WHERE code='SCHOOL_ATTESTATE'")).scalar_one()=='Аттестат'

def test_selection_empty_is_not_no_education_and_never_contains_notes():
    assert selection_value('levels',None,'ru')=={'code':None,'name':None}
    assert selection_value('levels','','kk')=={'code':None,'name':None}
    assert selection_value('levels','NO_EDUCATION','ru')['name']=='Без образования'
    for code,ru,kk,*_ in LEVELS:
        assert selection_value('levels',code,'ru')==dict(code=code,name=ru)
        assert selection_value('levels',code,'kk')==dict(code=code,name=kk)

@pytest.mark.parametrize('kind',['levels','document-kinds'])
def test_crud_search_revision_deactivation_and_idempotence(kind):
    code='TEST_'+uuid4().hex[:8].upper()
    created=save_value(kind,code=code,name_ru='Синтетическое значение',name_kk='Синтетикалық мән',sort_order=-10,actor_user_id=25)
    assert list_values(kind,q='СИНТЕТИКАЛЫҚ')['items'][0]['code']==code
    assert list_values(kind,q='синтетическое')['items'][0]['code']==code
    assert created['usage_count']==0
    edited=save_value(kind,code=code,name_ru='Изменено',name_kk='Өзгертілді',sort_order=99,is_active=False,expected_revision=1,actor_user_id=25)
    assert edited['revision']==2 and not edited['is_active']
    assert list_values(kind,q=code,state='active')['total']==0
    assert list_values(kind,q=code,state='inactive')['total']==1
    with pytest.raises(HTTPException) as exc:save_value(kind,code=code,expected_revision=1,actor_user_id=25)
    assert exc.value.status_code==409
    with pytest.raises(HTTPException):selection_value(kind,code,'ru')
    with engine.begin() as c:upgrade(c)
    assert list_values(kind,q=code)['items'][0]['name_ru']=='Изменено'
    active=save_value(kind,code=code,is_active=True,expected_revision=2,actor_user_id=25)
    assert active['name_ru']=='Изменено'
    if kind=='document-kinds':assert active['name']==active['name_ru']

def test_used_document_can_be_read_and_corrected_after_kind_deactivation():
    from app.services.employee_documents_service import create_employee_document,update_employee_document,list_document_kinds,EmployeeDocumentValidationError
    code='USED_'+uuid4().hex[:8].upper()
    kind=save_value('document-kinds',code=code,name_ru='Синтетическое свидетельство',name_kk='Синтетикалық куәлік',actor_user_id=25)
    with engine.connect() as c:
        employee=c.execute(text('SELECT min(employee_id) FROM employees')).scalar_one()
        type_id=c.execute(text('SELECT document_type_id FROM document_types WHERE is_active AND NOT requires_medical_specialty AND NOT tracks_hours AND NOT has_valid_until LIMIT 1')).scalar_one()
    doc=create_employee_document(employee_id=employee,document_type_id=type_id,document_kind_id=kind['document_kind_id'],title='SYNTHETIC reference compatibility',created_by=25)
    used=list_values('document-kinds',q=code)['items'][0];assert used['usage_count']==1
    with engine.connect() as c:before=c.execute(text('SELECT to_jsonb(t)::text FROM employee_documents t WHERE document_id=:id'),{'id':doc['document_id']}).scalar_one()
    save_value('document-kinds',code=code,is_active=False,expected_revision=1,actor_user_id=25)
    with engine.connect() as c:assert c.execute(text('SELECT to_jsonb(t)::text FROM employee_documents t WHERE document_id=:id'),{'id':doc['document_id']}).scalar_one()==before
    assert any(r['code']==code for r in list_document_kinds(is_active=False)['items'])
    assert all(r['code']!=code for r in list_document_kinds(is_active=True)['items'])
    corrected=update_employee_document(doc['document_id'],comment='SYNTHETIC correction')
    assert corrected['document_kind_id']==kind['document_kind_id']
    with pytest.raises(EmployeeDocumentValidationError):create_employee_document(employee_id=employee,document_type_id=type_id,document_kind_id=kind['document_kind_id'],title='SYNTHETIC forbidden',created_by=25)

def test_used_level_count_and_safe_deactivation():
    from tests.ppr.conftest import insert_person
    code='LEVEL_'+uuid4().hex[:8].upper()
    save_value('levels',code=code,name_ru='Синтетический уровень',name_kk='Синтетикалық деңгей',actor_user_id=25)
    with engine.begin() as c:
        p=insert_person(c,full_name='SYNTHETIC level usage')
        c.execute(text("INSERT INTO person_education(person_id,education_kind,metadata) VALUES(:p,'basic',jsonb_build_object('education_level_code',:code))"),dict(p=p,code=code))
        before=c.execute(text('SELECT to_jsonb(t)::text FROM person_education t WHERE person_id=:p'),{'p':p}).scalar_one()
    assert list_values('levels',q=code)['items'][0]['usage_count']==1
    save_value('levels',code=code,is_active=False,expected_revision=1,actor_user_id=25)
    with engine.connect() as c:assert c.execute(text('SELECT to_jsonb(t)::text FROM person_education t WHERE person_id=:p'),{'p':p}).scalar_one()==before

def test_api_authorization_legacy_response_and_validation():
    from app.main import app
    from app.auth import get_current_user
    from app.services.tasks_service import SYSTEM_ADMIN_ROLE_ID
    old=app.dependency_overrides.copy()
    try:
        app.dependency_overrides[get_current_user]=lambda:dict(user_id=25,role_id=SYSTEM_ADMIN_ROLE_ID)
        with TestClient(app) as client:
            response=client.get('/directory/document-kinds?is_active=false');assert response.status_code==200,response.text
            assert set(response.json()['items'][0])=={'document_kind_id','code','name','is_active','sort_order'}
            for path in ['/api/ppr/education-levels','/api/ppr/document-kinds']:
                assert client.get(path).json()['can_manage']
                code='API_'+uuid4().hex[:8].upper()
                assert client.post(path,json=dict(code=code,name_ru='Тест',name_kk='Сынақ')).status_code==201
                assert client.patch(path+'/'+code,json=dict(expected_revision=1,sort_order=123)).status_code==200
                assert client.patch(path+'/'+code,json=dict(expected_revision=2,is_active=None)).status_code==422
                assert client.patch(path+'/'+code,json=dict(expected_revision=2,code='NEW')).status_code==422
                assert client.delete(path+'/'+code).status_code==405
                assert client.post(path,json=dict(code='EMPTY',name_ru=' ',name_kk=' ')).status_code==422
            assert client.patch('/api/ppr/education-levels/BASIC_SECONDARY',json=dict(expected_revision=1,description_ru='')).status_code==422
            app.dependency_overrides[get_current_user]=lambda:dict(user_id=99999999,role_id=-123)
            assert not client.get('/api/ppr/education-levels').json()['can_manage']
            assert client.post('/api/ppr/document-kinds',json=dict(code='DENIED',name_ru='Тест',name_kk='Сынақ')).status_code==403
    finally:app.dependency_overrides.clear();app.dependency_overrides.update(old)
