from app.services.personnel_order_template_catalog_service import list_personnel_order_template_catalog
from app.main import app
from app.security.admin_guard import require_sysadmin_api
from fastapi.testclient import TestClient


def test_catalog_is_registry_backed_and_safe():
    items = list_personnel_order_template_catalog()
    codes = {item["type_code"] for item in items}
    assert {"HIRE", "TRANSFER", "TERMINATION", "LEAVE.ANNUAL.GRANT", "LEAVE.UNPAID.GRANT", "LEAVE.CHILDCARE.GRANT", "RETURN_FROM_CHILDCARE_LEAVE", "CONCURRENT_DUTY_START", "CONCURRENT_DUTY_END", "SUPPLEMENTARY_PAY"} <= codes
    assert "COMPOSITE" not in codes
    pilot = next(item for item in items if item["type_code"] == "RETURN_FROM_CHILDCARE_LEAVE")
    assert pilot["is_pilot"] is True and pilot["support_level"] == "SUPPORTED"
    assert all(set(item) == {"type_code", "title_ru", "title_kk", "source", "support_level", "supported_locales", "uses_specialized_generator", "is_pilot", "required_fields", "notes"} for item in items)


def test_catalog_endpoint_requires_existing_admin_guard():
    app.dependency_overrides[require_sysadmin_api] = lambda: {"user_id": 2, "role_id": 2}
    try:
        response = TestClient(app).get("/admin/personnel-order-templates")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert "payload" not in response.text and "employee_id" not in response.text

    assert TestClient(app).get("/admin/personnel-order-templates").status_code in {401, 403}
