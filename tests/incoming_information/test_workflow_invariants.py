# tests/incoming_information/test_workflow_invariants.py
"""Maps workflow invariants to concrete tests (existing + dedicated)."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.incoming_information.conftest import (
    advance_document_to_status,
    assign_primary,
    register_test_document,
)


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_same_registration_and_responsible_org_unit_allowed(client, seed, ii_register_headers):
    body = register_test_document(client, seed, ii_register_headers)
    assert body["registration_org_unit_id"] == body["responsible_org_unit_id"]


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_registration_org_unit_is_immutable_after_internal_transfer(client, seed, ii_control_headers):
    from tests.conftest import create_unit

    body = register_test_document(client, seed, ii_control_headers)
    original_registration_org_unit_id = int(body["registration_org_unit_id"])
    with engine.begin() as conn:
        other_unit_id = create_unit(conn, "pytest_invariant_transfer_target")
    transfer = client.post(
        f"/api/incoming-information/incoming-documents/{body['incoming_document_id']}/transfer",
        json={
            "expected_version": body["row_version"],
            "transfer_scope": "INTERNAL",
            "target_org_unit_id": other_unit_id,
            "comment": "Move",
        },
        headers=ii_control_headers,
    )
    assert transfer.status_code == 200, transfer.text
    assert transfer.json()["registration_org_unit_id"] == original_registration_org_unit_id


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_assigned_in_progress_waiting_require_active_primary(client, seed, ii_control_headers):
    assigned = advance_document_to_status(client, seed, ii_control_headers, "ASSIGNED")
    in_progress = advance_document_to_status(client, seed, ii_control_headers, "IN_PROGRESS")
    waiting = advance_document_to_status(client, seed, ii_control_headers, "WAITING_INFORMATION")
    for document in (assigned, in_progress, waiting):
        with engine.connect() as conn:
            count = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.incoming_document_assignments
                    WHERE incoming_document_id = :document_id
                      AND role = 'PRIMARY'
                      AND completed_at IS NULL
                      AND cancelled_at IS NULL
                    """
                ),
                {"document_id": int(document["incoming_document_id"])},
            ).one()[0]
        assert int(count) == 1


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_only_one_active_primary_is_enforced(client, seed, ii_control_headers):
    body = register_test_document(client, seed, ii_control_headers)
    assigned = assign_primary(
        client,
        body,
        ii_control_headers,
        primary_user_id=int(seed["executor_user_id"]),
    )
    duplicate = client.post(
        f"/api/incoming-information/incoming-documents/{assigned['incoming_document_id']}/assign",
        json={
            "expected_version": assigned["row_version"],
            "primary_user_id": int(seed["initiator_user_id"]),
        },
        headers=ii_control_headers,
    )
    assert duplicate.status_code == 422


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_internal_transfer_resets_registered_and_clears_assignments(client, seed, ii_control_headers):
    from tests.conftest import create_unit

    assigned = advance_document_to_status(client, seed, ii_control_headers, "ASSIGNED")
    with engine.begin() as conn:
        target_unit_id = create_unit(conn, "pytest_invariant_internal_target")
    transfer = client.post(
        f"/api/incoming-information/incoming-documents/{assigned['incoming_document_id']}/transfer",
        json={
            "expected_version": assigned["row_version"],
            "transfer_scope": "INTERNAL",
            "target_org_unit_id": target_unit_id,
            "comment": "Move",
        },
        headers=ii_control_headers,
    )
    assert transfer.status_code == 200, transfer.text
    assert transfer.json()["status_code"] == "REGISTERED"
    with engine.connect() as conn:
        active = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.incoming_document_assignments
                WHERE incoming_document_id = :document_id
                  AND completed_at IS NULL
                  AND cancelled_at IS NULL
                """
            ),
            {"document_id": int(assigned["incoming_document_id"])},
        ).one()[0]
    assert int(active) == 0


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_resolved_requires_execution_result_and_executed_at(client, seed, ii_control_headers):
    in_progress = advance_document_to_status(client, seed, ii_control_headers, "IN_PROGRESS")
    bad = client.post(
        f"/api/incoming-information/incoming-documents/{in_progress['incoming_document_id']}/resolve",
        json={"expected_version": in_progress["row_version"], "execution_result": "   "},
        headers=ii_control_headers,
    )
    assert bad.status_code == 422


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_closed_requires_resolved_status(client, seed, ii_control_headers):
    in_progress = advance_document_to_status(client, seed, ii_control_headers, "IN_PROGRESS")
    close = client.post(
        f"/api/incoming-information/incoming-documents/{in_progress['incoming_document_id']}/close",
        json={"expected_version": in_progress["row_version"], "control_decision": "Accepted"},
        headers=ii_control_headers,
    )
    assert close.status_code == 422


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_cancel_requires_reason(client, seed, ii_register_headers):
    body = register_test_document(client, seed, ii_register_headers)
    cancel = client.post(
        f"/api/incoming-information/incoming-documents/{body['incoming_document_id']}/cancel",
        json={"expected_version": body["row_version"], "reason": "   "},
        headers=ii_register_headers,
    )
    assert cancel.status_code == 422
