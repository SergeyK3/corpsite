# tests/incoming_information/test_attachment_validation_negative.py
from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.engine import engine
from app.incoming_information.application.attachment_service import execute_attachment_deletion
from app.incoming_information.application.link_service import _raise_duplicate_link_conflict
from app.incoming_information.domain.errors import IncomingDocumentConflictError, IncomingDocumentValidationError
from app.incoming_information.domain.attachment_validation import validate_incoming_attachment_bytes
from app.incoming_information.infrastructure.attachment_storage import write_staging_attachment
from tests.incoming_information.conftest import build_user_dict, register_test_document


@pytest.mark.parametrize(
    "content,content_type,expected_fragment",
    [
        (b"not-a-pdf", "application/pdf", "valid PDF"),
        (b"\xff\xd0", "image/jpeg", "valid JPEG"),
        (b"not-png", "image/png", "valid PNG"),
        (b"MZ fake pdf", "application/pdf", "Executable"),
        (b"PK\x03\x04docx", "text/plain", "plain text"),
        (b"\x00binary", "text/plain", "plain text"),
        (b"fake doc", "application/msword", "not allowed"),
    ],
)
def test_attachment_validation_rejects_mismatch_or_fake_content(content, content_type, expected_fragment):
    with pytest.raises(IncomingDocumentValidationError, match=expected_fragment):
        validate_incoming_attachment_bytes(content, content_type=content_type)


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_upload_rejects_mismatched_filename_extension(client, seed, ii_register_headers):
    document = register_test_document(client, seed, ii_register_headers)
    response = client.post(
        f"/api/incoming-information/incoming-documents/{document['incoming_document_id']}/attachments",
        headers=ii_register_headers,
        files={"file": ("note.txt", b"%PDF-1.4 mismatch", "application/pdf")},
    )
    assert response.status_code == 422


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_upload_rejects_executable_with_allowed_content_type(client, seed, ii_register_headers):
    document = register_test_document(client, seed, ii_register_headers)
    response = client.post(
        f"/api/incoming-information/incoming-documents/{document['incoming_document_id']}/attachments",
        headers=ii_register_headers,
        files={"file": ("evil.pdf", b"MZ" + b"x" * 32, "application/pdf")},
    )
    assert response.status_code == 422


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_repeated_attachment_delete_returns_404(client, seed, ii_register_headers):
    document = register_test_document(client, seed, ii_register_headers)
    upload = client.post(
        f"/api/incoming-information/incoming-documents/{document['incoming_document_id']}/attachments",
        headers=ii_register_headers,
        files={"file": ("report.pdf", b"%PDF-1.4 delete", "application/pdf")},
    )
    assert upload.status_code == 200, upload.text
    attachment_id = int(upload.json()["attachment_id"])

    first = client.delete(
        f"/api/incoming-information/attachments/{attachment_id}",
        headers=ii_register_headers,
    )
    assert first.status_code == 204

    second = client.delete(
        f"/api/incoming-information/attachments/{attachment_id}",
        headers=ii_register_headers,
    )
    assert second.status_code == 404


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_concurrent_attachment_delete_does_not_return_500(client, seed, ii_register_headers):
    document = register_test_document(client, seed, ii_register_headers)
    staging_id = "c" * 32
    content = b"%PDF-1.4 concurrent"
    write_staging_attachment(staging_id, content)
    user = build_user_dict(int(seed["executor_user_id"]))
    from app.incoming_information.application.attachment_service import execute_attachment_upload

    snapshot = execute_attachment_upload(
        engine,
        user=user,
        incoming_document_id=int(document["incoming_document_id"]),
        staging_id=staging_id,
        content_type="application/pdf",
        original_filename="report.pdf",
        size_bytes=len(content),
    )

    with patch(
        "app.incoming_information.application.attachment_service.move_attachment_to_quarantine",
        side_effect=FileNotFoundError("already deleted"),
    ):
        result = execute_attachment_deletion(
            engine,
            user=user,
            attachment_id=int(snapshot.attachment_id),
        )
    assert result is not None

    with engine.connect() as conn:
        remaining = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.incoming_document_attachments
                WHERE attachment_id = :attachment_id
                """
            ),
            {"attachment_id": int(snapshot.attachment_id)},
        ).one()[0]
    assert int(remaining) == 0


def test_duplicate_link_integrity_error_maps_to_conflict():
    exc = IntegrityError("insert", {}, Exception("uq_incoming_document_operational_order_links"))
    with pytest.raises(IncomingDocumentConflictError, match="Operational order link already exists."):
        _raise_duplicate_link_conflict(exc, message="Operational order link already exists.")


def test_unknown_integrity_error_is_not_mapped_to_duplicate_link():
    exc = IntegrityError("insert", {}, Exception("fk_some_other_table"))
    with pytest.raises(IntegrityError):
        _raise_duplicate_link_conflict(exc, message="Operational order link already exists.")
