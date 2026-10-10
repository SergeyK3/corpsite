"""PostgreSQL rollback-only coverage of independent templates and exact-version application."""
import os
from contextlib import nullcontext
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from app.services import personnel_order_template_draft_service as templates
from app.services import personnel_order_template_application_service as applications
from app.services import personnel_order_manual_draft_service as manual
from app.services.personnel_order_template_specs import get_personnel_order_template_spec
from app.services.personnel_orders_query_service import PersonnelOrderValidationError

URL = os.environ.get('TEST_DATABASE_URL', '')
pytestmark = pytest.mark.skipif(not URL or make_url(URL).host not in ('localhost','127.0.0.1') or make_url(URL).database != 'corpsite_test', reason='requires local migrated corpsite_test')


@pytest.mark.parametrize('percent',[25,50])
def test_simple_supplementary_pay_saves_number_and_applies_exact_version(database,percent):
    from app.services.personnel_order_supplementary_pay_contract import BODY_RU,BODY_KK
    from app.services.personnel_order_service_area_contract import SAMPLE_RECIPIENT
    actor=database.execute(text('SELECT user_id FROM users ORDER BY user_id LIMIT 1')).scalar_one()
    employee=database.execute(text('SELECT employee_id FROM employees ORDER BY employee_id LIMIT 1')).scalar_one()
    draft=templates.copy_template('SUPPLEMENTARY_PAY',None,'TEST simple pay','TEST simple KK',actor,None,base_source='INITIAL')
    txt={field:draft[field] for field in templates.TEXT_FIELDS};txt.update(body_template_ru=BODY_RU,body_template_kk=BODY_KK)
    draft=templates.save_draft('SUPPLEMENTARY_PAY',draft['revision'],txt,actor,draft['template_id'])
    published=templates.publish_draft('SUPPLEMENTARY_PAY',draft['revision'],actor,draft['template_id'])
    allowance={'percent':str(percent),'employee_dative_ru':'Касымовой Раушан Тастемировне','employee_dative_kk':'Раушан Тастемировна Касымоваға','basis_ru':'Служебная записка','basis_kk':'Қызметтік хат','rate':1,'basis_type':'FOREIGN_SALARY'}
    recipient=dict(SAMPLE_RECIPIENT)
    assignments=database.execute(text("SELECT pa.assignment_id FROM person_assignments pa JOIN employees e ON e.person_id=pa.person_id WHERE e.employee_id=:id AND pa.active_flag AND pa.lifecycle_status='active' AND pa.start_date<=CURRENT_DATE AND (pa.end_date IS NULL OR pa.end_date>=CURRENT_DATE)"),{'id':employee}).scalars().all()
    if assignments:recipient['assignment_id']=assignments[0]
    order=manual.create_manual_draft(created_by=actor,template_version_id=published['template_version_id'],order_number='TEST-simple-'+uuid4().hex,order_date=date(2026,10,10),source_title=published['title_ru'],source_title_locale='ru',item_type_code='SUPPLEMENTARY_PAY',employee_id=employee,effective_date=date(2026,2,2),item_payload={'allowance':allowance,'allowance_recipient':recipient})
    payload=database.execute(text('SELECT payload FROM personnel_order_items WHERE order_id=:id'),{'id':order['order_id']}).scalar_one()
    assert payload['allowance']['percent']==percent and type(payload['allowance']['percent']) is int
    assert payload['allowance']['basis_type']=='RECIPIENT_BASE_SALARY'
    assert not {'rate','total_rate','replacement','concurrent'} & payload.keys()
    assert 'rate' not in payload['allowance']
    preview=applications.preview_template_application(order['order_id'])
    assert preview['template']['template_version_id']==published['template_version_id'] and not preview['items'][0]['blocked']
    assert f'{percent}% от собственного должностного оклада' in preview['items'][0]['proposed']['body_ru']

class TransactionEngine:
    def __init__(self, conn): self.conn = conn
    def begin(self): return nullcontext(self.conn)
    def connect(self): return nullcontext(self.conn)


def test_catalog_keeps_all_independent_identities_inside_the_order_type(database):
    from app.services.personnel_order_template_catalog_service import list_personnel_order_template_catalog
    actor=database.execute(text('SELECT user_id FROM users ORDER BY user_id LIMIT 1')).scalar_one()
    code='CONCURRENT_DUTY_START'
    first=templates.copy_template(code,None,'TEST simple rate','TEST ставка KK',actor,None,base_source='INITIAL')
    second=templates.copy_template(code,None,'TEST simple percentage','TEST доплата KK',actor,None,base_source='INITIAL')
    archived=templates.copy_template(code,None,'TEST archived','TEST архив KK',actor,None,base_source='INITIAL')
    templates.remove_template(code,archived['template_id'],archived['name_ru'],archived['name_kk'],actor,archive=True)
    before=[dict(r) for r in database.execute(text('SELECT * FROM personnel_order_template_versions ORDER BY template_version_id')).mappings()]
    group=next(row for row in list_personnel_order_template_catalog(include_saved_names=True) if row['type_code']==code)
    ids={row['template_id']:row for row in group['templates']}
    assert ids[first['template_id']]['name_ru']=='TEST simple rate'
    assert ids[second['template_id']]['name_ru']=='TEST simple percentage'
    assert ids[second['template_id']]['draft_version_id']==second['template_version_id']
    assert ids[second['template_id']]['draft_version_number']==second['version_number']
    assert archived['template_id'] not in ids
    assert [dict(r) for r in database.execute(text('SELECT * FROM personnel_order_template_versions ORDER BY template_version_id')).mappings()]==before


