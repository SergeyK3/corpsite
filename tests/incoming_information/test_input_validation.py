# tests/incoming_information/test_input_validation.py
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.incoming_information.conftest import (
    utc_today,
    assign_primary,
    lookup_dictionary_id,
    register_test_document,
)


def _registration_payload(seed, **overrides):
    with engine.connect() as conn:
        doc_type_id = lookup_dictionary_id(conn, table="incoming_document_types", code="OTHER")
        channel_id = lookup_dictionary_id(conn, table="incoming_receipt_channels", code="OTHER")
    payload = {
        "received_at": utc_today().isoformat(),
        "document_type_id": doc_type_id,
        "receipt_channel_id": channel_id,
        "summary": "Validation test",
        "sender_kind": "EXTERNAL_TEXT",
        "sender_text": "Sender",
        "addressee_kind": "USER",
        "addressee_user_id": int(seed["executor_user_id"]),
        "registration_org_unit_id": int(seed["unit_id"]),
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize(
    "overrides,expected_status",
    [
        ({"sender_kind": "EXTERNAL_TEXT", "sender_person_id": 999999}, 422),
        ({"addressee_kind": "USER", "addressee_org_unit_id": 999999999}, 422),
        ({"addressee_kind": "USER", "addressee_user_id": 999999999}, 422),
    ],
)
@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_registration_invalid_party_combinations_return_422(
    client, seed, ii_register_headers, overrides, expected_status
):
    payload = _registration_payload(seed, **overrides)
    response = client.post(
        "/api/incoming-information/incoming-documents",
        json=payload,
        headers=ii_register_headers,
    )
    assert response.status_code == expected_status


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_assign_invalid_controller_returns_422(client, seed, ii_control_headers):
    document = register_test_document(client, seed, ii_control_headers)
    response = client.post(
        f"/api/incoming-information/incoming-documents/{document['incoming_document_id']}/assign",
        json={
            "expected_version": document["row_version"],
            "primary_user_id": int(seed["executor_user_id"]),
            "controller_user_id": 999999999,
        },
        headers=ii_control_headers,
    )
    assert response.status_code == 422
    with engine.connect() as conn:
        audit_count = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.incoming_document_audit
                WHERE incoming_document_id = :id AND action = 'OPERATION_ASSIGN'
                """
            ),
            {"id": int(document["incoming_document_id"])},
        ).one()[0]
        assignment_count = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.incoming_document_assignments
                WHERE incoming_document_id = :id
                """
            ),
            {"id": int(document["incoming_document_id"])},
        ).one()[0]
    assert audit_count == 0
    assert assignment_count == 0


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_reassign_invalid_org_unit_returns_422(client, seed, ii_control_headers):
    document = register_test_document(client, seed, ii_control_headers)
    assigned = assign_primary(
        client,
        document,
        ii_control_headers,
        primary_user_id=int(seed["executor_user_id"]),
    )
    response = client.post(
        f"/api/incoming-information/incoming-documents/{assigned['incoming_document_id']}/reassign",
        json={
            "expected_version": assigned["row_version"],
            "primary_user_id": int(seed["initiator_user_id"]),
            "org_unit_id": 999999999,
        },
        headers=ii_control_headers,
    )
    assert response.status_code == 422


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_external_transfer_conflicting_recipient_fields_return_422(client, seed, ii_control_headers):
    document = register_test_document(client, seed, ii_control_headers)
    response = client.post(
        f"/api/incoming-information/incoming-documents/{document['incoming_document_id']}/transfer",
        json={
            "expected_version": document["row_version"],
            "transfer_scope": "EXTERNAL",
            "recipient_kind": "USER",
            "recipient_user_id": int(seed["initiator_user_id"]),
            "recipient_text": "Extra",
            "comment": "Transfer",
        },
        headers=ii_control_headers,
    )
    assert response.status_code == 422
    with engine.connect() as conn:
        transfer_count = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.incoming_document_transfers
                WHERE incoming_document_id = :id
                """
            ),
            {"id": int(document["incoming_document_id"])},
        ).one()[0]
    assert transfer_count == 0


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_transfer_whitespace_only_comment_returns_422(client, seed, ii_control_headers):
    document = register_test_document(client, seed, ii_control_headers)
    response = client.post(
        f"/api/incoming-information/incoming-documents/{document['incoming_document_id']}/transfer",
        json={
            "expected_version": document["row_version"],
            "transfer_scope": "EXTERNAL",
            "recipient_kind": "TEXT",
            "recipient_text": "Outside",
            "comment": "   ",
        },
        headers=ii_control_headers,
    )
    assert response.status_code == 422


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_registration_accepts_existing_responsible_org_unit_id(client, seed, ii_register_headers):
    payload = _registration_payload(
        seed,
        responsible_org_unit_id=int(seed["unit_id"]),
    )
    response = client.post(
        "/api/incoming-information/incoming-documents",
        json=payload,
        headers=ii_register_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["responsible_org_unit_id"] == int(seed["unit_id"])


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_registration_invalid_responsible_org_unit_id_returns_422(client, seed, ii_register_headers):
    payload = _registration_payload(
        seed,
        responsible_org_unit_id=999999999,
    )
    response = client.post(
        "/api/incoming-information/incoming-documents",
        json=payload,
        headers=ii_register_headers,
    )
    assert response.status_code == 422


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_registration_invalid_responsible_org_unit_id_leaves_no_partial_records(
    client,
    seed,
    ii_register_headers,
):
    payload = _registration_payload(
        seed,
        responsible_org_unit_id=999999999,
    )
    with engine.connect() as conn:
        before_docs = conn.execute(text("SELECT COUNT(*) FROM public.incoming_documents")).one()[0]
        before_audit = conn.execute(text("SELECT COUNT(*) FROM public.incoming_document_audit")).one()[0]
        before_assignments = conn.execute(
            text("SELECT COUNT(*) FROM public.incoming_document_assignments")
        ).one()[0]

    response = client.post(
        "/api/incoming-information/incoming-documents",
        json=payload,
        headers=ii_register_headers,
    )
    assert response.status_code == 422

    with engine.connect() as conn:
        after_docs = conn.execute(text("SELECT COUNT(*) FROM public.incoming_documents")).one()[0]
        after_audit = conn.execute(text("SELECT COUNT(*) FROM public.incoming_document_audit")).one()[0]
        after_assignments = conn.execute(
            text("SELECT COUNT(*) FROM public.incoming_document_assignments")
        ).one()[0]

    assert after_docs == before_docs
    assert after_audit == before_audit
    assert after_assignments == before_assignments
