"""Synthetic bound-point saves; only the disposable browser harness may run this."""
from contextlib import nullcontext
from datetime import date
import json
import os
from pathlib import Path

import pytest
from sqlalchemy import text
from app.db.engine import engine
from app.services import personnel_order_manual_draft_service as manual, personnel_orders_command_service as commands, personnel_orders_query_service as queries
from app.services import personnel_order_template_application_service as applications, personnel_order_document_header_service as headers
from app.services.personnel_orders_editorial import generation_service as generation, service as editorial

pytestmark = pytest.mark.skipif(not (engine.url.database or '').startswith('corpsite_case_') or not os.getenv('CASE_CHECK_STATE'), reason='requires isolated synthetic case-check harness')


@pytest.mark.parametrize('rate,total', [('0.25','1.25'), ('0.5','1.5'), ('0.75','1.75')])
def test_save_existing_binding_refreshes_bilingual_text_and_preserves_overrides(monkeypatch, rate, total):
    state=json.loads(Path(os.environ['CASE_CHECK_STATE']).read_text(encoding='utf8'))
    assert engine.url.database == state['db'] and engine.url.database.endswith('_test')
    with engine.connect() as conn:
        tx=conn.begin()
        try:
            class Adapter:
                def begin(self): return nullcontext(conn)
                def connect(self): return nullcontext(conn)
            for module in (manual,commands,queries,applications,headers,generation,editorial):
                monkeypatch.setattr(module,'engine',Adapter())
            created=manual.create_manual_draft(created_by=state['user_id'], template_version_id=state['versions']['TRANSFER'], order_number='SYNTHETIC-BOUND-CASE', order_date=date(2026,10,22), source_title='Синтетический приказ', source_title_locale='ru', item_type_code='TRANSFER', employee_id=state['employee_id'], effective_date=date(2026,11,1), item_payload={'document_forms_ru':{'employee_full_name_accusative_ru':'Тестову Анну Ивановну'}, 'transfer':{'position_ru':'Врач','position_kk':'Дәрігер','org_unit_ru':'Тестовое отделение','org_unit_kk':'Сынақ бөлімшесі','rate':'1','basis_ru':'Синтетическое заявление','basis_kk':'Сынақ өтініш'}})
            order=created['order_id']; assert order != 5645
            payload={'concurrent':{'position_ru':'Врач-реабилитолог','position_kk':'Реабилитолог дәрігері','org_unit_ru':'Тестовое отделение реабилитации','org_unit_kk':'Сынақ оңалту бөлімшесінің','position_genitive_ru':'врача-реабилитолога','org_unit_genitive_ru':'тестового отделения реабилитации','employee_dative_ru':'Тестовой Анне Ивановне','employee_dative_kk':'Анна Ивановна Тестоваға','rate':'0.25','total_rate':'1.25','basis_ru':'Синтетическое согласие','basis_kk':'Сынақ келісім'}}
            detail=commands.create_personnel_order_item(order_id=order,item_type_code='CONCURRENT_DUTY_START',template_version_id=state['versions']['CONCURRENT_DUTY_START'],employee_id=state['employee_id'],effective_date=date(2026,11,1),payload=payload,actor_user_id=state['user_id'])
            header_state=editorial.get_editorial_state(order)
            for locale,title in [('ru','О переводе и дополнительной нагрузке'),('kk','Ауыстыру және қосымша жүктеме туралы')]:
                block=next(b for b in header_state['order_blocks'] if b['locale']==locale and b['block_type']=='title')
                editorial.patch_editorial_block(order,block['block_id'],user_id=state['user_id'],override_text=title,expected_revision=block['revision'])
            first=json.dumps(detail['items'][0],sort_keys=True,default=str)
            item=detail['items'][1]['item_id']
            conn.execute(text("UPDATE personnel_order_item_editorial_blocks SET override_text='Ручное подтверждённое основание' WHERE order_item_id=:i AND locale='ru' AND block_type='basis'"),{'i':item})
            payload['concurrent'].update(rate=rate,total_rate=total)
            reopened=commands.update_personnel_order_item(order_id=order,item_id=item,payload=payload,actor_user_id=state['user_id'])
            assert json.dumps(reopened['items'][0],sort_keys=True,default=str)==first
            blocks=conn.execute(text("SELECT locale,block_type,generated_text,override_text FROM personnel_order_item_editorial_blocks WHERE order_item_id=:i"),{'i':item}).mappings().all()
            for locale in ('ru','kk'):
                body=next(b['generated_text'] for b in blocks if b['locale']==locale and b['block_type']=='body')
                assert rate.replace('.',',') in body and total.replace('.',',') in body
            assert next(b['override_text'] for b in blocks if b['locale']=='ru' and b['block_type']=='basis')=='Ручное подтверждённое основание'
            preview=applications.preview_template_application(order)
            assert {i['template']['template_version_id'] for i in preview['items']}==set(state['versions'].values())
            assert not any(i['blocked'] for i in preview['items'])
            if os.getenv('CASE_RESULTS_DIR'):
                folder=Path(os.environ['CASE_RESULTS_DIR']);folder.mkdir(exist_ok=True,parents=True)
                (folder/f'rate-{rate}.json').write_text(json.dumps({'detail':reopened,'editorial':editorial.get_editorial_state(order)},ensure_ascii=False,default=str,indent=2),encoding='utf8')
            first_item=reopened['items'][0]
            changed={**first_item['payload'],'document_forms_ru':{'employee_full_name_accusative_ru':'Тестову Анну Ивановну (проверено)'}}
            commands.update_personnel_order_item(order_id=order,item_id=first_item['item_id'],payload=changed,actor_user_id=state['user_id'])
            body=conn.execute(text("SELECT generated_text FROM personnel_order_item_editorial_blocks WHERE order_item_id=:i AND locale='ru' AND block_type='body'"),{'i':first_item['item_id']}).scalar_one()
            assert body.startswith('Перевести Тестову Анну Ивановну (проверено)')
            assert reopened['order']['status']=='DRAFT' and not reopened['events']
        finally:
            tx.rollback()
