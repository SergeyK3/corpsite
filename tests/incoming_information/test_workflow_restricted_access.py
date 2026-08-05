# tests/incoming_information/test_workflow_restricted_access.py
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import auth_headers
from tests.incoming_information.conftest import (
    utc_today,
    advance_document_to_status,
    advance_restricted_document_to_status,
    assign_primary,
    grant_permissions,
    register_restricted_document,
    revoke_user_access_grants,
)


WORKFLOW_ENDPOINTS = (
    ("assign", "post", lambda doc, seed: {
        "expected_version": doc["row_version"],
        "primary_user_id": int(seed["initiator_user_id"]),
    }),
    ("reassign", "post", lambda doc, seed: {
        "expected_version": doc["row_version"],
        "primary_user_id": int(seed["initiator_user_id"]),
    }),
    ("transfer", "post", lambda doc, seed: {
        "expected_version": doc["row_version"],
        "transfer_scope": "EXTERNAL",
        "recipient_kind": "TEXT",
        "recipient_text": "Outside",
        "comment": "Transfer",
    }),
    ("start", "post", lambda doc, seed: {"expected_version": doc["row_version"]}),
    ("request-information", "post", lambda doc, seed: {
        "expected_version": doc["row_version"],
        "reason": "Need info",
    }),
    ("resume", "post", lambda doc, seed: {"expected_version": doc["row_version"], "comment": "Resume"}),
    ("change-deadline", "post", lambda doc, seed: {
        "expected_version": doc["row_version"],
        "new_due_date": (utc_today() + timedelta(days=5)).isoformat(),
        "reason": "Extend",
    }),
    ("resolve", "post", lambda doc, seed: {
        "expected_version": doc["row_version"],
        "execution_result": "Done",
    }),
    ("close", "post", lambda doc, seed: {
        "expected_version": doc["row_version"],
        "control_decision": "Accepted",
    }),
    ("reopen", "post", lambda doc, seed: {
        "expected_version": doc["row_version"],
        "reason": "Reopen",
    }),
    ("cancel", "post", lambda doc, seed: {
        "expected_version": doc["row_version"],
        "reason": "Cancel",
    }),
)


def _prepare_restricted_document_for_endpoint(client, seed, control_headers, endpoint: str) -> dict:
    if endpoint in {"assign", "transfer", "change-deadline", "cancel"}:
        return register_restricted_document(client, seed, control_headers)
    if endpoint in {"reassign", "start"}:
        doc = register_restricted_document(client, seed, control_headers)
        return assign_primary(
            client,
            doc,
            control_headers,
            primary_user_id=int(seed["executor_user_id"]),
            controller_user_id=int(seed["executor_user_id"]),
        )
    if endpoint == "request-information":
        return advance_restricted_document_to_status(client, seed, control_headers, "IN_PROGRESS")
    if endpoint == "resume":
        return advance_restricted_document_to_status(client, seed, control_headers, "WAITING_INFORMATION")
    if endpoint == "resolve":
        return advance_restricted_document_to_status(client, seed, control_headers, "IN_PROGRESS")
    if endpoint == "close":
        doc = advance_restricted_document_to_status(client, seed, control_headers, "IN_PROGRESS")
        resolved = client.post(
            f"/api/incoming-information/incoming-documents/{doc['incoming_document_id']}/resolve",
            json={"expected_version": doc["row_version"], "execution_result": "Done"},
            headers=control_headers,
        )
        assert resolved.status_code == 200, resolved.text
        return resolved.json()
    if endpoint == "reopen":
        closed = _prepare_restricted_document_for_endpoint(client, seed, control_headers, "close")
        return closed
    raise AssertionError(endpoint)


@pytest.mark.parametrize("endpoint,method,payload_builder", WORKFLOW_ENDPOINTS)
@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_restricted_outsider_gets_403_on_every_workflow_endpoint(
    client, seed, ii_control_headers, ii_outsider_headers, endpoint, method, payload_builder
):
    document = _prepare_restricted_document_for_endpoint(client, seed, ii_control_headers, endpoint)
    payload = payload_builder(document, seed)
    response = client.post(
        f"/api/incoming-information/incoming-documents/{document['incoming_document_id']}/{endpoint}",
        json=payload,
        headers=ii_outsider_headers,
    )
    assert response.status_code == 403