def test_delete_persisted_identity_without_versions_does_not_recreate_on_reads(database):
    from app.services.personnel_order_template_catalog_service import list_personnel_order_template_catalog
    code='LEAVE.ANNUAL.RECALL'
    actor=database.execute(text('SELECT user_id FROM users ORDER BY user_id LIMIT 1')).scalar_one()
    empty_id=database.execute(text("INSERT INTO personnel_order_templates(item_type_code,name_ru,name_kk) VALUES(:code,'TEST empty recall','TEST empty KK') RETURNING template_id"),{'code':code}).scalar_one()
    before={table:[dict(r) for r in database.execute(text(f'SELECT * FROM {table} ORDER BY 1')).mappings()] for table in ('personnel_order_template_versions','personnel_orders','personnel_order_template_applications')}
    assert templates.get_editor_base(code,empty_id)['source']=='INITIAL'
    assert templates.remove_template(code,empty_id,'TEST empty recall','TEST empty KK',actor)=={'template_id':empty_id,'action':'DELETED'}
    for _ in range(2):
        assert all(t['template_id']!=empty_id for t in templates.list_templates(code))
        group=next(r for r in list_personnel_order_template_catalog(include_saved_names=True) if r['type_code']==code)
        assert all(t['template_id']!=empty_id for t in group['templates'])
        with pytest.raises(templates.TemplateDraftError): templates.get_editor_base(code,empty_id)
    assert database.execute(text('SELECT 1 FROM personnel_order_templates WHERE template_id=:id'),{'id':empty_id}).first() is None
    for table,rows in before.items():
        assert [dict(r) for r in database.execute(text(f'SELECT * FROM {table} ORDER BY 1')).mappings()]==rows


@pytest.mark.parametrize('percent,filled',[(25,False),(50,False),(25,True),(50,True)])
def test_exact_optional_pay_version_creates_without_rates_and_preserves_structure(database,percent,filled):
    from app.services.personnel_order_replacement_contract import OPTIONAL_PAY_RU,OPTIONAL_PAY_KK,SAMPLE_CONCURRENT,SAMPLE_REPLACEMENT
    actor=database.execute(text('SELECT user_id FROM users ORDER BY user_id LIMIT 1')).scalar_one()
    employee=database.execute(text('SELECT employee_id FROM employees ORDER BY employee_id LIMIT 1')).scalar_one()
    code='CONCURRENT_DUTY_START'
    draft=templates.copy_template(code,None,'TEST optional pay','TEST optional pay KK',actor,None,base_source='INITIAL')
    values={field:draft[field] for field in templates.TEXT_FIELDS}
    values.update(body_template_ru=OPTIONAL_PAY_RU,body_template_kk=OPTIONAL_PAY_KK)
    draft=templates.save_draft(code,draft['revision'],values,actor,draft['template_id'])
    published=templates.publish_draft(code,draft['revision'],actor,draft['template_id'])
    c=dict(SAMPLE_CONCURRENT);c.pop('rate');c.pop('total_rate')
    if not filled:
        for key in ('position_ru','position_kk','org_unit_ru','org_unit_kk','position_genitive_ru','org_unit_genitive_ru'):c[key]=''
    order=manual.create_manual_draft(created_by=actor,template_version_id=published['template_version_id'],order_number='TEST-pay-'+uuid4().hex,order_date=date(2026,10,9),source_title='TEST optional pay',source_title_locale='ru',item_type_code=code,employee_id=employee,effective_date=date(2026,7,3),item_payload={'concurrent':c,'replacement':{**SAMPLE_REPLACEMENT,'allowance_percent':str(percent),'mode':'RATE'}})
    payload=database.execute(text('SELECT payload FROM personnel_order_items WHERE order_id=:id'),{'id':order['order_id']}).scalar_one()
    assert payload['replacement']['allowance_percent']==percent and payload['replacement']['mode']=='PAY'
    assert not {'rate','total_rate'} & payload['concurrent'].keys()
    preview=applications.preview_template_application(order['order_id'])
    assert preview['template']['template_version_id']==published['template_version_id'] and not preview['items'][0]['blocked']
    texts=preview['items'][0]['proposed']
    assert f'с доплатой в размере {percent}%' in texts['body_ru'] and f'{percent}% мөлшерінде' in texts['body_kk']
    assert 'ставк' not in texts['body_ru']+texts['body_kk']


