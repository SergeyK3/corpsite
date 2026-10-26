"""Pure template/snapshot tests; no real order, template, or database writes."""
import json
from copy import deepcopy
from contextlib import nullcontext
import pytest
from app.services.personnel_order_print_titles import printable_template, pin_print_titles, template_text_snapshot, print_title_errors
from app.services.personnel_order_print_titles import initial_print_titles, INITIAL_PRINT_TITLES_RU, version_print_titles
from app.services.personnel_order_print_titles import order_print_title_snapshot, rendered_order_snapshot, load_order_print_title_snapshot
from app.services.personnel_order_template_specs import PERSONNEL_ORDER_TEMPLATE_SPECS, get_personnel_order_template_spec
from app.services.personnel_order_template_draft_service import preview_draft, TEXT_FIELDS, _validate, _row
from app.services.personnel_order_template_application_service import _render, TemplateApplicationError


@pytest.mark.parametrize('code',list(PERSONNEL_ORDER_TEMPLATE_SPECS))
def test_frozen_official_title_is_projected_to_api_for_every_type_even_if_old_editorial_title_is_internal(code):
    texts=dict(get_personnel_order_template_spec(code).initial_texts)
    internal=texts['title_ru']+' (TEST internal variant description)'
    official='О замещении' if code=='CONCURRENT_DUTY_START' else texts['title_ru']
    version={**texts,'item_type_code':code,'title_ru':internal,'print_title_ru':official,'print_title_kk':texts['title_kk']}
    # The former renderer/presenter could still have left this stale text in
    # order-level editorial/localized fields. Those fields are not the picker.
    application={'template_version_id':8001,'order_item_id':1,
        'template_snapshot':template_text_snapshot(version,TEXT_FIELDS),
        'rendered_snapshot':{'order':{'title_ru':internal,'title_kk':texts['title_kk']},'items':[{'order_item_id':1}]}}
    source=json.loads(json.dumps(application,ensure_ascii=False))
    projected=order_print_title_snapshot(source)
    assert projected['print_title_ru']==official
    assert projected['print_title_kk']==texts['title_kk']
    assert not projected['legacy'] and not projected['requires_update']
    assert source['template_snapshot']['title_ru']==internal
    assert source['rendered_snapshot']['order']['title_ru']==internal


def test_new_order_snapshot_keeps_official_header_separate_from_internal_template_name():
    from tests.test_personnel_order_concurrent_contract import DATA, TEXTS
    from app.services.personnel_order_concurrent_contract import concurrent_values
    internal='О совмещении (О замещении на время отпуска как доп ставка)'
    version={**TEXTS,'item_type_code':'CONCURRENT_DUTY_START','title_ru':internal,
             'print_title_ru':'О замещении','print_title_kk':TEXTS['title_kk']}
    printed=_render(version,concurrent_values(DATA,'2026-07-01'),draft_preview=True)
    application={'template_version_id':8001,'order_item_id':1,'template_snapshot':template_text_snapshot(version,TEXT_FIELDS),
                 'rendered_snapshot':{'order':rendered_order_snapshot(printed,version),'items':[{'order_item_id':1}]}}
    reread=json.loads(json.dumps(application,ensure_ascii=False))
    assert reread['template_snapshot']['title_ru']==internal
    assert reread['rendered_snapshot']['order']['title_ru']=='О замещении'
    assert reread['rendered_snapshot']['order']['print_title_ru']=='О замещении'
    assert order_print_title_snapshot(reread)['print_title_ru']=='О замещении'
    # Reading or rerendering an order never looks up a renamed default.
    version.update(print_title_ru='Changed later header',title_ru='Changed program label')
    pinned=pin_print_titles(version,reread['template_snapshot'],reread['rendered_snapshot']['order'])
    assert _render(pinned,concurrent_values(DATA,'2026-07-01'),draft_preview=True)['title_ru']=='О замещении'


