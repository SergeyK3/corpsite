"""Streaming upload helpers for incoming attachments."""
from __future__ import annotations

from typing import BinaryIO

from app.incoming_information.domain.attachment_validation import INCOMING_ATTACHMENT_MAX_BYTES
from app.incoming_information.domain.errors import IncomingDocumentPayloadTooLargeError
from app.incoming_information.infrastructure.attachment_storage import (
    delete_staging_attachment,
    staging_attachment_path,
)

_READ_CHUNK_SIZE = 64 * 1024


async def stream_upload_file_to_staging(
    upload,
    staging_id: str,
    *,
    max_bytes: int = INCOMING_ATTACHMENT_MAX_BYTES,
) -> int:
    """Read UploadFile in chunks into staging; enforce max size without trusting Content-Length."""
    path = staging_attachment_path(staging_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    try:
        with path.open("wb") as handle:
            while True:
                chunk = await upload.read(_READ_CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise IncomingDocumentPayloadTooLargeError(
                        "Attachment exceeds 10 MB limit."
                    )
                handle.write(chunk)
        if total == 0:
            delete_staging_attachment(staging_id)
            from app.incoming_information.domain.errors import IncomingDocumentValidationError

            raise IncomingDocumentValidationError("Attachment file is empty.")
        return total
    except Exception:
        delete_staging_attachment(staging_id)
        raise


def stream_bytes_to_staging(staging_id: str, source: BinaryIO, *, max_bytes: int = INCOMING_ATTACHMENT_MAX_BYTES) -> int:
    path = staging_attachment_path(staging_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    try:
        with path.open("wb") as handle:
            while True:
                chunk = source.read(_READ_CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise IncomingDocumentPayloadTooLargeError(
                        "Attachment exceeds 10 MB limit."
                    )
                handle.write(chunk)
        return total
    except Exception:
        delete_staging_attachment(staging_id)
        raise
