"""Read-only contract tests; no employees/orders/reference data are mutated."""
from app.services import directory_service as service
from app.services.org_units_service import OrgUnitsService
from contextlib import nullcontext


def test_assignment_projection_keeps_translations_and_unit_on_same_assignment(monkeypatch):
    monkeypatch.setattr(service, '_list_relations', lambda: [('person_assignments', 'table')])
    monkeypatch.setattr(service, '_positions_relation', lambda: ('positions', ['position_id','name','name_kk']))
    monkeypatch.setattr(service, '_departments_relation', lambda: (None, []))
    sql, _ = service._employee_select_sql('employees', ['employee_id','person_id','full_name','position_id','org_unit_id'])
    assert 'pa.assignment_id, pa.position_id, pa.org_unit_id' in sql
    assert "CASE WHEN current_pa.assignment_id IS NOT NULL THEN to_jsonb(current_p) ELSE to_jsonb(p) END" in sql
    assert "AS pos_name_kk" in sql
    assert "AS pos_document_possessive_kk" in sql
    assert "THEN current_pa.org_unit_id ELSE e.org_unit_id END" in sql
    assert 'pa.person_id = e.person_id' in sql


def test_dto_preserves_reference_fields_and_missing_translation():
    base = {'e_id': 777, 'e_pos_id': 44, 'pos_name': 'сестра-хозяйка', 'pos_name_kk': 'шаруа бикесі',
            'e_org_unit_id': 98, 'org_unit_name': 'Отделение', 'org_unit_name_kk': 'Бөлімше',
            'org_unit_document_genitive_kk': 'Бөлімшенің'}
    dto = service._normalize_employee_joined(base, 'employees')
    assert dto['id'] == '777'
    assert dto['position']['name_kk'] == 'шаруа бикесі'
    assert dto['org_unit']['unit_id'] == 98
    assert dto['org_unit']['document_genitive_kk'] == 'Бөлімшенің'
    assert service._normalize_employee_joined({**base, 'pos_name_kk': None}, 'employees')['position']['name_kk'] is None


def test_org_unit_select_keeps_both_reference_fields_without_writes():
    class Db:
        def begin(self): return nullcontext(self)
        def execute(self, statement, params):
            assert str(statement).lstrip().startswith('SELECT')
            assert "'name_kk'" in str(statement) and "'document_genitive_kk'" in str(statement)
            assert params == {'unit_id': 9}
            return self
        def mappings(self): return self
        def first(self): return {'unit_id':9,'parent_unit_id':None,'name':'Отделение','name_kk':'Бөлімше','document_genitive_kk':'Бөлімшенің','code':'TEST','group_id':1,'is_active':True}
    unit = OrgUnitsService(Db()).get_org_unit(unit_id=9)
    assert unit.name_kk == 'Бөлімше' and unit.document_genitive_kk == 'Бөлімшенің'
