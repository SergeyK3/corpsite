# tests/incoming_information/test_execute_permission.py
from __future__ import annotations

import pytest

from app.db.engine import engine
from tests.conftest import auth_headers
from tests.incoming_information.conftest import (
    assign_primary,
    grant_permissions,
    register_restricted_document,
    register_test_document,
    revoke_user_access_grants,
)


@pytest.mark.parametrize("access_level", ["NORMAL", "RESTRICTED"])
@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_active_primary_without_execute_gets_403(client, seed, ii_control_headers, access_level):
    primary_id = int(seed["initiator_user_id"])
    document = (
        register_test_document(client, seed, ii_control_headers, access_level=access_level)
        if access_level == "NORMAL"
        else register_restricted_document(client, seed, ii_control_headers)
    )
    assigned = assign_primary(
        client,
        document,
        ii_control_headers,
        primary_user_id=primary_id,
        controller_user_id=int(seed["executor_user_id"]),
    )
    with engine.begin() as conn:
        grant_permissions(conn, primary_id, "INCOMING_INFO_READ")
    try:
        response = client.post(
            f"/api/incoming-information/incoming-documents/{assigned['incoming_document_id']}/start",
            json={"expected_version": assigned["row_version"]},
            headers=auth_headers(primary_id),
        )
        assert response.status_code == 403
    finally:
        with engine.begin() as conn:
            revoke_user_access_grants(conn, primary_id)


@pytest.mark.parametrize("access_level", ["NORMAL", "RESTRICTED"])
@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_active_coexecutor_without_execute_gets_403(client, seed, ii_control_headers, access_level):
    primary_id = int(seed["executor_user_id"])
    coexecutor_id = int(seed["initiator_user_id"])
    document = (
        register_test_document(client, seed, ii_control_headers, access_level=access_level)
        if access_level == "NORMAL"
        else register_restricted_document(client, seed, ii_control_headers)
    )
    assigned = client.post(
        f"/api/incoming-information/incoming-documents/{document['incoming_document_id']}/assign",
        json={
            "expected_version": document["row_version"],
            "primary_user_id": primary_id,
            "coexecutor_user_ids": [coexecutor_id],
            "controller_user_id": primary_id,
        },
        headers=ii_control_headers,
    ).json()
    started = client.post(
        f"/api/incoming-information/incoming-documents/{assigned['incoming_document_id']}/start",
        json={"expected_version": assigned["row_version"]},
        headers=ii_control_headers,
    ).json()
    waiting = client.post(
        f"/api/incoming-information/incoming-documents/{started['incoming_document_id']}/request-information",
        json={"expected_version": started["row_version"], "reason": "Need info"},
        headers=ii_control_headers,
    ).json()
    with engine.begin() as conn:
        grant_permissions(conn, coexecutor_id, "INCOMING_INFO_READ")
    try:
        response = client.post(
            f"/api/incoming-information/incoming-documents/{waiting['incoming_document_id']}/resume",
            json={"expected_version": waiting["row_version"], "comment": "Resume"},
            headers=auth_headers(coexecutor_id),
        )
        assert response.status_code == 403
    finally:
        with engine.begin() as conn:
            revoke_user_access_grants(conn, coexecutor_id)


@pytest.mark.parametrize("access_level", ["NORMAL", "RESTRICTED"])
@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_execute_permission_without_assignment_gets_403(client, seed, ii_control_headers, access_level):
    user_id = int(seed["initiator_user_id"])
    document = (
        register_test_document(client, seed, ii_control_headers, access_level=access_level)
        if access_level == "NORMAL"
        else register_restricted_document(client, seed, ii_control_headers)
    )
    assigned = assign_primary(
        client,
        document,
        ii_control_headers,
        primary_user_id=int(seed["executor_user_id"]),
        controller_user_id=int(seed["executor_user_id"]),
    )
    started = client.post(
        f"/api/incoming-information/incoming-documents/{assigned['incoming_document_id']}/start",
        json={"expected_version": assigned["row_version"]},
        headers=ii_control_headers,
    ).json()
    waiting = client.post(
        f"/api/incoming-information/incoming-documents/{started['incoming_document_id']}/request-information",
        json={"expected_version": started["row_version"], "reason": "Need info"},
        headers=ii_control_headers,
    ).json()
    with engine.begin() as conn:
        grant_permissions(conn, user_id, "INCOMING_INFO_EXECUTE", "INCOMING_INFO_READ")
    try:
        response = client.post(
            f"/api/incoming-information/incoming-documents/{waiting['incoming_document_id']}/resume",
            json={"expected_version": waiting["row_version"], "comment": "Resume"},
            headers=auth_headers(user_id),
        )
        assert response.status_code == 403
    finally:
        with engine.begin() as conn:
            revoke_user_access_grants(conn, user_id)
