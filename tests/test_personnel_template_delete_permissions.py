from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.main import app
from app.security import admin_guard
from app.api import admin_router


def test_delete_requires_template_management_backend_guard(monkeypatch):
    called = []
    monkeypatch.setattr(admin_router, "remove_template", lambda *args, **kwargs: called.append(args))
    monkeypatch.setattr(admin_guard, "evaluate_admin_access", lambda user: False)
    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_current_user] = lambda: {"user_id": 999999, "role_id": 3}
    try:
        response = TestClient(app).request("DELETE", "/admin/personnel-order-templates/HIRE/templates/99", json={"name_ru": "TEST", "name_kk": "TEST KK"})
        assert response.status_code == 403
        assert not called
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
