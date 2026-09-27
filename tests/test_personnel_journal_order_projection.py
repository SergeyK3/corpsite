from contextlib import contextmanager
from datetime import date

from app.services import directory_service


class Result:
    def __init__(self, value): self.value = value
    def mappings(self): return self
    def first(self): return self.value
    def all(self): return self.value


def event_row(**overrides):
    row = {"event_id": 1, "employee_id": 2, "employee_name": "Employee", "event_type": "HIRE", "event_class": "EMPLOYMENT", "lifecycle_status": "APPROVED", "metadata": None, "effective_date": "2026-09-01", "from_org_unit_id": None, "from_org_unit_name": None, "to_org_unit_id": None, "to_org_unit_name": None, "from_position_id": None, "from_position_name": None, "to_position_id": None, "to_position_name": None, "from_rate": None, "to_rate": None, "order_ref": None, "order_id": 11, "order_item_id": 12, "order_number": "11-K", "comment": None}
    row.update(overrides)
    return row


def enable_projection(monkeypatch, events, drafts, candidates=None):
    class Connection:
        def execute(self, statement, *_args, **_kwargs):
            sql = str(statement)
            if "COUNT(*)" in sql: return Result({"cnt": len(events)})
            if "candidate_has_linked_event" in sql: return Result(candidates or [])
            if "FROM public.personnel_order_items" in sql: return Result(drafts)
            return Result(events)
    class Engine:
        @contextmanager
        def begin(self): yield Connection()
    monkeypatch.setattr(directory_service, "engine", Engine())
    monkeypatch.setattr(directory_service, "_employee_events_order_columns_available", lambda: True)
    monkeypatch.setattr(directory_service, "personnel_orders_available", lambda: True)


def temporary_item(**overrides):
    item = {
        "order_item_id": 19,
        "item_type_code": "RETURN_FROM_CHILDCARE_LEAVE",
        "effective_date": date(2026, 9, 2),
        "order_id": 11,
        "order_number": "11-K",
        "order_status": "DRAFT",
        "employee_id": 2,
        "employee_name": "Employee",
        "org_unit_id": None,
        "org_unit_name": None,
        "position_id": None,
        "position_name": None,
        "employment_rate": None,
    }
    item.update(overrides)
    return item


def import_candidate(**overrides):
    candidate = {
        "employee_id": 2,
        "candidate_order_id": 11,
        "candidate_order_number": "11-K",
        "candidate_order_status": "DRAFT",
        "candidate_has_linked_event": False,
    }
    candidate.update(overrides)
    return candidate


def import_event(**overrides):
    return event_row(
        event_id=7,
        employee_id=2,
        event_type="EMPLOYEE_ENROLLED_FROM_IMPORT",
        order_id=None,
        order_item_id=None,
        order_number=None,
        **overrides,
    )


def test_personnel_journal_projects_linked_order_number(monkeypatch):
    enable_projection(monkeypatch, [event_row()], [])
    result = directory_service.list_personnel_events()
    assert result["items"][0]["order_id"] == 11
    assert result["items"][0]["order_item_id"] == 12
    assert result["items"][0]["order_number"] == "11-K"


def test_unapplied_item_is_separate_from_unlinked_import_event(monkeypatch):
    draft = temporary_item()
    enable_projection(monkeypatch, [import_event()], [draft])
    result = directory_service.list_personnel_events()
    temporary = next(item for item in result["items"] if item.get("is_temporary"))
    historical = next(item for item in result["items"] if not item.get("is_temporary"))
    assert temporary["order_item_id"] == 19
    assert temporary["order_id"] == 11
    assert historical["event_id"] == 7
    assert historical["order_id"] is None
    assert historical["import_order_preparation"] == {"state": "NOT_PREPARED"}


def test_import_event_without_candidate_reports_not_prepared(monkeypatch):
    enable_projection(monkeypatch, [import_event()], [])
    result = directory_service.list_personnel_events()
    item = result["items"][0]
    assert item["order_id"] is None
    assert item["order_item_id"] is None
    assert item["import_order_preparation"] == {"state": "NOT_PREPARED"}


