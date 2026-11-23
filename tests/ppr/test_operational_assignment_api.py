"""Focused HTTP contract tests for the Person-rooted operational assignment read."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api import ppr_router
from app.auth import get_current_user
from app.main import app


@pytest.fixture
def client(monkeypatch):
    """Use a read-capable user without the card-correction grant.

    The route must be protected by the PPR read/visibility gate, not by
    ``PERSONNEL_CARD_EDIT``.  The production services are replaced only at
    the HTTP boundary so these tests neither depend on nor mutate data.
    """
    user = {"user_id": 101, "has_personnel_card_edit": False}
    app.dependency_overrides[get_current_user] = lambda: user
    monkeypatch.setattr(ppr_router, "assert_ppr_read_path_activation_allowed", lambda: None)
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)


def _stub_authorized_person(monkeypatch, *, person_id: int = 41, employee_id: int | None = 71) -> list[tuple[int, int | None]]:
    checked: list[tuple[int, int | None]] = []
    monkeypatch.setattr(
        ppr_router._query_service,
        "load_by_person_id",
        lambda route_person_id: SimpleNamespace(person_id=person_id, employee_id=employee_id),
    )

    def allow_read(_user, resolved_person_id: int, *, resolved_employee_id: int | None = None) -> None:
        checked.append((resolved_person_id, resolved_employee_id))

    monkeypatch.setattr(ppr_router, "assert_ppr_read_allowed_for_person", allow_read)
    return checked


def test_operational_assignment_returns_projection_by_route_person_id(client, monkeypatch) -> None:
    checked = _stub_authorized_person(monkeypatch)
    projection_calls: list[int] = []

    def projection(_user, person_id: int) -> dict:
        projection_calls.append(person_id)
        return {
            "has_assignment": True,
            "department_group_name": "Clinical group",
            "org_unit_name": "Long unit name",
            "position_name": "Long position name",
            "status": "Active",
            "employment_rate": "1.0",
        }

    monkeypatch.setattr(ppr_router, "load_current_operational_assignment_for_person", projection)

    response = client.request(
        "GET",
        "/api/ppr/persons/41/operational-assignment?employee_id=999",
        json={"person_id": 998, "employee_id": 997},
    )

    assert response.status_code == 200
    assert response.json()["has_assignment"] is True
    assert checked == [(41, 71)]
    assert projection_calls == [41]


def test_operational_assignment_returns_empty_state_when_absent(client, monkeypatch) -> None:
    _stub_authorized_person(monkeypatch)
    monkeypatch.setattr(
        ppr_router,
        "load_current_operational_assignment_for_person",
        lambda _user, _person_id: {"has_assignment": False},
    )

    response = client.get("/api/ppr/persons/41/operational-assignment")

    assert response.status_code == 200
    assert response.json() == {
        "has_assignment": False,
        "department_group_name": None,
        "org_unit_name": None,
        "position_name": None,
        "status": None,
        "employment_rate": None,
    }


@pytest.mark.parametrize("code", ["ACTIVE_EMPLOYEE_CARDINALITY_INVALID", "ACTIVE_ASSIGNMENT_CARDINALITY_INVALID"])
def test_operational_assignment_preserves_controlled_cardinality_conflicts(client, monkeypatch, code: str) -> None:
    _stub_authorized_person(monkeypatch)

    def conflict(_user, _person_id: int) -> dict:
        raise HTTPException(status_code=409, detail={"code": code, "message": "ambiguous"})

    monkeypatch.setattr(ppr_router, "load_current_operational_assignment_for_person", conflict)

    response = client.get("/api/ppr/persons/41/operational-assignment")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == code


def test_operational_assignment_rejects_unauthenticated_request(monkeypatch) -> None:
    monkeypatch.setattr(ppr_router, "assert_ppr_read_path_activation_allowed", lambda: None)
    app.dependency_overrides.pop(get_current_user, None)

    response = TestClient(app).get("/api/ppr/persons/41/operational-assignment")

    assert response.status_code == 401


def test_operational_assignment_denies_person_outside_visibility_scope(client, monkeypatch) -> None:
    monkeypatch.setattr(
        ppr_router._query_service,
        "load_by_person_id",
        lambda _person_id: SimpleNamespace(person_id=41, employee_id=71),
    )
    monkeypatch.setattr(
        ppr_router,
        "assert_ppr_read_allowed_for_person",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(HTTPException(status_code=404, detail="Person not found.")),
    )
    monkeypatch.setattr(
        ppr_router,
        "load_current_operational_assignment_for_person",
        lambda *_args, **_kwargs: pytest.fail("projection must not run outside visibility scope"),
    )

    response = client.get("/api/ppr/persons/41/operational-assignment")

    assert response.status_code == 404
