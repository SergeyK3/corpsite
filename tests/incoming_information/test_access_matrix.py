# tests/incoming_information/test_access_matrix.py
"""Access matrix for NORMAL/RESTRICTED list/detail/download alignment."""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import auth_headers, create_unit
from tests.incoming_information.conftest import (
    assign_primary,
    grant_permissions,
    grant_user_permission,
    lookup_dictionary_id,
    register_restricted_document,
    register_test_document,
    revoke_user_access_grants,
    utc_today,
)


def _list_ids(client, user_id: int) -> set[int]:
    response = client.get(
        "/api/incoming-information/incoming-documents",
        params={"limit": 100, "offset": 0},
        headers=auth_headers(user_id),
    )
    assert response.status_code == 200, response.text
    return {int(item["incoming_document_id"]) for item in response.json()["items"]}


def _register_restricted_in_other_unit(client, seed, headers, *, other_unit_id: int) -> dict:
    with engine.connect() as conn:
        doc_type_id = lookup_dictionary_id(conn, table="incoming_document_types", code="COMPLAINT")
        channel_id = lookup_dictionary_id(conn, table="incoming_receipt_channels", code="PAPER")
    payload = {
        "received_at": utc_today().isoformat(),
        "document_type_id": doc_type_id,
        "receipt_channel_id": channel_id,
        "summary": "Restricted outside seed scope",
        "access_level": "RESTRICTED",
        "sender_kind": "EXTERNAL_TEXT",
        "sender_text": "Sender",
        "addressee_kind": "USER",
        "addressee_user_id": int(seed["initiator_user_id"]),
        "registration_org_unit_id": int(seed["unit_id"]),
        "responsible_org_unit_id": int(other_unit_id),
    }
    response = client.post(
        "/api/incoming-information/incoming-documents",
        json=payload,
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_bypass_only_user_cannot_list_or_read_normal(client, seed, ii_register_headers):
    user_id = int(seed["initiator_user_id"])
    normal = register_test_document(client, seed, ii_register_headers)
    normal_id = int(normal["incoming_document_id"])

    with engine.begin() as conn:
        grant_user_permission(conn, user_id, "INCOMING_INFO_RESTRICTED_BYPASS")
    try:
        listing = client.get(
            "/api/incoming-information/incoming-documents",
            headers=auth_headers(user_id),
        )
        assert listing.status_code == 403

        detail = client.get(
            f"/api/incoming-information/incoming-documents/{normal_id}",
            headers=auth_headers(user_id),
        )
        assert detail.status_code == 403
    finally:
        with engine.begin() as conn:
            revoke_user_access_grants(conn, user_id)


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_read_without_bypass_can_list_and_read_normal_in_scope(client, seed, ii_register_headers):
    user_id = int(seed["initiator_user_id"])
    normal = register_test_document(client, seed, ii_register_headers)
    normal_id = int(normal["incoming_document_id"])

    with engine.begin() as conn:
        grant_user_permission(conn, user_id, "INCOMING_INFO_READ")
    try:
        assert normal_id in _list_ids(client, user_id)
        detail = client.get(
            f"/api/incoming-information/incoming-documents/{normal_id}",
            headers=auth_headers(user_id),
        )
        assert detail.status_code == 200, detail.text
    finally:
        with engine.begin() as conn:
            revoke_user_access_grants(conn, user_id)


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_read_with_bypass_can_access_restricted_outside_scope(client, seed, ii_control_headers):
    user_id = int(seed["initiator_user_id"])
    with engine.begin() as conn:
        other_unit_id = create_unit(conn, "pytest_ii_access_matrix_other")
        assert other_unit_id is not None
        grant_permissions(conn, user_id, "INCOMING_INFO_READ", "INCOMING_INFO_RESTRICTED_BYPASS")

    document = _register_restricted_in_other_unit(
        client,
        seed,
        ii_control_headers,
        other_unit_id=int(other_unit_id),
    )
    document_id = int(document["incoming_document_id"])
    try:
        assert document_id in _list_ids(client, user_id)
        detail = client.get(
            f"/api/incoming-information/incoming-documents/{document_id}",
            headers=auth_headers(user_id),
        )
        assert detail.status_code == 200, detail.text
    finally:
        with engine.begin() as conn:
            revoke_user_access_grants(conn, user_id)


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_active_assignee_can_access_restricted_outside_scope(client, seed, ii_control_headers):
    assignee_id = int(seed["executor_user_id"])
    with engine.begin() as conn:
        other_unit_id = create_unit(conn, "pytest_ii_access_matrix_assignee")
        assert other_unit_id is not None
        grant_permissions(conn, assignee_id, "INCOMING_INFO_READ", "INCOMING_INFO_EXECUTE")

    document = _register_restricted_in_other_unit(
        client,
        seed,
        ii_control_headers,
        other_unit_id=int(other_unit_id),
    )
    assigned = assign_primary(
        client,
        document,
        ii_control_headers,
        primary_user_id=assignee_id,
        controller_user_id=int(seed["executor_user_id"]),
    )
    document_id = int(assigned["incoming_document_id"])
    try:
        assert document_id in _list_ids(client, assignee_id)
        detail = client.get(
            f"/api/incoming-information/incoming-documents/{document_id}",
            headers=auth_headers(assignee_id),
        )
        assert detail.status_code == 200, detail.text
    finally:
        with engine.begin() as conn:
            revoke_user_access_grants(conn, assignee_id)


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_outsider_outside_scope_not_in_list_and_detail_forbidden(
    client, seed, ii_control_headers, ii_outsider_headers
):
    outsider_id = int(seed["initiator_user_id"])
    document = register_restricted_document(
        client,
        seed,
        ii_control_headers,
        addressee_user_id=int(seed["executor_user_id"]),
    )
    document_id = int(document["incoming_document_id"])

    with engine.begin() as conn:
        grant_user_permission(conn, outsider_id, "INCOMING_INFO_READ")
    try:
        visible_ids = _list_ids(client, outsider_id)
        assert document_id not in visible_ids

        detail = client.get(
            f"/api/incoming-information/incoming-documents/{document_id}",
            headers=ii_outsider_headers,
        )
        assert detail.status_code == 403
    finally:
        with engine.begin() as conn:
            revoke_user_access_grants(conn, outsider_id)


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_inactive_assignee_is_not_participant(client, seed, ii_control_headers):
    former_assignee = int(seed["initiator_user_id"])
    replacement = int(seed["executor_user_id"])
    with engine.begin() as conn:
        grant_user_permission(conn, former_assignee, "INCOMING_INFO_READ")

    document = register_restricted_document(client, seed, ii_control_headers)
    assigned = assign_primary(
        client,
        document,
        ii_control_headers,
        primary_user_id=former_assignee,
        controller_user_id=replacement,
    )
    reassigned = client.post(
        f"/api/incoming-information/incoming-documents/{assigned['incoming_document_id']}/reassign",
        json={
            "expected_version": assigned["row_version"],
            "primary_user_id": replacement,
        },
        headers=ii_control_headers,
    )
    assert reassigned.status_code == 200, reassigned.text
    document_id = int(reassigned.json()["incoming_document_id"])

    visible = _list_ids(client, former_assignee)
    assert document_id not in visible

    detail = client.get(
        f"/api/incoming-information/incoming-documents/{document_id}",
        headers=auth_headers(former_assignee),
    )
    assert detail.status_code == 403

    with engine.begin() as conn:
        revoke_user_access_grants(conn, former_assignee)


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_restricted_participant_download_requires_same_access_as_detail(
    client, seed, ii_control_headers, ii_outsider_headers
):
    participant_id = int(seed["executor_user_id"])
    document = register_restricted_document(
        client,
        seed,
        ii_control_headers,
        addressee_user_id=participant_id,
    )
    document_id = int(document["incoming_document_id"])

    upload = client.post(
        f"/api/incoming-information/incoming-documents/{document_id}/attachments",
        headers=ii_control_headers,
        files={"file": ("report.pdf", b"%PDF-1.4 matrix", "application/pdf")},
    )
    assert upload.status_code == 200, upload.text
    attachment_id = int(upload.json()["attachment_id"])

    with engine.begin() as conn:
        grant_user_permission(conn, participant_id, "INCOMING_INFO_READ")

    try:
        allowed = client.get(
            f"/api/incoming-information/attachments/{attachment_id}/download",
            headers=auth_headers(participant_id),
        )
        assert allowed.status_code == 200, allowed.text

        denied = client.get(
            f"/api/incoming-information/attachments/{attachment_id}/download",
            headers=ii_outsider_headers,
        )
        assert denied.status_code == 403
    finally:
        with engine.begin() as conn:
            revoke_user_access_grants(conn, participant_id)
