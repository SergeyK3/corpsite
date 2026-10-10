from contextlib import nullcontext

from app.services import directory_service as directory


def test_optional_assignment_read_excludes_primary_and_respects_scope(monkeypatch):
    class Store:
        def __init__(self):
            self.statements = []
        def begin(self):
            return nullcontext(self)
        def execute(self, query, params):
            sql = str(query)
            self.statements.append(sql)
            class Result:
                def mappings(self):
                    return self
                def first(self):
                    return dict(e_person_id=10, e_id=1)
                def all(self):
                    return [dict(assignment_id=i, is_primary=primary, org_unit_id=unit, position_id=6, rate=rate, position={}, org_unit={}) for i, primary, unit, rate in ((1, True, 59, 1), (2, False, 59, 0.5), (3, False, 60, 0.25))]
            return Result()
    store = Store()
    monkeypatch.setattr(directory, "engine", store)
    monkeypatch.setattr(directory, "_employees_relation", lambda: ("employees", ["employee_id", "org_unit_id"]))
    monkeypatch.setattr(directory, "_employee_select_sql", lambda *args: ("SELECT e.* FROM employees e", {}))
    monkeypatch.setattr(directory, "_list_relations", lambda: [("person_assignments", "table")])
    monkeypatch.setattr(directory, "_normalize_employee_joined", lambda *args: {"id": "1"})
    monkeypatch.setattr(directory, "_fetch_linked_user", lambda *args: None)
    monkeypatch.setattr(directory, "build_dept_scope_cte", lambda **kwargs: ("", "", {}))
    result = directory.get_employee(employee_id="1", include_assignments=True, scope_unit_ids=[59])
    assert result["active_assignment_id"] == 1
    assert [row["assignment_id"] for row in result["additional_assignments"]] == [2]
    assert all(sql.lstrip().startswith("SELECT") for sql in store.statements)
    assert "pa.active_flag IS TRUE" in store.statements[-1]
    assert "pa.start_date<=CURRENT_DATE" in store.statements[-1]
    assert "pa.end_date>=CURRENT_DATE" in store.statements[-1]