@pytest.mark.parametrize("endpoint,method,payload_builder", WORKFLOW_ENDPOINTS)
@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_restricted_privileged_admin_without_bypass_gets_403_on_every_workflow_endpoint(
    client, seed, ii_control_headers, endpoint, method, payload_builder, monkeypatch
):
    privileged_id = int(seed["initiator_user_id"])
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(privileged_id))
    try:
        document = _prepare_restricted_document_for_endpoint(client, seed, ii_control_headers, endpoint)
        payload = payload_builder(document, seed)
        response = client.post(
            f"/api/incoming-information/incoming-documents/{document['incoming_document_id']}/{endpoint}",
            json=payload,
            headers=auth_headers(privileged_id),
        )
        assert response.status_code == 403
    finally:
        monkeypatch.delenv("DIRECTORY_PRIVILEGED_USER_IDS", raising=False)


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_restricted_org_scope_control_without_participation_is_forbidden(client, seed, ii_control_headers):
    outsider_id = int(seed["initiator_user_id"])
    with engine.begin() as conn:
        grant_permissions(
            conn,
            outsider_id,
            "INCOMING_INFO_CONTROL",
            "INCOMING_INFO_READ",
            "INCOMING_INFO_REGISTER",
        )
    try:
        document = register_restricted_document(
            client,
            seed,
            ii_control_headers,
            addressee_user_id=int(seed["executor_user_id"]),
        )
        response = client.post(
            f"/api/incoming-information/incoming-documents/{document['incoming_document_id']}/assign",
            json={
                "expected_version": document["row_version"],
                "primary_user_id": outsider_id,
            },
            headers=auth_headers(outsider_id),
        )
        assert response.status_code == 403
    finally:
        with engine.begin() as conn:
            revoke_user_access_grants(conn, outsider_id)


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_restricted_primary_may_execute_allowed_operations(client, seed, ii_control_headers):
    primary_id = int(seed["initiator_user_id"])
    controller_id = int(seed["executor_user_id"])
    with engine.begin() as conn:
        grant_permissions(conn, primary_id, "INCOMING_INFO_EXECUTE", "INCOMING_INFO_READ")
    try:
        document = register_restricted_document(client, seed, ii_control_headers)
        assigned = assign_primary(
            client,
            document,
            ii_control_headers,
            primary_user_id=primary_id,
            controller_user_id=controller_id,
        )
        headers = auth_headers(primary_id)
        start = client.post(
            f"/api/incoming-information/incoming-documents/{assigned['incoming_document_id']}/start",
            json={"expected_version": assigned["row_version"]},
            headers=headers,
        )
        assert start.status_code == 200, start.text

        denied_change_deadline = client.post(
            f"/api/incoming-information/incoming-documents/{start.json()['incoming_document_id']}/change-deadline",
            json={
                "expected_version": start.json()["row_version"],
                "new_due_date": (utc_today() + timedelta(days=3)).isoformat(),
                "reason": "Extend",
            },
            headers=headers,
        )
        assert denied_change_deadline.status_code == 403
    finally:
        with engine.begin() as conn:
            revoke_user_access_grants(conn, primary_id)


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_restricted_coexecutor_cannot_resolve(client, seed, ii_control_headers):
    executor_id = int(seed["executor_user_id"])
    coexecutor_id = int(seed["initiator_user_id"])
    document = register_restricted_document(client, seed, ii_control_headers)
    assigned = client.post(
        f"/api/incoming-information/incoming-documents/{document['incoming_document_id']}/assign",
        json={
            "expected_version": document["row_version"],
            "primary_user_id": executor_id,
            "coexecutor_user_ids": [coexecutor_id],
            "controller_user_id": executor_id,
        },
        headers=ii_control_headers,
    ).json()
    started = client.post(
        f"/api/incoming-information/incoming-documents/{assigned['incoming_document_id']}/start",
        json={"expected_version": assigned["row_version"]},
        headers=ii_control_headers,
    ).json()
    with engine.begin() as conn:
        grant_permissions(conn, coexecutor_id, "INCOMING_INFO_EXECUTE", "INCOMING_INFO_READ")
    try:
        resolve = client.post(
            f"/api/incoming-information/incoming-documents/{started['incoming_document_id']}/resolve",
            json={"expected_version": started["row_version"], "execution_result": "Done"},
            headers=auth_headers(coexecutor_id),
        )
        assert resolve.status_code == 403
    finally:
        with engine.begin() as conn:
            revoke_user_access_grants(conn, coexecutor_id)


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_former_primary_after_reassign_is_forbidden(client, seed, ii_control_headers):
    executor_id = int(seed["executor_user_id"])
    initiator_id = int(seed["initiator_user_id"])
    document = register_restricted_document(client, seed, ii_control_headers)
    assigned = assign_primary(
        client,
        document,
        ii_control_headers,
        primary_user_id=executor_id,
        controller_user_id=executor_id,
    )
    reassign = client.post(
        f"/api/incoming-information/incoming-documents/{assigned['incoming_document_id']}/reassign",
        json={
            "expected_version": assigned["row_version"],
            "primary_user_id": initiator_id,
        },
        headers=ii_control_headers,
    )
    assert reassign.status_code == 200, reassign.text
    with engine.begin() as conn:
        grant_permissions(conn, executor_id, "INCOMING_INFO_EXECUTE", "INCOMING_INFO_READ")
    try:
        denied = client.post(
            f"/api/incoming-information/incoming-documents/{reassign.json()['incoming_document_id']}/start",
            json={"expected_version": reassign.json()["row_version"]},
            headers=auth_headers(executor_id),
        )
        assert denied.status_code == 403
    finally:
        with engine.begin() as conn:
            revoke_user_access_grants(conn, executor_id)


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_former_primary_after_internal_transfer_is_forbidden(client, seed, ii_control_headers):
    from tests.conftest import create_unit

    executor_id = int(seed["executor_user_id"])
    document = register_restricted_document(client, seed, ii_control_headers)
    assigned = assign_primary(
        client,
        document,
        ii_control_headers,
        primary_user_id=executor_id,
        controller_user_id=executor_id,
    )
    with engine.begin() as conn:
        target_unit_id = create_unit(conn, "pytest_restricted_transfer_target")
    transfer = client.post(
        f"/api/incoming-information/incoming-documents/{assigned['incoming_document_id']}/transfer",
        json={
            "expected_version": assigned["row_version"],
            "transfer_scope": "INTERNAL",
            "target_org_unit_id": target_unit_id,
            "comment": "Move unit",
        },
        headers=ii_control_headers,
    )
    assert transfer.status_code == 200, transfer.text
    with engine.begin() as conn:
        grant_permissions(conn, executor_id, "INCOMING_INFO_EXECUTE", "INCOMING_INFO_READ")
    try:
        denied = client.post(
            f"/api/incoming-information/incoming-documents/{transfer.json()['incoming_document_id']}/start",
            json={"expected_version": transfer.json()["row_version"]},
            headers=auth_headers(executor_id),
        )
        assert denied.status_code == 403
    finally:
        with engine.begin() as conn:
            revoke_user_access_grants(conn, executor_id)


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_restricted_assigned_controller_may_close(client, seed, ii_control_headers):
    controller_id = int(seed["executor_user_id"])
    document = register_restricted_document(client, seed, ii_control_headers)
    assigned = assign_primary(
        client,
        document,
        ii_control_headers,
        primary_user_id=controller_id,
        controller_user_id=controller_id,
    )
    started = client.post(
        f"/api/incoming-information/incoming-documents/{assigned['incoming_document_id']}/start",
        json={"expected_version": assigned["row_version"]},
        headers=ii_control_headers,
    ).json()
    with engine.begin() as conn:
        grant_permissions(conn, controller_id, "INCOMING_INFO_CONTROL", "INCOMING_INFO_READ")
    try:
        resolved = client.post(
            f"/api/incoming-information/incoming-documents/{started['incoming_document_id']}/resolve",
            json={"expected_version": started["row_version"], "execution_result": "Done"},
            headers=auth_headers(controller_id),
        )
        assert resolved.status_code == 200, resolved.text
        closed = client.post(
            f"/api/incoming-information/incoming-documents/{resolved.json()['incoming_document_id']}/close",
            json={
                "expected_version": resolved.json()["row_version"],
                "control_decision": "Accepted",
                "comment": "OK",
            },
            headers=auth_headers(controller_id),
        )
        assert closed.status_code == 200, closed.text
        assert closed.json()["control_decision"] == "Accepted"
        assert closed.json()["control_comment"] == "OK"
    finally:
        with engine.begin() as conn:
            revoke_user_access_grants(conn, controller_id)


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_restricted_bypass_admin_may_assign(client, seed, ii_control_headers):
    bypass_user_id = int(seed["initiator_user_id"])
    with engine.begin() as conn:
        grant_permissions(
            conn,
            bypass_user_id,
            "INCOMING_INFO_RESTRICTED_BYPASS",
            "INCOMING_INFO_CONTROL",
            "INCOMING_INFO_READ",
        )
    try:
        document = register_restricted_document(
            client,
            seed,
            ii_control_headers,
            addressee_user_id=int(seed["executor_user_id"]),
        )
        response = client.post(
            f"/api/incoming-information/incoming-documents/{document['incoming_document_id']}/assign",
            json={
                "expected_version": document["row_version"],
                "primary_user_id": bypass_user_id,
            },
            headers=auth_headers(bypass_user_id),
        )
        assert response.status_code == 200, response.text
    finally:
        with engine.begin() as conn:
            revoke_user_access_grants(conn, bypass_user_id)