@pytest.mark.parametrize('percent,term,worker',[(25,'NONE',False),(50,'NONE',True),(25,'DATE',False),(50,'DATE',True),(25,'UNTIL_RETURN',True),(50,'UNTIL_RETURN',True)])
def test_service_area_order_uses_own_salary_and_selected_assignment(database,percent,term,worker):
    from app.services.personnel_order_service_area_contract import BODY_RU,BODY_KK,SAMPLE_RECIPIENT
    from app.services.personnel_order_replacement_contract import SAMPLE_CONCURRENT,SAMPLE_REPLACEMENT
    actor=database.execute(text('SELECT user_id FROM users ORDER BY user_id LIMIT 1')).scalar_one()
    employee=database.execute(text('SELECT employee_id FROM employees ORDER BY employee_id LIMIT 1')).scalar_one()
    assignments=database.execute(text("SELECT pa.assignment_id FROM person_assignments pa JOIN employees e ON e.person_id=pa.person_id WHERE e.employee_id=:id AND pa.active_flag AND pa.lifecycle_status='active' AND pa.start_date<=CURRENT_DATE AND (pa.end_date IS NULL OR pa.end_date>=CURRENT_DATE)"),{'id':employee}).scalars().all()
    code='CONCURRENT_DUTY_START';draft=templates.copy_template(code,None,'TEST service area','TEST service area KK',actor,None,base_source='INITIAL')
    txt={field:draft[field] for field in templates.TEXT_FIELDS};txt.update(body_template_ru=BODY_RU,body_template_kk=BODY_KK)
    draft=templates.save_draft(code,draft['revision'],txt,actor,draft['template_id']);published=templates.publish_draft(code,draft['revision'],actor,draft['template_id'])
    replacement={**(SAMPLE_REPLACEMENT if worker else {}),'term_type':term,'allowance_percent':percent,'end_date':'2026-06-30'}
    recipient={**SAMPLE_RECIPIENT,**({'assignment_id':assignments[0]} if assignments else {})}
    order=manual.create_manual_draft(created_by=actor,template_version_id=published['template_version_id'],order_number='TEST-area-'+uuid4().hex,order_date=date(2026,10,9),source_title='TEST service area',source_title_locale='ru',item_type_code=code,employee_id=employee,effective_date=date(2026,6,15),item_payload={'concurrent':SAMPLE_CONCURRENT,'replacement':replacement,'allowance_recipient':recipient})
    payload=database.execute(text('SELECT payload FROM personnel_order_items WHERE order_id=:id'),{'id':order['order_id']}).scalar_one()
    assert payload['replacement']['allowance_basis_type']=='RECIPIENT_BASE_SALARY' and payload['replacement']['allowance_percent']==percent
    assert 'allowance_basis_ru' not in payload['replacement']
    assert ('end_date' in payload['replacement'])==(term=='DATE')
    assert payload['allowance_recipient']==recipient and 'rate' not in payload['concurrent']
    preview=applications.preview_template_application(order['order_id']);assert not preview['items'][0]['blocked']
    assert 'от собственного должностного оклада' in preview['items'][0]['proposed']['body_ru']


@pytest.mark.parametrize('position,expected',[('Менеджер','менеджеру'),('Неизвестный код','')])
def test_service_area_missing_client_dative_is_saved_and_renders_without_manual_confirmation(database,position,expected):
    from app.services.personnel_order_service_area_contract import BODY_RU,BODY_KK,SAMPLE_RECIPIENT
    from app.services.personnel_order_replacement_contract import SAMPLE_CONCURRENT
    actor=database.execute(text('SELECT user_id FROM users ORDER BY user_id LIMIT 1')).scalar_one()
    employee=database.execute(text('SELECT employee_id FROM employees ORDER BY employee_id LIMIT 1')).scalar_one()
    assignments=database.execute(text("SELECT pa.assignment_id FROM person_assignments pa JOIN employees e ON e.person_id=pa.person_id WHERE e.employee_id=:id AND pa.active_flag AND pa.lifecycle_status='active' AND pa.start_date<=CURRENT_DATE AND (pa.end_date IS NULL OR pa.end_date>=CURRENT_DATE)"),{'id':employee}).scalars().all()
    code='CONCURRENT_DUTY_START';draft=templates.copy_template(code,None,'TEST automatic recipient','TEST automatic recipient KK',actor,None,base_source='INITIAL')
    txt={field:draft[field] for field in templates.TEXT_FIELDS};txt.update(body_template_ru=BODY_RU,body_template_kk=BODY_KK)
    draft=templates.save_draft(code,draft['revision'],txt,actor,draft['template_id']);published=templates.publish_draft(code,draft['revision'],actor,draft['template_id'])
    recipient={**SAMPLE_RECIPIENT,'position_ru':position,**({'assignment_id':assignments[0]} if assignments else {})};recipient.pop('position_dative_ru')
    result=manual.create_manual_draft(created_by=actor,template_version_id=published['template_version_id'],order_number='TEST-auto-recipient-'+uuid4().hex,order_date=date(2026,10,9),source_title='TEST automatic recipient',source_title_locale='ru',item_type_code=code,employee_id=employee,effective_date=date(2026,6,15),item_payload={'concurrent':SAMPLE_CONCURRENT,'replacement':{'term_type':'NONE','allowance_percent':25},'allowance_recipient':recipient})
    payload=database.execute(text('SELECT payload FROM personnel_order_items WHERE order_id=:id'),{'id':result['order_id']}).scalar_one()
    assert payload['allowance_recipient']['position_dative_ru']==expected
    preview=applications.preview_template_application(result['order_id']);assert not preview['items'][0]['blocked']
    rendered=preview['items'][0]['proposed']['body_ru']
    assert ('менеджеру' in rendered)==bool(expected)
    if not expected:assert rendered.startswith(SAMPLE_CONCURRENT['employee_dative_ru']+', с ')
    assert '{{' not in rendered and 'Неизвестный' not in rendered


