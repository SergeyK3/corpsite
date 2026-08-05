"""Incoming document attachment validation."""
from __future__ import annotations

import re
from typing import Final

from app.incoming_information.domain.errors import IncomingDocumentValidationError

INCOMING_ATTACHMENT_MAX_BYTES: Final[int] = 10 * 1024 * 1024
INCOMING_ATTACHMENT_ALLOWED_CONTENT_TYPES: Final[frozenset[str]] = frozenset(
    {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "text/plain",
    }
)

_EXECUTABLE_SIGNATURES: Final[tuple[bytes, ...]] = (
    b"MZ",
    b"\x7fELF",
)

_CONTENT_TYPE_EXTENSIONS: Final[dict[str, str]] = {
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/png": "png",
    "text/plain": "txt",
}


def storage_extension_for_content_type(content_type: str | None) -> str:
    normalized_type = str(content_type or "").strip().lower().split(";", 1)[0]
    if normalized_type not in INCOMING_ATTACHMENT_ALLOWED_CONTENT_TYPES:
        raise IncomingDocumentValidationError("Attachment content type is not allowed.")
    return _CONTENT_TYPE_EXTENSIONS[normalized_type]


def allowed_extensions_for_content_type(content_type: str | None) -> frozenset[str]:
    ext = storage_extension_for_content_type(content_type)
    aliases = {ext}
    if ext == "jpg":
        aliases.add("jpeg")
    return frozenset(aliases)


def validate_filename_extension_for_content_type(
    original_filename: str,
    *,
    content_type: str | None,
) -> None:
    parts = str(original_filename or "").rsplit(".", 1)
    if len(parts) != 2 or not parts[1]:
        return
    filename_ext = parts[1].lower()
    if not filename_ext.isalnum() or len(filename_ext) > 8:
        raise IncomingDocumentValidationError("Attachment filename extension is invalid.")
    allowed = allowed_extensions_for_content_type(content_type)
    if filename_ext not in allowed:
        raise IncomingDocumentValidationError("Filename extension does not match content type.")


def _contains_executable_signature(content: bytes) -> bool:
    head = content[:512]
    return any(head.startswith(signature) for signature in _EXECUTABLE_SIGNATURES)


def _validate_plain_text_bytes(content: bytes) -> None:
    sample = content[:8192]
    if b"\x00" in sample:
        raise IncomingDocumentValidationError("Attachment is not valid plain text.")
    if _contains_executable_signature(content):
        raise IncomingDocumentValidationError("Executable attachments are not allowed.")
    if content.startswith(b"%PDF") or content.startswith(b"\xff\xd8") or content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise IncomingDocumentValidationError("Attachment content does not match plain text.")
    if content.startswith(b"PK\x03\x04"):
        raise IncomingDocumentValidationError("Attachment content does not match plain text.")


def validate_incoming_attachment_bytes(content: bytes, *, content_type: str | None) -> str:
    if not content:
        raise IncomingDocumentValidationError("Attachment file is empty.")
    if len(content) > INCOMING_ATTACHMENT_MAX_BYTES:
        raise IncomingDocumentValidationError("Attachment exceeds 10 MB limit.")

    normalized_type = str(content_type or "").strip().lower().split(";", 1)[0]
    if not normalized_type or normalized_type not in INCOMING_ATTACHMENT_ALLOWED_CONTENT_TYPES:
        raise IncomingDocumentValidationError("Attachment content type is not allowed.")

    head = content[:512]
    if head.startswith(b"<?xml") or b"<svg" in head[:256].lower():
        raise IncomingDocumentValidationError("SVG/XML attachments are not allowed.")
    if _contains_executable_signature(content):
        raise IncomingDocumentValidationError("Executable attachments are not allowed.")

    if normalized_type == "application/pdf" and not content.startswith(b"%PDF"):
        raise IncomingDocumentValidationError("Attachment is not a valid PDF.")
    if normalized_type == "image/jpeg" and not content.startswith(b"\xff\xd8"):
        raise IncomingDocumentValidationError("Attachment is not a valid JPEG.")
    if normalized_type == "image/png" and not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise IncomingDocumentValidationError("Attachment is not a valid PNG.")
    if normalized_type == "text/plain":
        _validate_plain_text_bytes(content)

    return storage_extension_for_content_type(normalized_type)