def test_old_snapshot_is_reported_for_explicit_update_and_is_not_relabelled_as_an_approved_print_title():
    texts=dict(get_personnel_order_template_spec('CONCURRENT_DUTY_START').initial_texts)
    internal='О совмещении (О замещении на время отпуска как доп ставка)'
    old={**texts,'title_ru':internal}
    app={'template_version_id':8001,'template_snapshot':old,'rendered_snapshot':{'order':{'title_ru':internal}}}
    before=deepcopy(app)
    projected=order_print_title_snapshot(app)
    assert projected['legacy'] and projected['requires_update']
    assert projected['print_title_ru'] is None and 'ru' in projected['missing_locales']
    pinned=pin_print_titles({**texts,'print_title_ru':'О замещении','print_title_kk':texts['title_kk']},old,app['rendered_snapshot']['order'])
    assert pinned['print_title_ru']==internal
    assert 'print_title_ru' not in template_text_snapshot(pinned,TEXT_FIELDS)
    assert 'print_title_ru' not in rendered_order_snapshot(app['rendered_snapshot']['order'],pinned)
    assert app==before


def test_composite_print_title_comes_from_the_order_snapshot_not_the_first_item_template():
    app={'template_version_id':1,'template_snapshot':{'print_title_ru':'О приёме','print_title_kk':'TEST template KK'},
         'rendered_snapshot':{'order':{'title_ru':'Internal composite (TEST)', 'print_title_ru':'О кадровых изменениях','print_title_kk':'TEST saved KK'}}}
    assert order_print_title_snapshot(app,composite=True)['print_title_ru']=='О кадровых изменениях'
    del app['rendered_snapshot']['order']['print_title_ru'];del app['rendered_snapshot']['order']['print_title_kk']
    assert order_print_title_snapshot(app,composite=True)['legacy']


def test_read_projection_selects_only_the_first_active_items_snapshot_without_writes():
    old={'template_version_id':4,'order_item_id':1,'template_snapshot':{'print_title_ru':'О замещении','print_title_kk':'TEST KK'},'rendered_snapshot':{}}
    newer_other={'template_version_id':5,'order_item_id':2,'template_snapshot':{'print_title_ru':'Other item header'},'rendered_snapshot':{}}
    class Result:
        def scalar_one(self): return 'personnel_order_template_applications'
        def mappings(self): return self
        def all(self): return [newer_other,old]
    class Conn:
        def execute(self,sql,params=None):
            assert str(sql).strip().startswith('SELECT')
            return Result()
    projected=load_order_print_title_snapshot(Conn(),99001,[{'item_id':1,'item_number':1,'item_status':'ACTIVE'},{'item_id':2,'item_number':2,'item_status':'ACTIVE'}])
    assert projected['template_version_id']==4 and projected['print_title_ru']=='О замещении'


def test_detail_query_and_response_schema_retain_the_frozen_print_title(monkeypatch):
    from app.services import personnel_orders_query_service as queries
    from app.directory.personnel_orders_schemas import PersonnelOrderDetailResponse
    internal='О совмещении (О замещении на время отпуска как доп ставка)'
    header={'order_id':99001,'order_type_code':'CONCURRENT_DUTY_START','status':'DRAFT','source_mode':'MANUAL','created_by':1,'source_title':internal}
    item={'order_id':99001,'item_id':1,'item_number':1,'item_type_code':'CONCURRENT_DUTY_START','item_status':'ACTIVE','payload':{}}
    application={'order_item_id':1,'template_version_id':8001,'template_snapshot':{'title_ru':internal,'print_title_ru':'О замещении','print_title_kk':'TEST saved KK'},'rendered_snapshot':{}}
    class Result:
        def __init__(self,rows=None,scalar=None): self.rows=rows or [];self.scalar=scalar
        def mappings(self): return self
        def first(self): return self.rows[0] if self.rows else None
        def all(self): return self.rows
        def scalar_one(self): return self.scalar
    class Conn:
        def execute(self,sql,params=None):
            sql=str(sql)
            assert sql.strip().startswith('SELECT')
            if 'to_regclass' in sql:
                return Result(scalar='personnel_order_template_applications' if 'personnel_order_template_applications' in sql else None)
            if 'FROM public.personnel_order_template_applications' in sql: return Result([application])
            if 'FROM public.personnel_orders po' in sql: return Result([header])
            if 'FROM public.personnel_order_items poi' in sql: return Result([item])
            return Result()
    class Engine:
        def begin(self): return nullcontext(Conn())
    monkeypatch.setattr(queries,'engine',Engine())
    monkeypatch.setattr(queries,'personnel_orders_available',lambda:True)
    response=PersonnelOrderDetailResponse.model_validate(queries.get_personnel_order(99001)).model_dump()
    assert response['print_title_snapshot']['print_title_ru']=='О замещении'
    assert response['print_title_snapshot']['template_version_id']==8001
    assert response['order']['source_title']==internal


