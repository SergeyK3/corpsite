# tests/test_hr_event_registry.py
from __future__ import annotations

from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.hr_event_registry import (
    HR_EVENT_REGISTRY,
    PHASE_1A_CREATABLE,
    get_event_class,
    get_event_def,
    get_event_label,
    is_creatable_in_phase_1a,
    list_registry_for_ui,
)
from tests.conftest import auth_headers


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


def test_registry_contains_phase_1a_types():
    for code in ("TRANSFER", "POSITION_CHANGE", "RATE_CHANGE", "CORRECTION"):
        assert code in HR_EVENT_REGISTRY


def test_registry_event_classes():
    assert get_event_class("TRANSFER") == "EMPLOYMENT"
    assert get_event_class("POSITION_CHANGE") == "EMPLOYMENT"
    assert get_event_class("RATE_CHANGE") == "EMPLOYMENT"
    assert get_event_class("CORRECTION") == "CORRECTION"
    assert get_event_class("BONUS") == "PERSONNEL"


def test_registry_label_ru_present():
    for code in ("TRANSFER", "POSITION_CHANGE", "RATE_CHANGE", "CORRECTION"):
        label = get_event_label(code)
        assert isinstance(label, str)
        assert label.strip()


def test_deferred_types_not_creatable_in_phase_1a():
    assert not is_creatable_in_phase_1a("BONUS")
    assert not is_creatable_in_phase_1a("ANNUAL_LEAVE")
    assert not is_creatable_in_phase_1a("HIRE")
    assert is_creatable_in_phase_1a("TRANSFER")


def test_list_registry_for_ui_marks_supported():
    items = {x["code"]: x for x in list_registry_for_ui()}
    assert items["TRANSFER"]["supported_in_phase_1a"] is True
    assert items["BONUS"]["supported_in_phase_1a"] is False
    assert items["TRANSFER"]["event_class"] == "EMPLOYMENT"


def test_get_hr_event_registry_route(client: TestClient, privileged_headers):
    resp = client.get("/directory/hr-event-registry", headers=privileged_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    codes = {x["code"] for x in body["items"]}
    assert "TRANSFER" in codes
    assert "POSITION_CHANGE" in codes
    assert "RATE_CHANGE" in codes
