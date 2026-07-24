"""Personnel verification domain error → HTTP mapping (WP-VER-005A)."""
from __future__ import annotations

from fastapi import HTTPException

from app.personnel_verification.domain.errors import (
    AttestationImmutableError,
    AttestationValidationError,
    CanonicalRecordUnavailableError,
    ControlledRecordNotFoundError,
    ControlPointNotAllowedError,
    PersonnelVerificationError,
    PolicyNotFoundError,
    PolicyValidationError,
    RevisionConflictError,
    TaskNotFoundError,
    TaskValidationError,
)


def map_personnel_verification_error(exc: Exception) -> HTTPException | None:
    if isinstance(exc, (TaskNotFoundError, ControlledRecordNotFoundError, PolicyNotFoundError)):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, RevisionConflictError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(
        exc,
        (
            TaskValidationError,
            PolicyValidationError,
            AttestationValidationError,
            AttestationImmutableError,
            CanonicalRecordUnavailableError,
            ControlPointNotAllowedError,
        ),
    ):
        return HTTPException(status_code=422, detail=str(exc))
    if isinstance(exc, PersonnelVerificationError):
        return HTTPException(status_code=422, detail=str(exc))
    return None
