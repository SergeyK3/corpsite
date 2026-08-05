# tests/incoming_information/test_content_disposition.py
from __future__ import annotations

import pytest

from app.incoming_information.domain.content_disposition import build_attachment_content_disposition
from app.incoming_information.infrastructure.attachment_storage import write_staging_attachment
from tests.incoming_information.conftest import build_user_dict, register_test_document
from app.db.engine import engine
from app.incoming_information.application.attachment_service import execute_attachment_upload


@pytest.mark.parametrize(
    "filename,expected_ascii,expected_utf8_fragment",
    [
        ("Заключение.pdf", "attachment", "%D0%97%D0%B0%D0%BA%D0%BB%D1%8E%D1%87%D0%B5%D0%BD%D0%B8%D0%B5.pdf"),
        ("my report.pdf", "my_report.pdf", "my%20report.pdf"),
        ('say "hello".pdf', "say_hello_.pdf", "hello"),
        ("bad\r\nname.pdf", "badname.pdf", "badname.pdf"),
    ],
)
def test_content_disposition_header_safe(filename, expected_ascii, expected_utf8_fragment):
    header = build_attachment_content_disposition(filename)
    assert f'filename="{expected_ascii}"' in header
    assert "filename*=UTF-8''" in header
    assert expected_utf8_fragment in header
    assert "\r" not in header
    assert "\n" not in header


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_download_cyrillic_filename_not_500(client, seed, ii_register_headers, _incoming_info_storage_root):
    document = register_test_document(client, seed, ii_register_headers)
    document_id = int(document["incoming_document_id"])
    staging_id = "e" * 32
    content = b"%PDF-1.4 cyr"
    write_staging_attachment(staging_id, content)
    user = build_user_dict(int(seed["executor_user_id"]))
    snapshot = execute_attachment_upload(
        engine,
        user=user,
        incoming_document_id=document_id,
        staging_id=staging_id,
        content_type="application/pdf",
        original_filename="Заключение.pdf",
        size_bytes=len(content),
    )

    response = client.get(
        f"/api/incoming-information/attachments/{snapshot.attachment_id}/download",
        headers=ii_register_headers,
    )
    assert response.status_code == 200, response.text
    assert "filename*=UTF-8''" in response.headers["content-disposition"]