def test_explicit_ru_print_names_cover_all_types_without_changing_internal_titles_or_inventing_kk():
    assert set(INITIAL_PRINT_TITLES_RU)==set(PERSONNEL_ORDER_TEMPLATE_SPECS)
    for code in PERSONNEL_ORDER_TEMPLATE_SPECS:
        before=dict(get_personnel_order_template_spec(code).initial_texts)
        values=initial_print_titles(code)
        assert values['print_title_ru']==before['title_ru']
        assert values['print_title_kk'] is None
        assert dict(get_personnel_order_template_spec(code).initial_texts)==before


def test_explicit_replacement_variant_has_its_own_ru_print_name_and_needs_approved_kk():
    internal='О совмещении (О замещении на время отпуска как доп ставка)'
    assert initial_print_titles('CONCURRENT_DUTY_START',internal)=={'print_title_ru':'О замещении','print_title_kk':None}
    assert internal.endswith('(О замещении на время отпуска как доп ставка)')


def test_simple_concurrent_variant_uses_the_user_approved_pair_without_approval_warnings():
    name='О совмещении (простой, как по доп ставке)'
    pair=initial_print_titles('CONCURRENT_DUTY_START',name)
    assert pair=={'print_title_ru':'О совмещении','print_title_kk':'Қоса атқару туралы'}
    assert not print_title_errors(pair)
    assert printable_template({'title_ru':name,'title_kk':'Қоса атқару туралы',**pair})['title_ru']=='О совмещении'
    assert printable_template({'title_ru':name,'title_kk':'Қоса атқару туралы',**pair})['title_kk']=='Қоса атқару туралы'
    pair['print_title_kk']='TEST manual copy'
    assert initial_print_titles('CONCURRENT_DUTY_START',name)['print_title_kk']=='Қоса атқару туралы'


def test_known_published_version_gets_approved_headings_without_rewriting_its_raw_record_or_old_order_snapshot():
    internal='О совмещении (простой, как по доп ставке)'
    raw={'template_version_id':33,'item_type_code':'CONCURRENT_DUTY_START','status':'PUBLISHED','title_ru':internal,'title_kk':'Қоса атқару туралы','print_title_ru':None,'print_title_kk':None}
    before=deepcopy(raw)
    projected=version_print_titles(raw)
    assert not print_title_errors(projected)
    assert projected['print_title_ru']=='О совмещении' and projected['print_title_kk']=='Қоса атқару туралы'
    assert projected['title_ru']==internal and raw==before
    old={'title_ru':internal,'title_kk':'Қоса атқару туралы'}
    pinned=pin_print_titles(projected,old,{'title_ru':internal,'title_kk':'Қоса атқару туралы'})
    assert pinned['print_title_ru']==internal and pinned['_print_title_source']=='LEGACY'
    unknown=version_print_titles({**raw,'title_ru':'TEST another unapproved variant'})
    assert unknown['print_title_kk'] is None
    cleared_draft=version_print_titles({**raw,'status':'DRAFT','print_title_ru':'','print_title_kk':''})
    assert cleared_draft['print_title_ru']=='' and print_title_errors(cleared_draft)


def test_title_api_removes_approval_notice_for_the_known_published_variant_in_both_lookup_paths(monkeypatch):
    from app.directory import personnel_orders_routes as routes
    from app.db import engine as database_module
    raw={'template_version_id':33,'item_type_code':'CONCURRENT_DUTY_START','status':'PUBLISHED','title_ru':'О совмещении (простой, как по доп ставке)','title_kk':'Қоса атқару туралы'}
    class Result:
        def mappings(self): return self
        def first(self): return raw
    class Conn:
        def execute(self,sql,params):
            assert str(sql).strip().startswith('SELECT') and params['id']==33
            return Result()
    class Engine:
        def connect(self): return nullcontext(Conn())
    monkeypatch.setattr(database_module,'engine',Engine())
    monkeypatch.setattr(routes,'require_personnel_admin_or_403',lambda user:None)
    monkeypatch.setattr(routes,'get_published',lambda code:raw)
    for version in (None,33):
        result=routes.get_personnel_order_published_template_title('CONCURRENT_DUTY_START',{},version)
        assert result['title_ru']=='О совмещении' and result['title_kk']=='Қоса атқару туралы'
        assert not result['print_title_approval_required']
    assert raw['title_ru']=='О совмещении (простой, как по доп ставке)' and 'print_title_ru' not in raw


