# tests/incoming_information/test_attachment_upload_limits.py
from __future__ import annotations

import asyncio

import pytest

from app.incoming_information.application.attachment_upload import stream_upload_file_to_staging
from app.incoming_information.domain.attachment_validation import INCOMING_ATTACHMENT_MAX_BYTES
from app.incoming_information.domain.errors import IncomingDocumentPayloadTooLargeError
from app.incoming_information.infrastructure.attachment_storage import list_orphan_paths_in_root
from tests.incoming_information.conftest import register_test_document


class _ChunkedUpload:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = list(chunks)
        self._index = 0

    async def read(self, size: int = -1) -> bytes:
        if self._index >= len(self._chunks):
            return b""
        chunk = self._chunks[self._index]
        self._index += 1
        return chunk


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_upload_exactly_max_size_accepted(client, seed, ii_register_headers, _incoming_info_storage_root):
    document = register_test_document(client, seed, ii_register_headers)
    content = b"%PDF-1.4" + b"x" * (INCOMING_ATTACHMENT_MAX_BYTES - 8)
    assert len(content) == INCOMING_ATTACHMENT_MAX_BYTES
    response = client.post(
        f"/api/incoming-information/incoming-documents/{document['incoming_document_id']}/attachments",
        headers=ii_register_headers,
        files={"file": ("max.pdf", content, "application/pdf")},
    )
    assert response.status_code == 200, response.text
    assert not list_orphan_paths_in_root()


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_upload_one_byte_over_max_rejected(client, seed, ii_register_headers, _incoming_info_storage_root):
    document = register_test_document(client, seed, ii_register_headers)
    content = b"%PDF-1.4" + b"x" * (INCOMING_ATTACHMENT_MAX_BYTES - 7)
    assert len(content) == INCOMING_ATTACHMENT_MAX_BYTES + 1
    response = client.post(
        f"/api/incoming-information/incoming-documents/{document['incoming_document_id']}/attachments",
        headers=ii_register_headers,
        files={"file": ("too-big.pdf", content, "application/pdf")},
    )
    assert response.status_code == 413
    assert not list_orphan_paths_in_root()


def test_stream_without_content_length_is_limited(_incoming_info_storage_root):
    staging_id = "f" * 32
    chunk = b"x" * (512 * 1024)
    chunks = [b"%PDF-1.4"] + [chunk] * 21

    async def _run() -> None:
        with pytest.raises(IncomingDocumentPayloadTooLargeError):
            await stream_upload_file_to_staging(_ChunkedUpload(chunks), staging_id)

    asyncio.run(_run())
    assert not list_orphan_paths_in_root()
