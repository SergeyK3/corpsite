"""Real API: published template produces an editable draft, never template write access."""
from uuid import uuid4
import pytest

from sqlalchemy import text
from app.db.engine import engine
from tests.test_sysadmin_assistant_hr_postgres import assistant_http, _call


@pytest.fixture
def published_hire_template():
    # An isolated, previously approved template fixture, never production data.
    from app.services.personnel_order_template_specs import get_personnel_order_template_spec
    values = dict(get_personnel_order_template_spec('HIRE').initial_texts)
    values.update(print_title_ru='О приёме на работу', print_title_kk='Жұмысқа қабылдау туралы')
    with engine.begin() as conn:
        identity=conn.execute(text("""INSERT INTO personnel_order_templates(item_type_code,name_ru,name_kk,is_default)
            VALUES('HIRE',:name,:name,FALSE) RETURNING template_id"""),{'name':'Assistant acceptance '+uuid4().hex}).scalar_one()
        version=conn.execute(text("SELECT coalesce(max(version_number),0)+1 FROM personnel_order_template_versions WHERE item_type_code='HIRE'")).scalar_one()
        template=conn.execute(text("""INSERT INTO personnel_order_template_versions
            (template_id,item_type_code,version_number,status,title_ru,title_kk,print_title_ru,print_title_kk,
             preamble_ru,preamble_kk,body_template_ru,body_template_kk,basis_template_ru,basis_template_kk)
            VALUES(:identity,'HIRE',:version,'PUBLISHED',:title_ru,:title_kk,:print_title_ru,:print_title_kk,
              :preamble_ru,:preamble_kk,:body_template_ru,:body_template_kk,:basis_template_ru,:basis_template_kk)
            RETURNING template_version_id"""),{**values,'version':version,'identity':identity}).scalar_one()
    yield template
    with engine.begin() as conn:
        conn.execute(text("UPDATE personnel_order_template_versions SET status='ARCHIVED' WHERE template_version_id=:t"),{'t':template})


def test_published_template_draft_edit_and_template_write_denied(assistant_http,published_hire_template):
    with engine.connect() as conn:
        assert conn.execute(text('SELECT current_database()')).scalar_one() == 'corpsite_test'
        template = published_hire_template
        employee = conn.execute(text("""SELECT employee_id,org_unit_id,position_id FROM employees
            WHERE org_unit_id IS NOT NULL AND position_id IS NOT NULL ORDER BY employee_id LIMIT 1""")).mappings().one()
        templates_before = conn.execute(text("SELECT md5(string_agg(to_jsonb(t)::text,'|' ORDER BY template_version_id)) FROM personnel_order_template_versions t")).scalar_one()
        employee_before = conn.execute(text("SELECT to_jsonb(e) FROM employees e WHERE employee_id=:e"), {'e':employee['employee_id']}).scalar_one()
        events_before = conn.execute(text('SELECT count(*) FROM employee_events WHERE employee_id=:e'), {'e':employee['employee_id']}).scalar_one()
    title = _call(assistant_http,'GET',f'/directory/personnel-orders/templates/HIRE/published-title?template_version_id={template}').json()
    number = 'ASST-TEMPLATE-' + uuid4().hex[:12]
    order = _call(assistant_http,'POST','/directory/personnel-orders/manual-draft', {
        'template_version_id':template,'order_number':number,'order_date':'2026-11-06',
        'source_title':title['print_title_ru'],'source_title_locale':'ru','item_type_code':'HIRE',
        'employee_id':employee['employee_id'],'effective_date':'2026-11-06',
        'document_subject_context':{'position_name':'Проверка черновика','org_unit_name':'Тестовое отделение',
            'document_position_kk':'Тексеру','document_org_unit_kk':'Сынақ бөлімі'},
        'item_payload':{'org_unit_id':employee['org_unit_id'],'position_id':employee['position_id'],
            'employment_rate':1,'hire_basis':{'ru':'Проверка опубликованного шаблона','kk':'Үлгіні тексеру'}}},status=201).json()['order_id']
    try:
        _call(assistant_http,'PATCH',f'/directory/personnel-orders/{order}',{'comment':'Assistant edited draft'})
        detail = _call(assistant_http,'GET',f'/directory/personnel-orders/{order}').json()
        assert detail['order']['status']=='DRAFT'
        assert detail['order']['comment']=='Assistant edited draft'
        with engine.connect() as conn:
            assert conn.execute(text('SELECT selected_template_version_id FROM personnel_orders WHERE order_id=:o'),{'o':order}).scalar_one()==template
            assert conn.execute(text('SELECT count(*) FROM personnel_order_template_applications WHERE order_id=:o'),{'o':order}).scalar_one()==1
        _call(assistant_http,'PUT','/admin/personnel-order-templates/HIRE/draft',{},status=403)
        _call(assistant_http,'POST','/admin/personnel-order-templates/HIRE/draft/publish',{},status=403)
        with engine.connect() as conn:
            assert conn.execute(text("SELECT md5(string_agg(to_jsonb(t)::text,'|' ORDER BY template_version_id)) FROM personnel_order_template_versions t")).scalar_one()==templates_before
            assert conn.execute(text('SELECT to_jsonb(e) FROM employees e WHERE employee_id=:e'),{'e':employee['employee_id']}).scalar_one()==employee_before
            assert conn.execute(text('SELECT count(*) FROM employee_events WHERE employee_id=:e'),{'e':employee['employee_id']}).scalar_one()==events_before
    finally:
        _call(assistant_http,'DELETE',f'/directory/personnel-orders/{order}',{
            'reason':'Published-template draft acceptance test completed',
            'confirmation_phrase':f'DELETE DRAFT ORDER {order}'})
