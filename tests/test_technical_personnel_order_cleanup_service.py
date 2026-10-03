import pytest

from app.services import technical_personnel_order_cleanup_service as service


def test_technical_order_requires_two_machine_readable_markers_not_a_number_prefix():
    clause = service._technical_clause()
    assert "technical_record" in clause
    assert "record_quality" in clause
    assert "order_number" not in clause
    assert "PERSONNEL-IMPORT" not in clause


@pytest.mark.parametrize("confirmation", ["", "DELETE TECHNICAL ORDER 99", "DELETE TECHNICAL ORDER 101"])
def test_execute_rejects_non_exact_confirmation_without_opening_transaction(confirmation):
    with pytest.raises(service.TechnicalOrderCleanupError) as exc:
        service.execute(order_id=100, actor_user_id=1, reason="test cleanup", confirmation_phrase=confirmation)
    assert exc.value.code == "TECHNICAL_ORDER_CONFIRMATION_REQUIRED"


def test_allowlists_do_not_include_employee_events_or_template_audit():
    allowed = service.ORDER_CHILD_ALLOWLIST | service.ITEM_CHILD_ALLOWLIST
    assert "employee_events" not in allowed
    assert "personnel_order_template_applications" not in allowed
    assert "employee_events" in service.BLOCKING_TABLES


def test_three_way_classification_keeps_legacy_visible_but_not_confirmed():
    assert service.classification({"technical_record": True, "record_quality": "TECHNICAL_RECORD"}, "PERSONNEL-IMPORT-2026-273") == service.CONFIRMED_TECHNICAL
    assert service.classification({}, "PERSONNEL-IMPORT-2026-273") == service.LEGACY_TECHNICAL_CANDIDATE
    assert service.classification({}, "273-Ж") == service.REGULAR


def test_routes_require_the_dedicated_system_admin_permission(monkeypatch):
    from fastapi.testclient import TestClient
    from app.auth import get_current_user
    from app.main import app
    from app.directory import technical_personnel_order_cleanup_routes as routes

    monkeypatch.setattr(routes, "has_technical_personnel_order_cleanup_permission", lambda _uid: False)
    app.dependency_overrides[get_current_user] = lambda: {"user_id": 991}
    try:
        response = TestClient(app).get("/directory/technical-personnel-order-cleanup/search", params={"order_id": 1})
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "TECHNICAL_ORDER_CLEANUP_PERMISSION_REQUIRED"
    finally:
        app.dependency_overrides.pop(get_current_user, None)
