from app.services import personnel_order_draft_deletion_service as deletion
from app.services import personnel_order_quality_control_service as quality
from app.directory import personnel_orders_routes as routes
from fastapi import HTTPException
import pytest


def test_draft_delete_is_fail_closed_for_legal_dependencies_and_unknown_fk_tables():
    assert "employee_events" in deletion.BLOCKING_TABLES
    assert "personnel_order_template_applications" not in deletion.BLOCKING_TABLES
    assert "personnel_order_lifecycle_audit" in deletion.BLOCKING_TABLES
    assert "personnel_order_acknowledgement_events" in deletion.BLOCKING_TABLES
    assert "personnel_order_items" in deletion.ORDER_CHILD_ALLOWLIST
    assert "unknown_reference" not in deletion.ORDER_CHILD_ALLOWLIST


def test_draft_delete_requires_exact_order_scoped_confirmation_and_reason():
    try:
        deletion.execute(order_id=17, actor_user_id=1, reason="", confirmation_phrase="DELETE DRAFT ORDER 17")
    except deletion.DraftDeletionError as exc:
        assert exc.code == "DRAFT_ORDER_REASON_REQUIRED"
    else:
        raise AssertionError("missing reason must not open a transaction")
    try:
        deletion.execute(order_id=17, actor_user_id=1, reason="duplicate", confirmation_phrase="DELETE DRAFT ORDER 18")
    except deletion.DraftDeletionError as exc:
        assert exc.code == "DRAFT_ORDER_CONFIRMATION_REQUIRED"
    else:
        raise AssertionError("wrong confirmation must not open a transaction")


def test_privileged_all_status_delete_route_is_role_gated_and_uses_physical_delete(monkeypatch):
    monkeypatch.setattr(routes, "require_personnel_admin_or_403", lambda _user: None)
    calls = []
    monkeypatch.setattr(routes.draft_deletion, "execute_physical_delete", lambda **kwargs: calls.append(kwargs) or {"status": "PHYSICALLY_DELETED", "order_id": kwargs["order_id"]})
    result = routes.delete_personnel_order_hr_head_route(41, {"user_id": 7, "role_code": "HR_HEAD"})
    assert result == {"status": "PHYSICALLY_DELETED", "order_id": 41}
    assert calls == [{"order_id": 41}]
    assert routes.delete_personnel_order_hr_head_route(42, {"user_id": 7, "role_code": "ADMIN"}) == {"status": "PHYSICALLY_DELETED", "order_id": 42}
    with pytest.raises(HTTPException) as denied:
        routes.delete_personnel_order_hr_head_route(41, {"user_id": 8, "role_code": "HR_ADMIN"})
    assert denied.value.status_code == 403


def test_hr_head_delete_contract_does_not_apply_draft_status_scope_or_dependency_blockers():
    source = deletion.execute_hr_head.__doc__ or ""
    assert "does not undo operational effects" in source
    implementation = __import__("inspect").getsource(deletion.execute_hr_head)
    assert "_preview_tx" not in implementation
    assert "status='DRAFT'" not in implementation


def test_quality_control_uses_only_strict_live_rules_without_mutation(monkeypatch):
    statements: list[str] = []

    class Result:
        def scalar_one(self): return 1
        def mappings(self): return self
        def all(self): return [{"order_id": 9, "reasons": ["LEGACY_TECHNICAL_CANDIDATE"]}]
    class Connection:
        def execute(self, statement, _params=None):
            statements.append(str(statement)); return Result()
    class Context:
        def __enter__(self): return Connection()
        def __exit__(self, *_args): return False
    class Engine:
        def connect(self): return Context()
    monkeypatch.setattr(quality, "engine", Engine())
    result = quality.list_personnel_order_quality_issues(status="DRAFT", q="Ильясова")
    sql = "\n".join(statements)
    assert result["items"][0]["order_id"] == 9
    assert "CONFIRMED_TECHNICAL" in sql and "LEGACY_TECHNICAL_CANDIDATE" in sql
    assert "MISSING_DISPLAY_TITLE" in sql and "DAMAGED_DISPLAY_TITLE" in sql
    assert "po.status = :status" in sql and "ILIKE :q" in sql
    assert all(statement.lstrip().upper().startswith("SELECT") for statement in statements)
