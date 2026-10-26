"""Create a version/order snapshot only in a new disposable PostgreSQL DB."""
import json
from sqlalchemy import text
from tests.test_personnel_order_print_titles_migration_isolated import fresh_database


def test_named_version_and_specialty_create_reopen_clear_preview_and_print(fresh_database,monkeypatch):
    from pathlib import Path
    from app.services import personnel_order_template_draft_service as templates
    from app.services.personnel_order_concurrent_contract import concurrent_values
    from app.services.personnel_order_medical_specialty import specialty_values
    from app.services.personnel_order_template_application_service import _render
    from app.services.personnel_order_print_titles import print_title_errors,template_text_snapshot,rendered_order_snapshot,load_order_print_title_snapshot
    from tests.test_personnel_order_concurrent_contract import DATA
    package=json.loads((Path(__file__).resolve().parents[1]/'reference-data/personnel-templates/transfer-181e750e.json').read_text(encoding='utf-8'))
    internal='О совмещении (простой, как по доп ставке)'
    entry=next(item for item in package['entries'] if item['identity']['name_ru']==internal)
    texts=entry['version']['texts']
    specialty={'medical_specialty_id':57,'name_ru':'Акушерство и гинекология','name_kk':'Акушерия және гинекология'}
    with fresh_database.begin() as conn:
        conn.execute(text('''CREATE TABLE public.personnel_order_templates(
            template_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,item_type_code text,name_ru text,name_kk text,
            is_default boolean DEFAULT false,created_by_user_id bigint,copied_from_template_version_id bigint)'''))
        conn.execute(text('''CREATE TABLE public.personnel_order_template_versions(
            template_version_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,template_id bigint,item_type_code text,
            version_number int,status text,revision int DEFAULT 1,title_ru text,title_kk text,print_title_ru text,print_title_kk text,
            preamble_ru text,preamble_kk text,body_template_ru text,body_template_kk text,basis_template_ru text,basis_template_kk text,
            based_on_built_in boolean DEFAULT false,created_at timestamptz DEFAULT now(),updated_at timestamptz DEFAULT now(),
            created_by_user_id bigint,updated_by_user_id bigint,published_at timestamptz,published_by_user_id bigint)'''))
        conn.execute(text('''CREATE TABLE public.personnel_order_template_applications(
            template_application_id bigint PRIMARY KEY,order_id bigint,order_item_id bigint,template_version_id bigint,
            template_snapshot jsonb,rendered_snapshot jsonb,applied_at timestamptz DEFAULT now())'''))
        conn.execute(text('CREATE TABLE public.personnel_order_items(item_id bigint PRIMARY KEY,payload jsonb)'))
        conn.execute(text("INSERT INTO public.personnel_order_templates(item_type_code,name_ru,name_kk,is_default) VALUES('CONCURRENT_DUTY_START',:name,:kk,true)"),{'name':internal,'kk':'Қоса атқару туралы'})
        conn.execute(text('''INSERT INTO public.personnel_order_template_versions(template_id,item_type_code,version_number,status,
            title_ru,title_kk,preamble_ru,preamble_kk,body_template_ru,body_template_kk,basis_template_ru,basis_template_kk)
            VALUES(1,'CONCURRENT_DUTY_START',1,'PUBLISHED',:title_ru,:title_kk,:preamble_ru,:preamble_kk,:body_template_ru,:body_template_kk,:basis_template_ru,:basis_template_kk)'''),texts)
        original=dict(conn.execute(text('SELECT * FROM public.personnel_order_template_versions WHERE template_version_id=1')).mappings().one())
    monkeypatch.setattr(templates,'engine',fresh_database)
    source_projection=templates.get_published.__wrapped__('CONCURRENT_DUTY_START',1)
    assert source_projection['title_ru']==internal and not print_title_errors(source_projection)
    base=templates.get_editor_base.__wrapped__('CONCURRENT_DUTY_START',1)
    assert base['title_ru']==internal and not print_title_errors(base)
    draft=templates.copy_template('CONCURRENT_DUTY_START',1,internal,'Қоса атқару туралы',1,1)
    assert draft['title_ru']==internal
    assert (draft['print_title_ru'],draft['print_title_kk'])==('О совмещении','Қоса атқару туралы')
    assert not print_title_errors(draft)
    published=templates.publish_draft.__wrapped__('CONCURRENT_DUTY_START',draft['revision'],1,draft['template_id'])
    assert published['title_ru']==internal and not print_title_errors(published)
    with fresh_database.begin() as conn:
        reopened=dict(conn.execute(text('SELECT * FROM public.personnel_order_template_versions WHERE template_version_id=:id'),{'id':published['template_version_id']}).mappings().one())
        assert dict(conn.execute(text('SELECT * FROM public.personnel_order_template_versions WHERE template_version_id=1')).mappings().one())==original
        from app.services.personnel_order_item_templates import resolve_item_templates
        pinned=resolve_item_templates(conn,{'order_id':99002,'selected_template_version_id':1},[{'item_id':1,'item_number':1,'item_type_code':'CONCURRENT_DUTY_START'}])[1]
        assert not print_title_errors(pinned)
        assert _render(pinned,concurrent_values(DATA,'2026-07-01'))['title_ru']=='О совмещении'
        assert _render(pinned,concurrent_values(DATA,'2026-07-01'))['title_kk']=='Қоса атқару туралы'
        conn.execute(text('INSERT INTO public.personnel_order_items VALUES(1,CAST(:p AS jsonb))'),{'p':json.dumps({'concurrent':DATA,'medical_specialty':specialty})})
        for _ in range(2):
            payload=conn.execute(text('SELECT payload FROM public.personnel_order_items WHERE item_id=1')).scalar_one()
            values=concurrent_values(payload['concurrent'],'2026-07-01')
            values.update(specialty_values('CONCURRENT_DUTY_START',payload,reopened))
            rendered=_render(reopened,values)
            assert rendered['title_ru']=='О совмещении' and rendered['title_kk']=='Қоса атқару туралы'
            assert rendered['body_template_ru'].count('Акушерство и гинекология')==1
            assert rendered['body_template_kk'].count('Акушерия және гинекология')==1
            assert 'требуется согласование' not in ' '.join(rendered.values())
        conn.execute(text('''INSERT INTO public.personnel_order_template_applications VALUES(1,99001,1,:v,CAST(:s AS jsonb),CAST(:r AS jsonb),now())'''),
            {'v':published['template_version_id'],'s':json.dumps(template_text_snapshot(reopened,templates.TEXT_FIELDS)),
             'r':json.dumps({'order':rendered_order_snapshot(rendered,reopened),'items':[{'order_item_id':1}]})})
        snapshot=load_order_print_title_snapshot(conn,99001,[{'item_id':1,'item_number':1,'item_status':'ACTIVE'}])
        assert not snapshot['requires_update'] and not snapshot['missing_locales']
        assert snapshot['print_title_ru']=='О совмещении' and snapshot['print_title_kk']=='Қоса атқару туралы'
        payload['medical_specialty']=None
        conn.execute(text('UPDATE public.personnel_order_items SET payload=CAST(:p AS jsonb) WHERE item_id=1'),{'p':json.dumps(payload)})
        payload=conn.execute(text('SELECT payload FROM public.personnel_order_items WHERE item_id=1')).scalar_one()
        assert payload['medical_specialty'] is None
        values=concurrent_values(payload['concurrent'],'2026-07-01')
        values.update(specialty_values('CONCURRENT_DUTY_START',payload,reopened))
        cleared=_render(reopened,values)
        assert 'Акушерство' not in cleared['body_template_ru'] and 'Акушерия' not in cleared['body_template_kk']
        assert cleared['title_ru']=='О совмещении' and cleared['title_kk']=='Қоса атқару туралы'