def test_import_event_with_one_draft_reports_registration_needed(monkeypatch):
    enable_projection(monkeypatch, [import_event()], [], [import_candidate()])
    item = directory_service.list_personnel_events()["items"][0]
    assert item["order_id"] is None
    assert item["import_order_preparation"] == {
        "state": "DRAFT", "candidate_order_id": 11, "candidate_order_number": "11-K"
    }


def test_import_event_with_one_registered_order_reports_apply_needed(monkeypatch):
    enable_projection(
        monkeypatch,
        [import_event()],
        [],
        [import_candidate(candidate_order_status="REGISTERED")],
    )
    item = directory_service.list_personnel_events()["items"][0]
    assert item["import_order_preparation"]["state"] == "PENDING_APPLY"


def test_import_event_with_event_linked_by_item_reports_applied(monkeypatch):
    enable_projection(
        monkeypatch,
        [import_event()],
        [],
        [import_candidate(candidate_order_status="SIGNED", candidate_has_linked_event=True)],
    )
    item = directory_service.list_personnel_events()["items"][0]
    assert item["import_order_preparation"]["state"] == "APPLIED"


def test_import_event_with_multiple_candidates_stays_ambiguous(monkeypatch):
    enable_projection(
        monkeypatch,
        [import_event()],
        [],
        [import_candidate(), import_candidate(candidate_order_id=12, candidate_order_number="12-K")],
    )
    item = directory_service.list_personnel_events()["items"][0]
    assert item["order_id"] is None
    assert item["import_order_preparation"] == {"state": "AMBIGUOUS"}


def test_import_event_ignores_candidate_for_another_employee(monkeypatch):
    enable_projection(monkeypatch, [import_event()], [], [import_candidate(employee_id=3)])
    item = directory_service.list_personnel_events()["items"][0]
    assert item["import_order_preparation"] == {"state": "NOT_PREPARED"}


def test_temporary_item_query_accepts_only_manual_active_process_orders(monkeypatch):
    captured_sql = []

    class Connection:
        def execute(self, statement, *_args, **_kwargs):
            captured_sql.append(str(statement))
            return Result([])

    class Engine:
        @contextmanager
        def begin(self):
            yield Connection()

    monkeypatch.setattr(directory_service, "engine", Engine())
    assert directory_service._list_unapplied_personnel_order_items(scope_unit_ids=None) == []
    sql = captured_sql[0]
    assert "poi.item_status = 'ACTIVE'" in sql
    assert "po.source_mode = 'MANUAL'" in sql
    assert "po.status IN ('DRAFT', 'REGISTERED', 'SIGNED')" in sql
    assert "applied.order_item_id = poi.item_id" in sql


def test_paper_item_is_not_projected_after_query_filtering(monkeypatch):
    # The database predicate excludes PAPER; the mock returns only SQL-filtered rows.
    enable_projection(monkeypatch, [], [])
    result = directory_service.list_personnel_events()
    assert result == {"items": [], "total": 0}


def test_registered_and_signed_items_remain_temporary_candidates(monkeypatch):
    drafts = [
        temporary_item(order_item_id=20, order_status="REGISTERED"),
        temporary_item(order_item_id=21, order_status="SIGNED"),
    ]
    enable_projection(monkeypatch, [], drafts)
    result = directory_service.list_personnel_events()
    assert {(item["order_item_id"], item["order_status"]) for item in result["items"]} == {
        (20, "REGISTERED"),
        (21, "SIGNED"),
    }


def test_item_with_matching_order_item_event_is_not_projected(monkeypatch):
    # The NOT EXISTS predicate removes an applied item before projection.
    enable_projection(monkeypatch, [event_row(order_id=11)], [])
    result = directory_service.list_personnel_events()
    assert not any(item.get("is_temporary") for item in result["items"])
