# tests/test_hr_event_registry.py
from __future__ import annotations

from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.db.engine import engine
from app.services.hr_event_registry import (
    HR_EVENT_REGISTRY,
    PHASE_1A_CREATABLE,
    get_event_class,
    get_event_def,
    get_event_label,
    is_creatable_in_phase_1a,
    list_registry_for_ui,
    resolve_journal_event_codes,
)
from tests.conftest import auth_headers


@pytest.fixture
def registry_deps_group():
    with engine.begin() as conn:
        created = conn.execute(
            text(
                """
                INSERT INTO public.deps_group (group_id, group_name)
                VALUES (1, 'pytest registry group')
                ON CONFLICT (group_id) DO NOTHING
                RETURNING group_id
                """
            )
        ).scalar_one_or_none()
    try:
        yield
    finally:
        if created is not None:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "DELETE FROM public.deps_group WHERE group_id = 1"
                    )
                )


@pytest.fixture
def registry_seed(registry_deps_group, seed):
    return seed


@pytest.fixture
def hr_enrollment_access_role(registry_seed):
    with engine.begin() as conn:
        access_role_id = conn.execute(
            text(
                """
                SELECT access_role_id
                FROM public.access_roles
                WHERE code = 'HR_ENROLLMENT_MANAGER'
                LIMIT 1
                """
            )
        ).scalar_one_or_none()
        created = access_role_id is None
        if created:
            access_role_id = conn.execute(
                text(
                    """
                    INSERT INTO public.access_roles (
                        code, name, access_level, level_rank, is_system, is_active
                    )
                    VALUES ('HR_ENROLLMENT_MANAGER', 'Pytest HR Enrollment Manager', 'MANAGER', 20, FALSE, TRUE)
                    RETURNING access_role_id
                    """
                )
            ).scalar_one()
    try:
        yield int(access_role_id)
    finally:
        if created:
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM public.access_grants WHERE access_role_id = :access_role_id"),
                    {"access_role_id": int(access_role_id)},
                )
                conn.execute(
                    text("DELETE FROM public.access_roles WHERE access_role_id = :access_role_id"),
                    {"access_role_id": int(access_role_id)},
                )


@pytest.fixture
def privileged_headers(registry_seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(registry_seed["initiator_user_id"]))
    return auth_headers(registry_seed["initiator_user_id"])


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
    assert body["version"] == "1.1"
    codes = {x["code"] for x in body["items"]}
    assert "TRANSFER" in codes
    assert "POSITION_CHANGE" in codes
    assert "RATE_CHANGE" in codes
    assert "LEAVE.ANNUAL.GRANT" in codes


def test_personnel_admin_gets_hr_event_registry_v11(
    client: TestClient, registry_seed, hr_enrollment_access_role
):
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO public.access_grants (
                    access_role_id, target_type, target_id, resource_key,
                    scope_type, starts_at, granted_by_user_id, reason
                )
                VALUES (
                    :access_role_id, 'USER', :user_id, '*', 'GLOBAL',
                    statement_timestamp(), :user_id, 'pytest personnel journal registry'
                )
                """
            ),
            {"access_role_id": hr_enrollment_access_role, "user_id": registry_seed["initiator_user_id"]},
        )

    resp = client.get(
        "/directory/hr-event-registry",
        headers=auth_headers(registry_seed["initiator_user_id"]),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["version"] == "1.1"


def test_user_without_personnel_journal_access_gets_403(client: TestClient, registry_seed):
    resp = client.get(
        "/directory/hr-event-registry",
        headers=auth_headers(registry_seed["executor_user_id"]),
    )
    assert resp.status_code == 403, resp.text


def test_journal_registry_contains_current_and_leave_v11_codes():
    items = {item["code"]: item for item in list_registry_for_ui()}
    for code in (
        "HIRE",
        "TRANSFER",
        "POSITION_CHANGE",
        "RATE_CHANGE",
        "CORRECTION",
        "TERMINATION",
        "EMPLOYEE_ENROLLED_FROM_IMPORT",
        "LEAVE.ANNUAL.GRANT",
        "LEAVE.ANNUAL.POSTPONE",
        "LEAVE.UNPAID.EARLY_RETURN",
    ):
        assert code in items
    assert items["LEAVE.ANNUAL.GRANT"]["category"] == "LEAVE"
    assert items["LEAVE.ANNUAL.GRANT"]["leave_kind"] == "ANNUAL"
    assert items["LEAVE.ANNUAL.GRANT"]["operation"] == "GRANT"
    assert items["LEAVE.UNCLASSIFIED"]["automatic_effect"] == "NO_AUTOMATIC_EFFECT"


def test_journal_registry_filters_resolve_to_canonical_codes():
    assert resolve_journal_event_codes(event_category="LEAVE") == {
        "LEAVE.ANNUAL.GRANT",
        "LEAVE.ANNUAL.POSTPONE",
        "LEAVE.ANNUAL.EXTEND",
        "LEAVE.ANNUAL.RECALL",
        "LEAVE.UNPAID.GRANT",
        "LEAVE.UNPAID.EARLY_RETURN",
        "LEAVE.PAID_OTHER.GRANT",
        "LEAVE.MATERNITY.GRANT",
        "LEAVE.CHILDCARE.GRANT",
        "LEAVE.UNCLASSIFIED",
    }
    assert resolve_journal_event_codes(
        event_category="LEAVE", leave_kind="ANNUAL", leave_operation="RECALL"
    ) == {"LEAVE.ANNUAL.RECALL"}
    assert resolve_journal_event_codes(event_type="TRANSFER") == {"TRANSFER"}
