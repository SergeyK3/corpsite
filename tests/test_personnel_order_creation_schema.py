"""No database writes: old-schema authoring SQL and independent optional features."""
from contextlib import nullcontext
from datetime import date
import pytest
from app.services import personnel_order_manual_draft_service as manual
from app.services.personnel_order_creation_schema import creation_capabilities
from app.services.personnel_orders_query_service import PersonnelOrderValidationError


class Result:
    def __init__(self,row=None):self.row=row
    def mappings(self):return self
    def first(self):return self.row
    def one(self):return self.row
    def one_or_none(self):return self.row
    def scalar_one(self):return 99


class Connection:
    def __init__(self):self.statements=[]
    def execute(self,sql,values=None):
        self.statements.append(str(sql))
        return Result({'full_name':'Тестов Тест','position_name':'врач','org_unit_name':'Терапия'})


@pytest.fixture
def legacy_authoring(monkeypatch):
    conn=Connection();generated=[];applied=[]
    class Engine:
        def begin(self):return nullcontext(conn)
    monkeypatch.setattr(manual,'engine',Engine())
    monkeypatch.setattr(manual,'duplicate_preview',lambda **kwargs:{'blocking':False})
    monkeypatch.setattr(manual,'creation_capabilities',lambda c,code:{'creation_supported':True,'independent_supported':False,'job_catalog_supported':False})
    monkeypatch.setattr(manual,'create_personnel_order_evidence_scope_tx',lambda *args,**kwargs:None)
    monkeypatch.setattr(manual,'generate_editorial',lambda *args,**kwargs:generated.append(args))
    from app.services import personnel_order_template_application_service as templates
    monkeypatch.setattr(templates,'apply_template_application_tx',lambda *args,**kwargs:applied.append(args))
    return conn,generated,applied


def create(**overrides):
    values=dict(created_by=25,order_number='UNIT-ONLY',order_date=date(2026,10,7),source_title='О трудовом отпуске',source_title_locale='ru',item_type_code='LEAVE.ANNUAL.GRANT',employee_id=1,effective_date=date(2026,10,12),document_subject_context={'position_name':'врач','org_unit_name':'Терапия'})
    values.update(overrides);return manual.create_manual_draft(**values)


def test_legacy_creation_uses_existing_columns_employee_reader_and_generator(legacy_authoring):
    conn,generated,applied=legacy_authoring
    result=create()
    assert result['order_id']==99 and result['status']=='DRAFT'
    assert generated and not applied
    assert any('INSERT INTO personnel_orders' in sql for sql in conn.statements)
    assert all('selected_template_version_id' not in sql and 'job_positions_catalog' not in sql and 'personnel_order_templates' not in sql for sql in conn.statements)
    assert all('employee_events' not in sql for sql in conn.statements)


def test_legacy_explicit_variant_never_silently_falls_back(legacy_authoring):
    conn,generated,applied=legacy_authoring
    with pytest.raises(PersonnelOrderValidationError,match='hrtpl001'):create(template_version_id=50)
    assert not any('INSERT' in sql for sql in conn.statements)
    assert not generated and not applied


def test_recall_schema_guard_runs_before_any_insert(legacy_authoring,monkeypatch):
    conn,generated,applied=legacy_authoring
    monkeypatch.setattr(manual,'creation_capabilities',lambda c,code:{'creation_supported':False,'creation_reason':'LEAVE.ANNUAL.RECALL requires hrrecall001'})
    with pytest.raises(PersonnelOrderValidationError,match='hrrecall001'):create(item_type_code='LEAVE.ANNUAL.RECALL')
    assert not conn.statements and not generated


def test_independent_insertion_keeps_the_exact_version_link():
    conn=Connection()
    assert manual._insert_manual_order(conn,{},supports_selection=True)==99
    assert 'selected_template_version_id' in conn.statements[0] and ':template_version' in conn.statements[0]


@pytest.mark.parametrize('kind,supported',[('LEAVE.ANNUAL.GRANT',True),('LEAVE.UNPAID.GRANT',True),('LEAVE.ANNUAL.RECALL',False)])
def test_capabilities_follow_both_real_constraints_without_ddl(kind,supported):
    class Conn(Connection):
        def execute(self,sql,values=None):
            self.statements.append(str(sql))
            return Result({'identities':False,'selected_version':False,'job_catalog':False,'order_codes':"CHECK (code IN ('LEAVE.ANNUAL.GRANT','LEAVE.UNPAID.GRANT'))",'item_codes':"CHECK (code IN ('LEAVE.ANNUAL.GRANT','LEAVE.UNPAID.GRANT'))"})
    conn=Conn();result=creation_capabilities(conn,kind)
    assert result['creation_supported'] is supported
    assert result['independent_supported'] is False and result['schema_mode']=='LEGACY'
    assert all(sql.lstrip().startswith('SELECT') for sql in conn.statements)