@pytest.mark.parametrize('code', list(PERSONNEL_ORDER_TEMPLATE_SPECS))
def test_every_type_uses_separate_official_headings_without_changing_internal_names(code):
    configured = dict(get_personnel_order_template_spec(code).initial_texts)
    template = {**configured, 'item_type_code':code,
                'print_title_ru':configured['title_ru'], 'print_title_kk':configured['title_kk'],
                'title_ru':configured['title_ru']+' (TEST internal explanation)',
                'title_kk':configured['title_kk']+' (TEST internal explanation)'}
    before = deepcopy(template)
    preview = preview_draft(code, {key:value for key,value in template.items() if key != 'item_type_code'})
    for locale in ('ru','kk'):
        assert preview[locale]['title'] == configured[f'title_{locale}']
        assert printable_template(template)[f'title_{locale}'] == configured[f'title_{locale}']
    # Exercise the same renderer used for new/added/regenerated order items.
    render_copy = {**template, 'body_template_ru':'TEST', 'body_template_kk':'TEST', 'basis_template_ru':'TEST', 'basis_template_kk':'TEST'}
    result = _render(render_copy, {}, draft_preview=True)
    assert result['title_ru'] == configured['title_ru']
    assert result['title_kk'] == configured['title_kk']
    assert template == before


def test_parentheses_in_an_explicit_official_title_are_not_removed():
    data = {'title_ru':'TEST internal (explanation)', 'title_kk':'TEST internal',
            'print_title_ru':'О приёме (по совместительству)', 'print_title_kk':'TEST official (approved fixture)'}
    assert printable_template(data)['title_ru'] == 'О приёме (по совместительству)'
    assert printable_template(data)['title_kk'] == data['print_title_kk']


def test_missing_kazakh_heading_requires_approval_without_inventing_translation():
    data = {'title_ru':'О совмещении (О замещении на время отпуска как доп ставка)',
            'title_kk':'TEST detailed internal name', 'print_title_ru':'О замещении', 'print_title_kk':None}
    assert print_title_errors(data) == ['Печатный заголовок KK: требуется согласование.']
    assert printable_template(data,preview=True)['title_ru'] == 'О замещении'
    assert 'согласование' in printable_template(data,preview=True)['title_kk']
    with pytest.raises(ValueError,match='KK.*согласование'):
        printable_template(data)


def test_order_snapshot_wins_over_later_directory_and_version_changes():
    configured = dict(get_personnel_order_template_spec('TRANSFER').initial_texts)
    version = {**configured,'print_title_ru':configured['title_ru'],'print_title_kk':configured['title_kk']}
    stored = json.loads(json.dumps(template_text_snapshot(version,TEXT_FIELDS)))
    changed = {**version, 'title_ru':'Changed internal name', 'print_title_ru':'Changed official title','print_title_kk':'Changed official KK'}
    for _ in range(2):
        pinned = pin_print_titles(changed,stored)
        assert printable_template(pinned)['title_ru'] == version['print_title_ru']
        assert printable_template(pinned)['title_kk'] == version['print_title_kk']
    assert stored['title_ru'] == configured['title_ru']


def test_legacy_order_keeps_its_actual_rendered_heading_when_a_new_title_is_approved():
    old = {'title_ru':'Historical title (including parentheses)', 'title_kk':'Historical KK'}
    rendered = {'title_ru':'Historical paper heading', 'title_kk':'Historical paper KK'}
    current = {'print_title_ru':'New approved title','print_title_kk':'New approved KK'}
    result = printable_template(pin_print_titles(current,old,rendered))
    assert result['title_ru'] == rendered['title_ru']
    assert result['title_kk'] == rendered['title_kk']


def test_new_binding_with_unapproved_headings_cannot_generate_a_document():
    configured = dict(get_personnel_order_template_spec('HIRE').initial_texts)
    data = pin_print_titles({**configured,'item_type_code':'HIRE'})
    with pytest.raises(TemplateApplicationError,match='согласование'):
        _render(data,{})


