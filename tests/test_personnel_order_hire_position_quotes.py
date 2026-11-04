from unittest.mock import MagicMock
import pytest
from app.services.personnel_order_hire_position_quotes import hire_body_template_without_position_quotes, hire_generated_body_without_position_quotes


@pytest.mark.parametrize('opening,closing',[('«','»'),('“','”'),('"','"')])
def test_only_template_position_wrappers_are_removed_before_substitution(opening,closing):
    source=f'«{{{{org_unit.title_ru}}}}» на должность {opening}{{{{position.title_ru}}}}{closing}; «Другое»'
    assert hire_body_template_without_position_quotes(source)=='«{{org_unit.title_ru}}» на должность {{position.title_ru}}; «Другое»'


@pytest.mark.parametrize('position',['Врач УЗИ','Врач «УЗИ»','«Врач УЗИ»','Врач "УЗИ" — уточнение'])
def test_generated_projection_keeps_internal_and_department_quotes_verbatim(position):
    unit='Отделение «А»'
    payload={'document_position':{'name':position,'name_kk':position},'document_org_unit':{'name':unit,'name_kk':unit}}
    ru=f'Принять в подразделение «{unit}» на должность «{position}» со ставкой 1. «Другое»'
    kk=f'Сынақ «{unit}» бөлімшесіне «{position}» лауазымына қабылдансын. «Другое»'
    assert hire_generated_body_without_position_quotes(ru,'ru',payload)==f'Принять в подразделение «{unit}» на должность {position} со ставкой 1. «Другое»'
    assert hire_generated_body_without_position_quotes(kk,'kk',payload)==f'Сынақ «{unit}» бөлімшесіне {position} лауазымына қабылдансын. «Другое»'


@pytest.mark.parametrize('item_type,override',[('HIRE',None),('HIRE','Ручной текст «Врач УЗИ»'),('HIRE',''),('TRANSFER',None)])
def test_editorial_read_projection_never_changes_overrides_or_other_types(monkeypatch,item_type,override):
    from app.services.personnel_orders_editorial import service
    generated='Принять в подразделение «Отделение» на должность «Врач УЗИ» со ставкой 1.'
    raw={'block_id':1,'order_item_id':1,'locale':'ru','block_type':'body','generated_text':generated,'override_text':override,'review_status':'CURRENT'}
    monkeypatch.setattr(service,'require_available',lambda:None)
    monkeypatch.setattr(service,'engine',MagicMock())
    monkeypatch.setattr(service,'fetch_order',lambda *a:{'order_id':1,'status':'DRAFT'})
    monkeypatch.setattr(service,'load_order_blocks',lambda *a,**kw:[])
    monkeypatch.setattr(service,'load_item_blocks',lambda *a,**kw:[raw])
    monkeypatch.setattr(service,'load_items',lambda *a,**kw:[{'item_id':1,'item_number':1,'item_type_code':item_type,
        'payload':{'document_position':{'name':'Врач УЗИ'},'document_org_unit':{'name':'Отделение'}}}])
    block=service.get_editorial_state(1)['items'][0]['blocks'][0]
    assert raw['generated_text']==generated
    assert block['override_text']==override
    if item_type=='HIRE' and override is None:assert 'на должность Врач УЗИ со ставкой' in block['effective_text']
    else:assert block['generated_text']==generated


def test_bound_hire_render_and_draft_preview_keep_value_quotes_and_template_immutable():
    from app.services.personnel_order_template_specs import get_personnel_order_template_spec
    from app.services.personnel_order_template_application_service import _values,_render
    from app.services.personnel_order_template_draft_service import preview_draft
    template={**get_personnel_order_template_spec('HIRE').initial_texts,'item_type_code':'HIRE'}
    template['body_template_ru']='Принять {{employee.full_name}} в подразделение «{{org_unit.title_ru}}» на должность «{{position.title_ru}}» со ставкой {{rate}} с {{effective_date}}.'
    template['body_template_kk']='{{employee.full_name}} «{{org_unit.title_kk}}» бөлімшесіне «{{position.title_kk}}» лауазымына {{effective_date}} бастап қабылдансын.'
    original=dict(template)
    conn=MagicMock();conn.execute.return_value.mappings.return_value.first.return_value=None
    item={'item_type_code':'HIRE','employee_id':None,'effective_date':'2026-02-02','payload':{
        'source_employee_name':'SYNTHETIC PERSON','hire_basis':{'ru':'Заявление','kk':'Өтініш'},'employment_rate':1,
        'document_position':{'name':'Врач «УЗИ»','name_kk':'«УДЗ» Дәрігер'},'document_org_unit':{'name':'Отделение «А»','name_kk':'«А» бөлімше'}}}
    result=_render(template,_values(conn,item,template)[0])
    assert 'на должность Врач «УЗИ» со ставкой' in result['body_template_ru']
    assert '«УДЗ» Дәрігер лауазымына' in result['body_template_kk']
    assert '«Отделение «А»»' in result['body_template_ru']
    preview=preview_draft('HIRE',{k:v for k,v in template.items() if k!='item_type_code'})
    assert '«[[' not in preview['ru']['body'].split('на должность ')[1]
    assert template==original
