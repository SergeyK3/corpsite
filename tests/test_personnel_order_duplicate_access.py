"""Duplicate actions must follow the order-detail read policy, including 409 races."""
from copy import deepcopy

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.directory import personnel_orders_routes as routes
from app.services.personnel_order_document_header_service import PersonnelOrderDuplicateError


@pytest.fixture
def api(monkeypatch):
    duplicate = {"blocking": True, "warnings": [], "candidates": [{
        "order_id": 5647, "order_number": "2 тест", "order_date": "2026-01-05",
        "order_type_code": "COMPOSITE", "status": "DRAFT", "record_quality": "WORKING",
        "is_conflict": True, "can_open": False,
    }]}
    actor = {"user_id": 1, "can_read": True}
    def require_read(user):
        if not user.get("can_read"):
            raise HTTPException(status_code=403, detail="Personnel admin access required.")
    monkeypatch.setattr(routes, "require_personnel_admin_or_403", require_read)
    monkeypatch.setattr(routes, "duplicate_preview", lambda **kwargs: deepcopy(duplicate))
    app = FastAPI()
    app.include_router(routes.router, prefix="/directory")
    app.dependency_overrides[get_current_user] = lambda: actor
    with TestClient(app) as client:
        yield client, actor, duplicate


def test_duplicate_preview_grants_open_only_after_order_read_policy(api):
    client, actor, duplicate = api
    result = client.post("/directory/personnel-orders/header-duplicate-preview", json={"order_number": "2 тест", "order_date": "2026-01-05"})
    assert result.status_code == 200, result.text
    assert result.json()["blocking"]
    assert result.json()["candidates"][0]["can_open"] is True
    assert duplicate["candidates"][0]["can_open"] is False
    actor["can_read"] = False
    assert client.post("/directory/personnel-orders/header-duplicate-preview", json={"order_number": "2 тест", "order_date": "2026-01-05"}).status_code == 403
    assert client.get("/directory/personnel-orders/5647").status_code == 403


def test_transactional_duplicate_conflict_preserves_the_open_action(api, monkeypatch):
    client, actor, duplicate = api
    def reject(**kwargs):
        raise PersonnelOrderDuplicateError(deepcopy(duplicate))
    monkeypatch.setattr(routes, "create_manual_draft", reject)
    result = client.post("/directory/personnel-orders/manual-draft", json={
        "order_number": "2 тест", "order_date": "2026-01-05", "source_title": "SYNTHETIC HIRE",
        "source_title_locale": "ru", "item_type_code": "HIRE", "employee_id": None,
        "unresolved_subject": {"full_name": "SYNTHETIC APPLICANT"}, "effective_date": "2026-01-05",
    })
    assert result.status_code == 409, result.text
    assert result.json()["detail"]["code"] == "DUPLICATE_ORDER_NUMBER_DATE"
    assert result.json()["detail"]["duplicate"]["candidates"][0]["can_open"] is True


def test_service_conflict_without_authenticated_reader_never_grants_open(api):
    _, actor, duplicate = api
    assert routes._conflict_http409(PersonnelOrderDuplicateError(duplicate)).detail["duplicate"]["candidates"][0]["can_open"] is False
    actor["can_read"] = False
    assert routes._conflict_http409(PersonnelOrderDuplicateError(duplicate), actor).detail["duplicate"]["candidates"][0]["can_open"] is False
