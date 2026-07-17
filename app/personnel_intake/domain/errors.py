"""Personnel Intake domain errors."""
from __future__ import annotations


class PersonnelIntakeError(Exception):
    """Base error for Personnel Intake bounded context."""


class PersonnelIntakeValidationError(PersonnelIntakeError):
    """Invalid input or business rule violation."""


class PersonnelIntakeNotFoundError(PersonnelIntakeError):
    """Intake resource not found."""


class PersonnelIntakeTokenError(PersonnelIntakeError):
    """Token invalid, expired, revoked, or already submitted."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


class PersonnelIntakeConflictError(PersonnelIntakeError):
    """Conflict with existing state."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


class PersonnelIntakeReviewError(PersonnelIntakeError):
    """Review workflow violation."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


class PersonnelIntakeTransferError(PersonnelIntakeError):
    """Transfer to PPR failed or blocked."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code
