"""Incoming Information domain errors."""
from __future__ import annotations


class IncomingInformationError(Exception):
    code: str = "INCOMING_INFO_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class IncomingDocumentNotFoundError(IncomingInformationError):
    code = "INCOMING_DOCUMENT_NOT_FOUND"


class IncomingDocumentValidationError(IncomingInformationError):
    code = "INCOMING_DOCUMENT_VALIDATION_FAILED"


class IncomingDocumentForbiddenError(IncomingInformationError):
    code = "INCOMING_DOCUMENT_FORBIDDEN"


class IncomingDocumentConflictError(IncomingInformationError):
    code = "INCOMING_DOCUMENT_CONFLICT"


class IncomingDocumentVersionConflictError(IncomingDocumentConflictError):
    code = "VERSION_CONFLICT"


class IncomingDocumentInvalidTransitionError(IncomingDocumentValidationError):
    code = "INVALID_STATUS_TRANSITION"


class IncomingAttachmentNotFoundError(IncomingInformationError):
    code = "INCOMING_ATTACHMENT_NOT_FOUND"


class IncomingDocumentPayloadTooLargeError(IncomingInformationError):
    code = "INCOMING_ATTACHMENT_TOO_LARGE"
