"""Domain errors for person photo canonicalization."""
from __future__ import annotations


class PersonPhotoError(Exception):
    """Base error for person photo operations."""


class IntakePhotoUnavailableError(PersonPhotoError):
    """Intake source bytes are missing or unreadable."""


class ApplicationNotFoundError(PersonPhotoError):
    """Personnel application referenced by the request does not exist."""


class ApplicationPersonMismatchError(PersonPhotoError):
    """Application person_id does not match the requested person."""


class CanonicalFileCollisionError(PersonPhotoError):
    """Canonical destination path already exists for the generated file id."""


class PhotoCanonicalizationError(PersonPhotoError):
    """Canonical file preparation or persistence failed."""


class LedgerPersonMismatchError(PersonPhotoError):
    """Provenance ledger person_id does not match the expected person."""


class CanonicalFileMissingError(PersonPhotoError):
    """Canonical file referenced by ledger/DB row is missing on disk."""


class CanonicalFileIntegrityError(PersonPhotoError):
    """Canonical file failed replay validation (checksum or JPEG rules)."""
