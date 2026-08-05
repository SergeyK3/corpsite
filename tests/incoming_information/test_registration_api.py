# tests/incoming_information/test_registration_api.py
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.incoming_information.conftest import utc_today, cleanup_incoming_documents, lookup_dictionary_id


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_post_incoming_document_registers_record(client, seed, ii_register_headers):
    with engine.connect() as conn:
        doc_type_id = lookup_dictionary_id(conn, table="incoming_document_types", code="REPORT")
        channel_id = lookup_dictionary_id(conn, table="incoming_receipt_channels", code="IN_PERSON")

    payload = {
        "received_at": utc_today().isoformat(),
        "document_type_id": doc_type_id,
        "receipt_channel_id": channel_id,
        "summary": "Рапорт без вложения",
        "access_level": "NORMAL",
        "sender_kind": "EXTERNAL_TEXT",
        "sender_text": "Сотрудник отдела",
        "addressee_kind": "ORG_UNIT",
        "addressee_org_unit_id": int(seed["unit_id"]),
        "registration_org_unit_id": int(seed["unit_id"]),
    }
    response = client.post(
        "/api/incoming-information/incoming-documents",
        json=payload,
        headers=ii_register_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    document_id = int(body["incoming_document_id"])
    assert body["registration_number"].startswith("ВХ-")
    assert body["status_code"] == "REGISTERED"
    assert body["responsible_org_unit_id"] == int(seed["unit_id"])

    audit = client.get(
        f"/api/incoming-information/incoming-documents/{document_id}/audit",
        headers=ii_register_headers,
    )
    assert audit.status_code == 200
    assert audit.json()[0]["action"] == "CREATED"

    with engine.begin() as conn:
        cleanup_incoming_documents(conn, [document_id])


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_get_incoming_documents_list_and_detail(client, seed, ii_register_headers):
    with engine.connect() as conn:
        doc_type_id = lookup_dictionary_id(conn, table="incoming_document_types", code="LETTER")
        channel_id = lookup_dictionary_id(conn, table="incoming_receipt_channels", code="EMAIL")

    payload = {
        "received_at": utc_today().isoformat(),
        "document_type_id": doc_type_id,
        "receipt_channel_id": channel_id,
        "summary": "Письмо по email",
        "sender_kind": "EXTERNAL_TEXT",
        "sender_text": "Контрагент",
        "addressee_kind": "USER",
        "addressee_user_id": int(seed["executor_user_id"]),
        "registration_org_unit_id": int(seed["unit_id"]),
    }
    created = client.post(
        "/api/incoming-information/incoming-documents",
        json=payload,
        headers=ii_register_headers,
    )
    assert created.status_code == 200
    document_id = int(created.json()["incoming_document_id"])

    listing = client.get(
        "/api/incoming-information/incoming-documents",
        headers=ii_register_headers,
    )
    assert listing.status_code == 200
    assert listing.json()["total"] >= 1

    detail = client.get(
        f"/api/incoming-information/incoming-documents/{document_id}",
        headers=ii_register_headers,
    )
    assert detail.status_code == 200
    assert detail.json()["incoming_document_id"] == document_id

    with engine.begin() as conn:
        cleanup_incoming_documents(conn, [document_id])
