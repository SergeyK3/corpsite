"""WP-PPR-MIG-005C HTTP contract and authorization tests (no database data)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import ppr_migration_status_router as status_router
from app.auth import get_current_user
from app.main import app


@pytest.fixture
def client(monkeypatch):
    app.dependency_overrides.clear()
    monkeypatch.setattr(status_router, "compute_scope", lambda *_a, **_k: {"privileged": True, "scope_unit_ids": None})
    monkeypatch.setattr(status_router, "require_personnel_visibility_or_403", lambda *_a: None)
    yield TestClient(app)
    app.dependency_overrides.clear()


def _authorize(monkeypatch, user_id: int, allowed: bool) -> None:
    app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id, "role_code": "HR_HEAD"}
    monkeypatch.setattr(status_router, "has_admin_permission", lambda uid, _permission: uid == user_id and allowed)


def test_unauthenticated_request_is_401(client):
    assert client.get("/directory/personnel/migration-status/universes").status_code == 401


def test_permission_is_required_and_admin_has_no_implicit_bypass(client, monkeypatch):
    _authorize(monkeypatch, 101, False)
    assert client.get("/directory/personnel/migration-status/universes").status_code == 403
    app.dependency_overrides[get_current_user] = lambda: {"user_id": 102, "role_code": "ADMIN"}
    assert client.get("/directory/personnel/migration-status", params={"universe_id": 1}).status_code == 403


@pytest.mark.parametrize("user_id", [201, 202], ids=["hr_head_role_grant", "personal_grant"])
def test_role_and_personal_grant_authorize_both_read_endpoints(client, monkeypatch, user_id):
    _authorize(monkeypatch, user_id, True)
    monkeypatch.setattr(status_router, "list_universes", lambda *_a: [{"universe_id": 7, "base_cohort_run_id": 4, "supplemental_cohort_run_ids": [], "calculated_at": "2026-01-01T00:00:00Z"}])
    monkeypatch.setattr(status_router, "matrix", lambda *_a, **_k: {"universe_id": 7, "page": 1, "page_size": 50, "total": 0, "items": [], "counts": []})
    assert client.get("/directory/personnel/migration-status/universes").status_code == 200
    response = client.get("/directory/personnel/migration-status", params={"universe_id": 7})
    assert response.status_code == 200
    assert response.json()["universe_id"] == 7


def test_matrix_contract_rejects_missing_or_oversized_page_and_hides_unknown_universe(client, monkeypatch):
    _authorize(monkeypatch, 301, True)
    assert client.get("/directory/personnel/migration-status").status_code == 422
    assert client.get("/directory/personnel/migration-status", params={"universe_id": 1, "page_size": 101}).status_code == 422
    monkeypatch.setattr(status_router, "matrix", lambda *_a, **_k: None)
    response = client.get("/directory/personnel/migration-status", params={"universe_id": 999})
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "MIGRATION_STATUS_UNIVERSE_NOT_FOUND"


def test_response_contains_only_safe_status_reason_and_evidence_fields(client, monkeypatch):
    _authorize(monkeypatch, 401, True)
    safe = {"universe_id": 3, "page": 1, "page_size": 1, "total": 1, "counts": [{"section_code": "general", "status_code": "ACCEPTED", "status_label": "Согласовано", "count": 1}], "items": [{"person_id": 8, "employee_context_id": 9, "org_unit_id": 10, "full_name": "Canonical Name", "cells": {"general": {"status_code": "ACCEPTED", "status_label": "Согласовано", "reason_code": "RUN_PARTICIPANT_ACCEPTED", "reason_label": "Результат сотрудника подтверждён.", "calculated_at": "2026-01-01T00:00:00Z", "stage_run_id": None, "stage1_run_id": 11, "stage_participant_id": None, "stage1_participant_id": 12, "pmf_run_id": None}}}]}
    monkeypatch.setattr(status_router, "matrix", lambda *_a, **_k: safe)
    body = client.get("/directory/personnel/migration-status", params={"universe_id": 3, "section": "general", "status": "ACCEPTED", "reason": "RUN_PARTICIPANT_ACCEPTED", "org_unit_id": 10, "q": "Canonical"}).json()
    serialized = str(body).lower()
    assert body["items"][0]["cells"]["general"]["status_label"]
    assert body["items"][0]["cells"]["general"]["reason_label"]
    assert not any(secret in serialized for secret in ("iin", "fingerprint", "raw_payload", "document", "traceback", "select "))