def test_bound_item_resolver_reads_the_order_snapshot_instead_of_current_template_titles():
    from app.services.personnel_order_item_templates import resolve_item_templates
    configured=dict(get_personnel_order_template_spec('HIRE').initial_texts)
    original={**configured,'print_title_ru':configured['title_ru'],'print_title_kk':configured['title_kk']}
    stored=template_text_snapshot(original,TEXT_FIELDS)
    current={**original,'template_version_id':7,'status':'ARCHIVED','name_ru':'Detailed internal name (TEST)',
             'print_title_ru':'Changed directory title','print_title_kk':'Changed KK'}
    class Result:
        def __init__(self,sql): self.sql=sql
        def mappings(self): return self
        def all(self): return [{'order_item_id':1,'template_version_id':7,'template_snapshot':stored,'rendered_snapshot':{'items':[{'order_item_id':1}]}}]
        def first(self): return current
    class Connection:
        def execute(self,sql,params):
            assert str(sql).lstrip().startswith('SELECT')
            return Result(str(sql))
    result=resolve_item_templates(Connection(),{'order_id':1,'selected_template_version_id':7},[{'item_id':1,'item_number':1,'item_type_code':'HIRE'}])[1]
    assert result['print_title_ru']==original['print_title_ru']
    assert result['print_title_kk']==original['print_title_kk']
    assert result['name_ru']==current['name_ru']


def test_manifest_round_trip_keeps_official_titles_separate_and_hashes_them(tmp_path):
    from app.services.personnel_order_template_manifest import build_manifest, _manifest_bytes, load_manifest, content_sha256
    configured=dict(get_personnel_order_template_spec('HIRE').initial_texts)
    data={**configured,'title_ru':'Detailed internal title (TEST)',
          'print_title_ru':configured['title_ru'],'print_title_kk':configured['title_kk']}
    manifest=build_manifest('HIRE',data)
    assert manifest['schema_version']==2
    path=tmp_path/'draft-v1.json';path.write_bytes(_manifest_bytes(manifest))
    reopened=load_manifest(path)
    assert reopened['print_title_ru']==configured['title_ru']
    assert reopened['title_ru']==data['title_ru']
    assert content_sha256('HIRE',data)!=content_sha256('HIRE',{**data,'print_title_ru':'Changed official title'})


def test_published_title_api_returns_print_headings_and_an_approval_notice_for_missing_kk(monkeypatch):
    from app.directory import personnel_orders_routes as routes
    configured=dict(get_personnel_order_template_spec('CONCURRENT_DUTY_START').initial_texts)
    template={**configured,'template_version_id':7,'item_type_code':'CONCURRENT_DUTY_START',
              'title_ru':'О совмещении (О замещении на время отпуска как доп ставка)',
              'print_title_ru':'О замещении','print_title_kk':None}
    monkeypatch.setattr(routes,'require_personnel_admin_or_403',lambda user:None)
    monkeypatch.setattr(routes,'get_published',lambda code:template)
    result=routes.get_personnel_order_published_template_title('CONCURRENT_DUTY_START',{},None)
    assert result['title_ru']=='О замещении'
    assert result['title_kk']==''
    assert result['print_title_approval_required']==['Печатный заголовок KK: требуется согласование.']
    assert template['title_ru'].endswith('(О замещении на время отпуска как доп ставка)')


