"""Existing editors remain usable without migrating or writing the working DB."""
from contextlib import nullcontext
from datetime import datetime,timezone
import pytest
from app.services import personnel_order_template_draft_service as templates
from app.services import personnel_order_template_legacy_service as legacy
from app.services.personnel_order_template_specs import get_personnel_order_template_spec
from app.api.admin_router import _template_draft_error


class Store:
    def __init__(self):
        self.statements=[]
        self.row={'template_version_id':7,'item_type_code':'RETURN_FROM_CHILDCARE_LEAVE','status':'DRAFT','revision':3,'version_number':1,'based_on_built_in':True,'created_at':datetime.now(timezone.utc),'updated_at':datetime.now(timezone.utc),**get_personnel_order_template_spec('RETURN_FROM_CHILDCARE_LEAVE').initial_texts}
    def connect(self):return nullcontext(self)
    def begin(self):return nullcontext(self)
    def execute(self,query,params=None):
        sql=str(query);self.statements.append(sql);params=params or {}
        if sql.lstrip().startswith('UPDATE'):
            self.row.update({key:params[key] for key in templates.TEXT_FIELDS});self.row['revision']+=1
        row=self.row if "status='PUBLISHED'" not in sql else None
        class Result:
            def mappings(self):return self
            def first(self):return row
            def one(self):return row
        return Result()


@pytest.fixture
def old_schema(monkeypatch):
    store=Store()
    monkeypatch.setattr(templates,'independent_template_schema_available',lambda:False)
    monkeypatch.setattr(legacy,'engine',store)
    return store


def test_old_schema_reads_real_eight_fields_without_independent_scope(old_schema):
    draft=templates.get_draft('RETURN_FROM_CHILDCARE_LEAVE')
    assert draft['template_id'] is None and draft['template_version_id']==7
    assert all(draft[field]==old_schema.row[field] for field in templates.TEXT_FIELDS)
    assert templates.get_published('RETURN_FROM_CHILDCARE_LEAVE') is None
    base=templates.get_editor_base('RETURN_FROM_CHILDCARE_LEAVE')
    assert base['source']=='INITIAL'
    assert all('personnel_order_templates' not in sql and 'template_id' not in sql for sql in old_schema.statements)
    assert all(sql.lstrip().startswith('SELECT') for sql in old_schema.statements)


def test_old_schema_save_keeps_noop_and_exact_revision_guards(old_schema):
    texts={field:old_schema.row[field] for field in templates.TEXT_FIELDS}
    with pytest.raises(templates.TemplateDraftError):
        templates.save_draft('RETURN_FROM_CHILDCARE_LEAVE',3,texts,25,expected_template_version_id=8)
    assert not any(sql.lstrip().startswith('UPDATE') for sql in old_schema.statements)
    texts['body_template_ru']='Incomplete but safely saved draft {{employee.full_name}}'
    saved=templates.save_draft('RETURN_FROM_CHILDCARE_LEAVE',3,texts,25,expected_template_version_id=7)
    assert saved['revision']==4 and saved['body_template_ru']==texts['body_template_ru']
    assert templates.save_draft('RETURN_FROM_CHILDCARE_LEAVE',4,texts,25)['revision']==4
    with pytest.raises(templates.TemplateDraftError):templates.save_draft('RETURN_FROM_CHILDCARE_LEAVE',3,texts,25)


def test_old_schema_never_ignores_an_independent_template_id(old_schema):
    with pytest.raises(templates.TemplateDraftError) as cause:templates.get_draft('LEAVE.UNPAID.GRANT',101)
    assert cause.value.code=='TEMPLATE_SCHEMA_REQUIRED'
    assert _template_draft_error(cause.value).status_code==503
    assert old_schema.statements==[]


def test_old_schema_blocks_copy_and_recall_persistence_with_concrete_reason(old_schema):
    with pytest.raises(templates.TemplateDraftError,match='hrrecall001'):
        templates.copy_template('LEAVE.UNPAID.GRANT',None,'RU','KZ',25,None,base_source='INITIAL')
    with pytest.raises(templates.TemplateDraftError,match='hrrecall001'):
        templates.create_draft_from_working_copy('LEAVE.ANNUAL.RECALL','INITIAL',None,None,dict(get_personnel_order_template_spec('LEAVE.ANNUAL.RECALL').initial_texts),25)
    assert old_schema.statements==[]