def test_rename_only_selected_template_and_delete_all_versions_preserving_copy(database):
    actor = database.execute(text('SELECT user_id FROM users ORDER BY user_id LIMIT 1')).scalar_one()
    code = 'SUPPLEMENTARY_PAY'
    parent = templates.copy_template(code, None, 'TEST parent', 'TEST parent KK', actor, None, base_source='INITIAL')
    sibling = templates.copy_template(code, None, 'TEST sibling', 'TEST sibling KK', actor, None, base_source='INITIAL')
    valid = {field: parent[field] for field in templates.TEXT_FIELDS}
    valid.update(basis_template_ru='Test evidence', basis_template_kk='Test evidence KK')
    parent = templates.save_draft(code, parent['revision'], valid, actor, parent['template_id'])
    v1 = templates.publish_draft(code, parent['revision'], actor, parent['template_id'])
    old = {field: v1[field] for field in templates.TEXT_FIELDS}
    changed = {**old, 'title_ru': 'TEST renamed RU', 'title_kk': 'TEST renamed KK'}
    v2 = templates.create_draft_from_working_copy(code, 'PUBLISHED', v1['template_version_id'], v1['revision'], changed, actor, parent['template_id'])
    changed['title_ru'] = 'TEST final RU'
    v2 = templates.save_draft(code, v2['revision'], changed, actor, parent['template_id'])
    current = next(t for t in templates.list_templates(code, published_only=True) if t['template_id'] == parent['template_id'])
    assert current['name_ru'] == 'TEST final RU' and current['name_kk'] == 'TEST renamed KK'
    assert current['title_ru'] == old['title_ru']
    assert templates.get_published(code, parent['template_id'])['template_version_id'] == v1['template_version_id']
    assert next(t for t in templates.list_templates(code) if t['template_id'] == sibling['template_id'])['name_ru'] == 'TEST sibling'
    child = templates.copy_template(code, v1['template_version_id'], 'TEST child', 'TEST child KK', actor, v1['revision'])
    result = templates.remove_template(code, parent['template_id'], current['name_ru'], current['name_kk'], actor)
    assert result['action'] == 'DELETED'
    assert not database.execute(text('SELECT 1 FROM personnel_order_template_versions WHERE template_id=:id'), {'id': parent['template_id']}).first()
    assert templates.get_draft(code, child['template_id'])['body_template_ru'] == old['body_template_ru']
    assert database.execute(text('SELECT copied_from_template_version_id FROM personnel_order_templates WHERE template_id=:id'), {'id':child['template_id']}).scalar_one() is None


def test_default_flag_does_not_prohibit_deleting_a_test_template(database):
    actor = database.execute(text('SELECT user_id FROM users ORDER BY user_id LIMIT 1')).scalar_one()
    code = 'SUPPLEMENTARY_PAY'
    test = templates.copy_template(code, None, 'TEST default', 'TEST default KK', actor, None, base_source='INITIAL')
    database.execute(text('UPDATE personnel_order_templates SET is_default=FALSE WHERE item_type_code=:code'), {'code':code})
    database.execute(text('UPDATE personnel_order_templates SET is_default=TRUE WHERE template_id=:id'), {'id':test['template_id']})
    assert templates.remove_template(code, test['template_id'], 'TEST default', 'TEST default KK', actor)['action'] == 'DELETED'


def test_copy_and_title_only_save_keep_source_and_two_identities(database):
    actor = database.execute(text('SELECT user_id FROM users ORDER BY user_id LIMIT 1')).scalar_one()
    code = 'CONCURRENT_DUTY_START'
    first = templates.copy_template(code, None, 'TEST additional rate', 'TEST ставка KK', actor, None, base_source='INITIAL')
    second = templates.copy_template(code, first['template_version_id'], 'TEST additional pay', 'TEST доплата KK', actor, first['revision'])
    assert first['template_id'] != second['template_id']
    assert second['title_ru'] == second['name_ru'] == 'TEST additional pay'
    assert second['title_kk'] == second['name_kk'] == 'TEST доплата KK'
    changed = {field: second[field] for field in templates.TEXT_FIELDS}
    changed['title_ru'] = 'TEST renamed pay'
    saved = templates.save_draft(code, second['revision'], changed, actor, second['template_id'], expected_template_version_id=second['template_version_id'])
    assert saved['status'] == 'DRAFT'
    assert saved['template_version_id'] == second['template_version_id']
    assert all(saved[field] == first[field] for field in templates.TEXT_FIELDS if not field.startswith('title_'))
    unchanged = templates.get_draft(code, first['template_id'])
    assert all(unchanged[field] == first[field] for field in (*templates.TEXT_FIELDS, 'revision', 'template_version_id', 'status'))
    names = {t['template_id']: t['name_ru'] for t in templates.list_templates(code)}
    assert names[first['template_id']] == 'TEST additional rate'
    assert names[second['template_id']] == 'TEST renamed pay'