@pytest.mark.parametrize('code',['HIRE','TRANSFER','CONCURRENT_DUTY_START'])
def test_copy_changes_only_internal_names_and_preserves_approved_source_headings(code,monkeypatch):
    from app.services import personnel_order_template_draft_service as service
    configured=dict(get_personnel_order_template_spec(code).initial_texts)
    source={**configured,'template_id':1,'template_version_id':1,'item_type_code':code,'version_number':1,
            'revision':1,'status':'PUBLISHED','based_on_built_in':True,'created_at':None,'updated_at':None,
            'print_title_ru':configured['title_ru'],'print_title_kk':configured['title_kk']}
    writes=[]
    class Result:
        def __init__(self,row): self.row=row
        def mappings(self): return self
        def first(self): return self.row
        def one(self): return self.row
        def scalar_one(self): return 2
    class Connection:
        def execute(self,sql,params):
            statement=str(sql).strip()
            if statement.startswith('SELECT'): return Result(source)
            assert statement.startswith('INSERT')
            writes.append((statement,dict(params)))
            return Result({**source,**{key:value for key,value in params.items() if key in source},'template_id':2,'template_version_id':2,'status':'DRAFT'})
    class Engine:
        def begin(self): return nullcontext(Connection())
    monkeypatch.setattr(service,'engine',Engine())
    monkeypatch.setattr(service,'require_independent_template_schema',lambda:None)
    result=service.copy_template(code,1,'TEST detailed internal (explanation)','TEST detailed KK (explanation)',1,1)
    assert result['title_ru']=='TEST detailed internal (explanation)'
    assert result['name_ru']==result['title_ru']
    assert result['print_title_ru']==source['print_title_ru']
    assert result['print_title_kk']==source['print_title_kk']
    assert source['status']=='PUBLISHED' and len(writes)==2


def test_new_working_version_inherits_approved_print_headings_when_an_older_client_only_renames_it(monkeypatch):
    from app.services import personnel_order_template_draft_service as service
    configured=dict(get_personnel_order_template_spec('HIRE').initial_texts)
    published={**configured,'template_id':1,'template_version_id':1,'item_type_code':'HIRE','version_number':1,
               'revision':1,'status':'PUBLISHED','based_on_built_in':True,'created_at':None,'updated_at':None,
               'print_title_ru':configured['title_ru'],'print_title_kk':configured['title_kk']}
    inserted={}
    class Result:
        def __init__(self,row): self.row=row
        def mappings(self): return self
        def first(self): return self.row
        def one(self): return self.row
    class Connection:
        def execute(self,sql,params):
            statement=str(sql).strip()
            if statement.startswith('SELECT'):
                return Result(None if "status='DRAFT'" in statement else published)
            if statement.startswith('INSERT'):
                inserted.update(params)
                return Result({**published,**params,'status':'DRAFT','template_version_id':2})
            return Result(published)
    class Engine:
        def begin(self): return nullcontext(Connection())
    monkeypatch.setattr(service,'engine',Engine())
    monkeypatch.setattr(service,'_resolve_template',lambda *a,**k:1)
    result=service.create_draft_from_working_copy.__wrapped__('HIRE','PUBLISHED',1,1,{**configured,'title_ru':'Detailed internal title (TEST)'},1,1)
    assert result['title_ru']=='Detailed internal title (TEST)'
    assert inserted['print_title_ru']==configured['title_ru']
    assert inserted['print_title_kk']==configured['title_kk']


def test_publication_requires_print_headings_and_renaming_a_draft_preserves_them(monkeypatch):
    from app.services import personnel_order_template_draft_service as service
    configured = dict(get_personnel_order_template_spec('HIRE').initial_texts)
    saved = {**configured, 'template_id':1,'template_version_id':1,'item_type_code':'HIRE','version_number':1,
             'revision':1,'status':'DRAFT','based_on_built_in':True,'created_at':None,'updated_at':None,
             'print_title_ru':configured['title_ru'],'print_title_kk':configured['title_kk']}
    writes=[]
    class Result:
        def mappings(self): return self
        def first(self): return saved
        def one(self): return saved
    class Connection:
        def execute(self,sql,params=None):
            sql=str(sql).strip()
            if sql.startswith('UPDATE public.personnel_order_template_versions SET title_ru'):
                writes.append(dict(params));saved.update({key:value for key,value in params.items() if key in saved})
            return Result()
    class Engine:
        def begin(self): return nullcontext(Connection())
    monkeypatch.setattr(service,'engine',Engine())
    monkeypatch.setattr(service,'_resolve_template',lambda *a,**k:1)
    values={**configured,'title_ru':'Detailed internal name (TEST)'}
    # Call the implementation under the schema compatibility boundary.
    result=service.save_draft.__wrapped__('HIRE',1,values,1,1)
    assert result['print_title_ru']==configured['title_ru']
    assert writes[0]['print_title_ru']==configured['title_ru']
    saved['print_title_kk']=None
    with pytest.raises(service.TemplateDraftError,match='KK.*согласование'):
        service.publish_draft.__wrapped__('HIRE',1,1,1)
