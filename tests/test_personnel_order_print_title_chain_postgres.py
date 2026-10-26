"""Version → stored order snapshot → typed API projection in a disposable DB."""
import json
from sqlalchemy import text
from tests.test_personnel_order_print_titles_migration_isolated import fresh_database


def test_print_header_chain_uses_frozen_fields_and_keeps_internal_name(fresh_database):
    from app.services.personnel_order_print_titles import template_text_snapshot, rendered_order_snapshot, load_order_print_title_snapshot
    from app.services.personnel_order_template_application_service import _render, _FIELDS
    from app.services.personnel_order_concurrent_contract import concurrent_values
    from app.directory.personnel_orders_schemas import PersonnelOrderDetailResponse
    from tests.test_personnel_order_concurrent_contract import DATA, TEXTS
    internal='О совмещении (О замещении на время отпуска как доп ставка)'
    # KK is an explicitly supplied synthetic approval fixture, not a translation.
    version={**TEXTS,'title_ru':internal,'item_type_code':'CONCURRENT_DUTY_START',
             'print_title_ru':'О замещении','print_title_kk':'TEST saved KK heading'}
    with fresh_database.begin() as conn:
        conn.execute(text('CREATE TABLE public.personnel_order_template_versions(template_version_id bigint PRIMARY KEY, title_ru text, print_title_ru text, version_json jsonb)'))
        conn.execute(text('''CREATE TABLE public.personnel_order_template_applications(
            template_application_id bigint PRIMARY KEY,order_id bigint,order_item_id bigint,template_version_id bigint,
            template_snapshot jsonb,rendered_snapshot jsonb,applied_at timestamptz DEFAULT now())'''))
        conn.execute(text('CREATE TABLE public.personnel_order_editorial_blocks(order_id bigint,locale text,block_type text,generated_text text)'))
        conn.execute(text('INSERT INTO public.personnel_order_template_versions VALUES(1,:internal,:printed,CAST(:v AS jsonb))'),
                     {'internal':internal,'printed':'О замещении','v':json.dumps(version)})
        saved_version=conn.execute(text('SELECT version_json FROM public.personnel_order_template_versions WHERE template_version_id=1')).scalar_one()
        rendered=_render(saved_version,concurrent_values(DATA,'2026-07-01'),draft_preview=True)
        assert rendered['title_ru']=='О замещении'
        snapshot=template_text_snapshot(saved_version,_FIELDS)
        order_snapshot=rendered_order_snapshot({key:rendered[key] for key in ('title_ru','title_kk','preamble_ru','preamble_kk')},saved_version)
        conn.execute(text('INSERT INTO public.personnel_order_template_applications VALUES(1,99001,1,1,CAST(:s AS jsonb),CAST(:r AS jsonb),now())'),
                     {'s':json.dumps(snapshot),'r':json.dumps({'order':order_snapshot,'items':[{'order_item_id':1}]})})
        # Reproduce the reported stale generated header. It must not win over
        # the separate frozen print title in either presenter.
        conn.execute(text("INSERT INTO public.personnel_order_editorial_blocks VALUES(99001,'ru','title',:internal)"),{'internal':internal})
        projected=load_order_print_title_snapshot(conn,99001,[{'item_id':1,'item_number':1,'item_status':'ACTIVE'}])
        dto=PersonnelOrderDetailResponse(
            order={'order_id':99001,'order_type_code':'CONCURRENT_DUTY_START','order_class':'SIMPLE','status':'DRAFT','source_mode':'MANUAL','created_by':1,'source_title':internal},
            items=[],localized_texts=[],attachments=[],prints=[],events=[],print_title_snapshot=projected)
        response=json.loads(dto.model_dump_json())
        assert response['print_title_snapshot']['print_title_ru']=='О замещении'
        assert not response['print_title_snapshot']['legacy']
        assert response['order']['source_title']==internal
        # A later template edit is unrelated to this order's frozen title.
        conn.execute(text("UPDATE public.personnel_order_template_versions SET title_ru='TEST renamed picker',print_title_ru='TEST later print title' WHERE template_version_id=1"))
        assert load_order_print_title_snapshot(conn,99001,[{'item_id':1,'item_number':1,'item_status':'ACTIVE'}])==projected
        stored=conn.execute(text('SELECT template_snapshot,rendered_snapshot FROM public.personnel_order_template_applications')).mappings().one()
        assert stored['template_snapshot']['title_ru']==internal
        assert stored['rendered_snapshot']['order']['title_ru']=='О замещении'
        assert conn.execute(text('SELECT generated_text FROM public.personnel_order_editorial_blocks')).scalar_one()==internal
        # A separate old order without print fields needs a deliberate update.
        legacy={key:value for key,value in snapshot.items() if not key.startswith('print_title_')}
        conn.execute(text('INSERT INTO public.personnel_order_template_applications VALUES(2,99002,2,1,CAST(:s AS jsonb),CAST(:r AS jsonb),now())'),
                     {'s':json.dumps(legacy),'r':json.dumps({'order':{'title_ru':internal},'items':[{'order_item_id':2}]})})
        old=load_order_print_title_snapshot(conn,99002,[{'item_id':2,'item_number':1,'item_status':'ACTIVE'}])
        assert old['legacy'] and old['requires_update']
        assert old['print_title_ru'] is None
        assert conn.execute(text('SELECT template_snapshot FROM public.personnel_order_template_applications WHERE order_id=99002')).scalar_one()==legacy