@pytest.fixture
def database(monkeypatch):
    engine = create_engine(URL)
    with engine.connect() as conn:
        transaction = conn.begin()
        assert conn.execute(text('SELECT version_num FROM alembic_version')).scalar_one() in {'hrtpl001','hrrecall001'}
        from app.services import personnel_order_document_item_service as document_items
        from app.services.personnel_orders_editorial import service as editorial
        for service in (templates, applications, manual, document_items, editorial): monkeypatch.setattr(service, 'engine', TransactionEngine(conn))
        # Duplicate checking uses its own engine. Make it share this rollback-only transaction.
        from app.services import personnel_order_document_header_service as headers
        monkeypatch.setattr(headers, 'engine', TransactionEngine(conn))
        try: yield conn
        finally: transaction.rollback()
    engine.dispose()


def test_independent_copy_publication_and_preserved_default(database):
    conn = database
    actor = conn.execute(text('SELECT user_id FROM users ORDER BY user_id LIMIT 1')).scalar_one()
    source = templates.get_published('HIRE')
    if source is None:
        initial=dict(get_personnel_order_template_spec('HIRE').initial_texts)
        initial_draft=templates.create_draft_from_working_copy('HIRE','INITIAL',None,None,initial,actor)
        source=templates.publish_draft('HIRE',initial_draft['revision'],actor)
    default_draft=templates.get_draft('HIRE')
    if default_draft is None:
        next_values={field:source[field] for field in templates.TEXT_FIELDS}
        next_values['title_ru']+=' Default draft'
        default_draft=templates.create_draft_from_working_copy('HIRE','PUBLISHED',source['template_version_id'],source['revision'],next_values,actor)
    published_count=len(templates.list_templates('HIRE',published_only=True))
    before = dict(conn.execute(text('SELECT * FROM personnel_order_template_versions WHERE template_version_id=:id'), {'id':source['template_version_id']}).mappings().one())
    copy = templates.copy_template('HIRE', source['template_version_id'], 'Variant RU', 'Variant KZ', actor, source['revision'])
    assert copy['template_id'] != source['template_id'] and copy['version_number'] == 1 and copy['status'] == 'DRAFT'
    assert all(copy[field] == source[field] for field in templates.TEXT_FIELDS if not field.startswith("title_"))
    assert copy["title_ru"] == "Variant RU" and copy["title_kk"] == "Variant KZ"
    assert templates.get_published('HIRE', copy['template_id']) is None
    assert templates.get_published('HIRE')['template_version_id'] == source['template_version_id']
    changed = {field: copy[field] for field in templates.TEXT_FIELDS}
    changed['body_template_ru'] += ' COPY ONLY'; changed['body_template_kk'] += ' COPY KZ'
    saved = templates.save_draft('HIRE', 1, changed, actor, copy['template_id'])
    with pytest.raises(templates.TemplateDraftError): templates.publish_draft('HIRE', 1, actor, copy['template_id'])
    published = templates.publish_draft('HIRE', saved['revision'], actor, copy['template_id'])
    assert published['template_version_id'] == copy['template_version_id']
    assert len(templates.list_templates('HIRE', published_only=True)) == published_count+1
    assert dict(conn.execute(text('SELECT * FROM personnel_order_template_versions WHERE template_version_id=:id'), {'id':source['template_version_id']}).mappings().one()) == before
    next_values = dict(changed); next_values['body_template_ru'] += ' NEXT'
    second = templates.create_draft_from_working_copy('HIRE', 'PUBLISHED', published['template_version_id'], published['revision'], next_values, actor, copy['template_id'])
    assert second['version_number'] == 2
    templates.publish_draft('HIRE', second['revision'], actor, copy['template_id'])
    assert templates.get_published('HIRE')['template_version_id'] == source['template_version_id']
    assert templates.get_draft('HIRE')['template_version_id'] == default_draft['template_version_id']
    with pytest.raises(templates.TemplateDraftError): templates.get_draft('TRANSFER', copy['template_id'])
    with pytest.raises(templates.TemplateDraftError): templates.copy_template('HIRE', source['template_version_id'], ' ', 'KZ', actor, source['revision'])


def test_copy_builtin_without_saving_or_publishing_source(database):
    actor=database.execute(text('SELECT user_id FROM users ORDER BY user_id LIMIT 1')).scalar_one()
    code='CONCURRENT_DUTY_END'
    initial=dict(get_personnel_order_template_spec(code).initial_texts)
    before=templates.get_draft(code),templates.get_published(code)
    created=templates.copy_template(code,None,'Builtin copy RU','Builtin copy KZ',actor,None,base_source='INITIAL')
    assert created['status']=='DRAFT' and created['version_number']==1
    assert all(created[field]==initial[field] for field in templates.TEXT_FIELDS if not field.startswith("title_"))
    assert created["title_ru"] == "Builtin copy RU" and created["title_kk"] == "Builtin copy KZ"
    assert templates.get_published(code,created['template_id']) is None
    assert (templates.get_draft(code),templates.get_published(code))==before
    assert any(t['is_default'] and t['template_id']!=created['template_id'] for t in templates.list_templates(code))


