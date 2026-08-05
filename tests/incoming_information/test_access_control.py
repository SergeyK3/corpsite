# tests/incoming_information/test_access_control.py
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import auth_headers
from tests.incoming_information.conftest import (
    utc_today,
    cleanup_incoming_documents,
    ensure_system_admin_role_row,
    grant_user_permission,
    lookup_dictionary_id,
    register_restricted_document,
    revoke_user_access_grants,
    revoke_user_permission,
)


@pytest.fixture
def ii_privileged_headers(seed, monkeypatch):
    user_id = int(seed["initiator_user_id"])
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(user_id))
    yield auth_headers(user_id)
    monkeypatch.delenv("DIRECTORY_PRIVILEGED_USER_IDS", raising=False)


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_restricted_document_hidden_from_outsider_direct_urls(client, seed, ii_register_headers, ii_outsider_headers):
    with engine.connect() as conn:
        doc_type_id = lookup_dictionary_id(conn, table="incoming_document_types", code="COMPLAINT")
        channel_id = lookup_dictionary_id(conn, table="incoming_receipt_channels", code="PAPER")

    payload = {
        "received_at": utc_today().isoformat(),
        "document_type_id": doc_type_id,
        "receipt_channel_id": channel_id,
        "summary": "Жалоба с ограниченным доступом",
        "access_level": "RESTRICTED",
        "sender_kind": "EXTERNAL_TEXT",
        "sender_text": "Заявитель",
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

    outsider_detail = client.get(
        f"/api/incoming-information/incoming-documents/{document_id}",
        headers=ii_outsider_headers,
    )
    assert outsider_detail.status_code == 403

    outsider_audit = client.get(
        f"/api/incoming-information/incoming-documents/{document_id}/audit",
        headers=ii_outsider_headers,
    )
    assert outsider_audit.status_code == 403

    with engine.begin() as conn:
        cleanup_incoming_documents(conn, [document_id])


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_attachment_download_requires_document_access(client, seed, ii_register_headers, ii_outsider_headers):
    with engine.connect() as conn:
        doc_type_id = lookup_dictionary_id(conn, table="incoming_document_types", code="ACT")
        channel_id = lookup_dictionary_id(conn, table="incoming_receipt_channels", code="PAPER")

    payload = {
        "received_at": utc_today().isoformat(),
        "document_type_id": doc_type_id,
        "receipt_channel_id": channel_id,
        "summary": "Акт",
        "access_level": "RESTRICTED",
        "sender_kind": "EXTERNAL_TEXT",
        "sender_text": "Инспекция",
        "addressee_kind": "USER",
        "addressee_user_id": int(seed["executor_user_id"]),
        "registration_org_unit_id": int(seed["unit_id"]),
    }
    created = client.post(
        "/api/incoming-information/incoming-documents",
        json=payload,
        headers=ii_register_headers,
    )
    document_id = int(created.json()["incoming_document_id"])

    upload = client.post(
        f"/api/incoming-information/incoming-documents/{document_id}/attachments",
        headers=ii_register_headers,
        files={"file": ("report.pdf", b"%PDF-1.4 test", "application/pdf")},
    )
    assert upload.status_code == 200, upload.text
    attachment_id = int(upload.json()["attachment_id"])

    denied = client.get(
        f"/api/incoming-information/attachments/{attachment_id}/download",
        headers=ii_outsider_headers,
    )
    assert denied.status_code == 403

    allowed = client.get(
        f"/api/incoming-information/attachments/{attachment_id}/download",
        headers=ii_register_headers,
    )
    assert allowed.status_code == 200
    assert allowed.content.startswith(b"%PDF")

    with engine.begin() as conn:
        cleanup_incoming_documents(conn, [document_id])


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_outsider_cannot_register_without_permission(client, seed, ii_outsider_headers):
    with engine.connect() as conn:
        doc_type_id = lookup_dictionary_id(conn, table="incoming_document_types", code="OTHER")
        channel_id = lookup_dictionary_id(conn, table="incoming_receipt_channels", code="OTHER")

    payload = {
        "received_at": utc_today().isoformat(),
        "document_type_id": doc_type_id,
        "receipt_channel_id": channel_id,
        "summary": "Попытка регистрации",
        "sender_kind": "EXTERNAL_TEXT",
        "sender_text": "Автор",
        "addressee_kind": "ORG_UNIT",
        "addressee_org_unit_id": int(seed["unit_id"]),
        "registration_org_unit_id": int(seed["unit_id"]),
    }
    response = client.post(
        "/api/incoming-information/incoming-documents",
        json=payload,
        headers=ii_outsider_headers,
    )
    assert response.status_code == 403


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_restricted_document_forbidden_for_privileged_admin_without_bypass(
    client, seed, ii_control_headers, ii_privileged_headers
):
    document = register_restricted_document(
        client,
        seed,
        ii_control_headers,
        addressee_user_id=int(seed["executor_user_id"]),
    )
    document_id = int(document["incoming_document_id"])

    detail = client.get(
        f"/api/incoming-information/incoming-documents/{document_id}",
        headers=ii_privileged_headers,
    )
    assert detail.status_code == 403

    audit = client.get(
        f"/api/incoming-information/incoming-documents/{document_id}/audit",
        headers=ii_privileged_headers,
    )
    assert audit.status_code == 403


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_restricted_document_allowed_for_admin_with_explicit_bypass(
    client, seed, ii_control_headers, ii_privileged_headers
):
    bypass_user_id = int(seed["initiator_user_id"])
    with engine.begin() as conn:
        grant_user_permission(conn, bypass_user_id, "INCOMING_INFO_RESTRICTED_BYPASS")
    try:
        document = register_restricted_document(
            client,
            seed,
            ii_control_headers,
            addressee_user_id=int(seed["executor_user_id"]),
        )
        document_id = int(document["incoming_document_id"])

        detail = client.get(
            f"/api/incoming-information/incoming-documents/{document_id}",
            headers=ii_privileged_headers,
        )
        assert detail.status_code == 200, detail.text
        assert detail.json()["access_level"] == "RESTRICTED"
    finally:
        with engine.begin() as conn:
            revoke_user_permission(conn, bypass_user_id, "INCOMING_INFO_RESTRICTED_BYPASS")


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_restricted_document_forbidden_for_system_admin_role_without_bypass(
    client, seed, ii_control_headers
):
    admin_id = int(seed["initiator_user_id"])
    with engine.connect() as conn:
        original_role_id = conn.execute(
            text("SELECT role_id FROM public.users WHERE user_id = :uid"),
            {"uid": admin_id},
        ).one()[0]
    with engine.begin() as conn:
        ensure_system_admin_role_row(conn)
        conn.execute(
            text("UPDATE public.users SET role_id = 2 WHERE user_id = :uid"),
            {"uid": admin_id},
        )
    try:
        document = register_restricted_document(
            client,
            seed,
            ii_control_headers,
            addressee_user_id=int(seed["executor_user_id"]),
        )
        response = client.get(
            f"/api/incoming-information/incoming-documents/{document['incoming_document_id']}",
            headers=auth_headers(admin_id),
        )
        assert response.status_code == 403
    finally:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE public.users SET role_id = :role_id WHERE user_id = :uid"),
                {"role_id": int(original_role_id), "uid": admin_id},
            )


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_restricted_document_hidden_from_list_for_outsider(client, seed, ii_control_headers, ii_outsider_headers):
    document = register_restricted_document(
        client,
        seed,
        ii_control_headers,
        addressee_user_id=int(seed["executor_user_id"]),
    )
    document_id = int(document["incoming_document_id"])

    with engine.begin() as conn:
        grant_user_permission(conn, int(seed["initiator_user_id"]), "INCOMING_INFO_READ")

    try:
        listing = client.get(
            "/api/incoming-information/incoming-documents",
            headers=ii_outsider_headers,
        )
        assert listing.status_code == 200, listing.text
        visible_ids = {int(item["incoming_document_id"]) for item in listing.json()["items"]}
        assert document_id not in visible_ids
    finally:
        with engine.begin() as conn:
            revoke_user_access_grants(conn, int(seed["initiator_user_id"]))


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_restricted_document_hidden_from_list_for_privileged_admin_without_bypass(
    client, seed, ii_control_headers, ii_privileged_headers
):
    document = register_restricted_document(
        client,
        seed,
        ii_control_headers,
        addressee_user_id=int(seed["executor_user_id"]),
    )
    document_id = int(document["incoming_document_id"])

    listing = client.get(
        "/api/incoming-information/incoming-documents",
        headers=ii_privileged_headers,
    )
    assert listing.status_code == 200, listing.text
    visible_ids = {int(item["incoming_document_id"]) for item in listing.json()["items"]}
    assert document_id not in visible_ids


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_privileged_interactive_admin_isolated_from_restricted_bypass(client, seed, ii_control_headers, monkeypatch):
    """Env-allowlisted privileged user is an interactive principal, not a system service contour."""
    admin_id = int(seed["initiator_user_id"])
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(admin_id))
    try:
        document = register_restricted_document(
            client,
            seed,
            ii_control_headers,
            addressee_user_id=int(seed["executor_user_id"]),
        )
        response = client.get(
            f"/api/incoming-information/incoming-documents/{document['incoming_document_id']}",
            headers=auth_headers(admin_id),
        )
        assert response.status_code == 403
    finally:
        monkeypatch.delenv("DIRECTORY_PRIVILEGED_USER_IDS", raising=False)