def test_recall_retyping_preserves_text_and_exact_version_application(database):
    from app.services.personnel_order_recall_contract import TEXTS
    actor=database.execute(text('SELECT user_id FROM users ORDER BY user_id LIMIT 1')).scalar_one()
    employee=database.execute(text('SELECT employee_id FROM employees ORDER BY employee_id LIMIT 1')).scalar_one()
    source=templates.copy_template('RETURN_FROM_CHILDCARE_LEAVE',None,'Recall rollback RU','Recall rollback KZ',actor,None,base_source='INITIAL')
    # Save all eight recall fields while the copy is an incomplete source-type draft.
    saved=templates.save_draft('RETURN_FROM_CHILDCARE_LEAVE',source['revision'],TEXTS,actor,source['template_id'],expected_template_version_id=source['template_version_id'])
    changed=templates.change_template_type('RETURN_FROM_CHILDCARE_LEAVE',source['template_id'],'LEAVE.ANNUAL.RECALL',saved['template_version_id'],saved['revision'],actor)
    assert changed['template_version_id']==source['template_version_id']
    assert changed['revision']==saved['revision']+1
    assert all(changed[field]==TEXTS[field] for field in templates.TEXT_FIELDS)
    # Publication does not require an artificial text edit.
    published=templates.publish_draft('LEAVE.ANNUAL.RECALL',changed['revision'],actor,source['template_id'])
    order=manual.create_manual_draft(created_by=actor,template_version_id=published['template_version_id'],order_number='recall-'+uuid4().hex,order_date=date(2026,10,7),source_title=TEXTS['title_ru'],source_title_locale='ru',item_type_code='LEAVE.ANNUAL.RECALL',employee_id=employee,effective_date=date(2026,10,12),document_subject_context={'position_name':'врач','org_unit_name':'Терапия'},item_payload={'recall_position_kk':'дәрігер','recall_org_unit_kk':'Терапия','basis_ru':'Докладная записка RU','basis_kk':'Баяндау хат KZ'})
    header=database.execute(text('SELECT order_type_code,status,selected_template_version_id FROM personnel_orders WHERE order_id=:id'),{'id':order['order_id']}).one()
    assert header==('LEAVE.ANNUAL.RECALL','DRAFT',published['template_version_id'])
    history=database.execute(text('SELECT template_version_id,rendered_snapshot FROM personnel_order_template_applications WHERE order_id=:id'),{'id':order['order_id']}).mappings().one()
    assert history['template_version_id']==published['template_version_id']
    assert '2026 жылғы 12 қазаннан' in str(history['rendered_snapshot'])
    assert 'Докладная записка RU' in str(history['rendered_snapshot']) and 'Баяндау хат KZ' in str(history['rendered_snapshot'])
    assert database.execute(text('SELECT count(*) FROM employee_events WHERE order_id=:id'),{'id':order['order_id']}).scalar_one()==0
    from app.services import personnel_order_document_item_service as document_items
    item=document_items.list_document_items(order_id=order['order_id'])['items'][0]
    assert item['basis_ru']=='Докладная записка RU' and item['basis_kk']=='Баяндау хат KZ'
    updated=document_items.patch_document_item(order_id=order['order_id'],item_id=item['item_id'],expected_document_revision=1,item_type_code='LEAVE.ANNUAL.RECALL',employee_id=employee,effective_date=date(2026,10,13),document_subject_context={'basis_ru':'Уточнённое основание RU','basis_kk':'Нақтыланған негіз KZ'},reason_code=None,reason_text=None,actor_user_id=actor)
    assert updated['resulting_document_revision']==2
    applications.apply_template_application(order['order_id'],actor,expected_document_revision=2,confirm_reapply=True)
    preview=applications.preview_template_application(order['order_id'])
    assert preview['last_application']['template_version_id']==published['template_version_id']
    assert 'Уточнённое основание RU' in str(preview) and 'Нақтыланған негіз KZ' in str(preview)
    assert '2026 жылғы 13 қазаннан' in str(preview)
    assert database.execute(text('SELECT count(*) FROM employee_events WHERE order_id=:id'),{'id':order['order_id']}).scalar_one()==0
    with pytest.raises(templates.TemplateDraftError):
        templates.change_template_type('LEAVE.ANNUAL.RECALL',source['template_id'],'RETURN_FROM_CHILDCARE_LEAVE',published['template_version_id'],published['revision'],actor)


def test_recall_schema_upgrade_changes_only_constraints(database,monkeypatch):
    import importlib.util
    from pathlib import Path
    spec=importlib.util.spec_from_file_location('recall_schema',Path('alembic/versions/hrrecall001_annual_leave_recall_drafts.py'))
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    tables=['personnel_orders','personnel_order_items','personnel_order_template_versions','employee_events']
    before={table:database.execute(text(f'SELECT count(*) FROM public.{table}')).scalar_one() for table in tables}
    monkeypatch.setattr(migration.op,'get_bind',lambda:database)
    monkeypatch.setattr(migration.op,'execute',lambda statement:database.execute(text(statement)))
    migration.upgrade()
    for table,name in migration.CONSTRAINTS:
        definition=database.execute(text('SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname=:name'),{'name':name}).scalar_one()
        assert 'LEAVE.ANNUAL.RECALL' in definition
    assert database.execute(text("SELECT condeferrable FROM pg_constraint WHERE conname='fk_personnel_template_version_template'")).scalar_one() is True
    assert before=={table:database.execute(text(f'SELECT count(*) FROM public.{table}')).scalar_one() for table in tables}


@pytest.mark.parametrize('stored', [False, True])
def test_unpaid_to_annual_keeps_text_and_requires_target_variables(database, stored):
    actor = database.execute(text('SELECT user_id FROM users ORDER BY user_id LIMIT 1')).scalar_one()
    source_code, target_code = 'LEAVE.UNPAID.GRANT', 'LEAVE.ANNUAL.GRANT'
    initial = dict(get_personnel_order_template_spec(source_code).initial_texts)
    source = templates.copy_template(source_code, None, 'Source RU', 'Source KZ', actor, None, base_source='INITIAL') if stored else None
    before = templates.get_draft(source_code), templates.get_published(source_code)
    copy = templates.copy_template(target_code, source['template_version_id'] if source else None,
        'Annual RU', 'Annual KZ', actor, source['revision'] if source else None,
        base_source='VERSION' if stored else 'INITIAL', source_type_code=source_code)
    assert copy['item_type_code'] == target_code
    assert copy['status'] == 'DRAFT' and copy['version_number'] == 1
    assert all(copy[field] == initial[field] for field in templates.TEXT_FIELDS if not field.startswith("title_"))
    assert templates.get_published(target_code, copy['template_id']) is None
    with pytest.raises(templates.TemplateDraftError, match='Неизвестная переменная'):
        templates.publish_draft(target_code, copy['revision'], actor, copy['template_id'])
    corrected = dict(get_personnel_order_template_spec(target_code).initial_texts)
    saved = templates.save_draft(target_code, copy['revision'], corrected, actor, copy['template_id'])
    published = templates.publish_draft(target_code, saved['revision'], actor, copy['template_id'])
    assert published['item_type_code'] == target_code
    assert (templates.get_draft(source_code), templates.get_published(source_code)) == before
    if source:
        assert all(templates.list_versions(source_code, source['template_id'])[0][field] == source[field] for field in templates.TEXT_FIELDS)


def test_delete_and_archive_independent_templates_keep_references(database):
    actor = database.execute(text('SELECT user_id FROM users ORDER BY user_id LIMIT 1')).scalar_one()
    code = 'HIRE'
    unused = templates.copy_template(code, None, 'Delete only test', 'Delete KZ', actor, None, base_source='INITIAL')
    with pytest.raises(templates.TemplateDraftError, match='Название'):
        templates.remove_template(code, unused['template_id'], 'wrong', 'Delete KZ', actor)
    assert templates.remove_template(code, unused['template_id'], 'Delete only test', 'Delete KZ', actor)['action'] == 'DELETED'
    assert not database.execute(text('SELECT 1 FROM personnel_order_template_versions WHERE template_version_id=:id'), {'id':unused['template_version_id']}).first()
    parent = templates.copy_template(code, None, 'Used parent', 'Parent KZ', actor, None, base_source='INITIAL')
    templates.publish_draft(code, parent['revision'], actor, parent['template_id'])
    order_id = database.execute(text("""
        INSERT INTO personnel_orders(order_number,order_date,order_type_code,status,source_mode,storage_json,created_by,selected_template_version_id)
        VALUES(:number,CURRENT_DATE,'HIRE','DRAFT','PAPER','{}'::jsonb,:actor,:version) RETURNING order_id
    """), {'number':'archive-'+uuid4().hex, 'actor':actor, 'version':parent['template_version_id']}).scalar_one()
    child = templates.copy_template(code, parent['template_version_id'], 'Child', 'Child KZ', actor, parent['revision'])
    result = templates.remove_template(code, parent['template_id'], 'Used parent', 'Parent KZ', actor)
    assert result['action'] == 'ARCHIVED'
    archived = templates.list_versions(code, parent['template_id'])[0]
    assert archived['status'] == 'ARCHIVED'
    assert all(archived[field] == parent[field] for field in templates.TEXT_FIELDS)
    assert not any(t['template_id'] == parent['template_id'] for t in templates.list_templates(code))
    assert database.execute(text('SELECT copied_from_template_version_id FROM personnel_order_templates WHERE template_id=:id'), {'id':child['template_id']}).scalar_one() == parent['template_version_id']
    assert database.execute(text('SELECT selected_template_version_id FROM personnel_orders WHERE order_id=:id'), {'id':order_id}).scalar_one() == parent['template_version_id']



def test_exact_versions_render_different_bilingual_content_and_rollback(database):
    conn = database
    actor = conn.execute(text('SELECT user_id FROM users ORDER BY user_id LIMIT 1')).scalar_one()
    current=templates.get_published('SUPPLEMENTARY_PAY')
    if current:
        conn.execute(text("UPDATE personnel_order_template_versions SET status='ARCHIVED',updated_at=now() WHERE template_version_id=:id"),{'id':current['template_version_id']})
    values = dict(get_personnel_order_template_spec('SUPPLEMENTARY_PAY').initial_texts)
    values.update(body_template_ru='FIRST {{employee.full_name}}', body_template_kk='FIRST KZ {{employee.full_name}}', basis_template_ru='Evidence RU', basis_template_kk='Evidence KZ')
    source = templates.create_draft_from_working_copy('SUPPLEMENTARY_PAY','INITIAL',None,None,values,actor)
    templates.publish_draft('SUPPLEMENTARY_PAY',1,actor)
    copied = templates.copy_template('SUPPLEMENTARY_PAY',source['template_version_id'],'Second option','Second KZ',actor,1)
    changed = dict(values); changed.update(body_template_ru='SECOND {{employee.full_name}}',body_template_kk='SECOND KZ {{employee.full_name}}')
    saved = templates.save_draft('SUPPLEMENTARY_PAY',1,changed,actor,copied['template_id'])
    templates.publish_draft('SUPPLEMENTARY_PAY',saved['revision'],actor,copied['template_id'])
    employee = conn.execute(text('SELECT employee_id FROM employees ORDER BY employee_id LIMIT 1')).scalar_one()
    def create(version, locale, kind='SUPPLEMENTARY_PAY'):
        return manual.create_manual_draft(created_by=actor, template_version_id=version,
          order_number='variant-'+uuid4().hex, order_date=date(2026,10,6), source_title='Archive title stays',
          source_title_locale=locale, item_type_code=kind, employee_id=employee, effective_date=date(2026,10,6))
    orders=[]
    for version, marker, locale in [(source['template_version_id'],'FIRST','kk'),(copied['template_version_id'],'SECOND','ru')]:
        order=create(version,locale); orders.append(order['order_id'])
        header=conn.execute(text('SELECT source_title,source_title_locale,selected_template_version_id FROM personnel_orders WHERE order_id=:id'),{'id':order['order_id']}).one()
        assert header == ('Archive title stays',locale,version)
        blocks=conn.execute(text("SELECT b.locale,b.generated_text FROM personnel_order_item_editorial_blocks b JOIN personnel_order_items i ON i.item_id=b.order_item_id WHERE i.order_id=:id AND b.block_type='body'"),{'id':order['order_id']}).all()
        assert len(blocks)==2 and all(marker in block.generated_text for block in blocks)
        history=conn.execute(text('SELECT template_version_id,template_snapshot,rendered_snapshot FROM personnel_order_template_applications WHERE order_id=:id'),{'id':order['order_id']}).mappings().one()
        assert history['template_version_id']==version and marker in str(history['rendered_snapshot'])
    # New publication of the same template cannot silently change a saved selection.
    third = dict(values); third['body_template_ru'] = 'LATER {{employee.full_name}}'
    next_draft=templates.create_draft_from_working_copy('SUPPLEMENTARY_PAY','PUBLISHED',source['template_version_id'],1,third,actor)
    templates.publish_draft('SUPPLEMENTARY_PAY',next_draft['revision'],actor)
    assert applications.preview_template_application(orders[0])['template']['template_version_id']==source['template_version_id']
    plain=create(None,'kk','TRANSFER')
    assert conn.execute(text('SELECT selected_template_version_id FROM personnel_orders WHERE order_id=:id'),{'id':plain['order_id']}).scalar_one() is None
    assert not conn.execute(text('SELECT 1 FROM personnel_order_template_applications WHERE order_id=:id'),{'id':plain['order_id']}).first()
    before=conn.execute(text('SELECT count(*) FROM personnel_orders')).scalar_one()
    with pytest.raises(PersonnelOrderValidationError), conn.begin_nested(): create(copied['template_version_id'],'ru','HIRE')
    assert conn.execute(text('SELECT count(*) FROM personnel_orders')).scalar_one()==before


def test_migration_preserves_existing_versions_and_history(database, monkeypatch):
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy.exc import DBAPIError
    path=Path(__file__).resolve().parents[1]/'alembic/versions/hrtpl001_independent_personnel_templates.py'
    spec=importlib.util.spec_from_file_location('template_variants_migration',path)
    migration=importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    monkeypatch.setattr(migration,'op',Operations(MigrationContext.configure(database)))
    if database.execute(text('SELECT count(*) FROM personnel_order_templates WHERE NOT is_default')).scalar_one():
        with pytest.raises(DBAPIError), database.begin_nested(): migration.downgrade()
        return
    migration.downgrade()
    before={table:[dict(row) for row in database.execute(text(f'SELECT * FROM {table} ORDER BY 1')).mappings()]
        for table in ('personnel_order_template_versions','personnel_order_template_applications','personnel_orders')}
    migration.upgrade()
    for table,rows in before.items():
        after=[dict(row) for row in database.execute(text(f'SELECT * FROM {table} ORDER BY 1')).mappings()]
        assert len(after)==len(rows)
        assert all({key:new[key] for key in old}==old for old,new in zip(rows,after))
    published=database.execute(text("SELECT template_version_id FROM personnel_order_template_versions WHERE status='PUBLISHED' LIMIT 1")).scalar_one()
    with pytest.raises(DBAPIError), database.begin_nested():
        database.execute(text("UPDATE personnel_order_template_versions SET title_ru='Forbidden overwrite' WHERE template_version_id=:id"),{'id':published})
    with pytest.raises(DBAPIError), database.begin_nested():
        database.execute(text("UPDATE personnel_order_template_applications SET template_snapshot='{}' WHERE template_application_id=(SELECT min(template_application_id) FROM personnel_order_template_applications)"))
