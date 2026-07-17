"""Personnel Application domain errors."""
from __future__ import annotations


class PersonnelApplicationError(Exception):
    """Base error for Personnel Application bounded context."""


class PersonnelApplicationValidationError(PersonnelApplicationError):
    """Invalid input or business rule violation."""


class PersonnelApplicationNotFoundError(PersonnelApplicationError):
    """Application row not found."""


class PersonnelApplicationConflictError(PersonnelApplicationError):
    """Conflict with existing state (e.g. active employee)."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


class ActiveEmployeeBlocksRegistrationError(PersonnelApplicationConflictError):
    def __init__(self, *, person_id: int) -> None:
        super().__init__(
            f"Active employee exists for person_id={person_id}; registration blocked.",
            code="ACTIVE_EMPLOYEE_BLOCKS_REGISTRATION",
        )
        self.person_id = person_id


class VacancyCheckGateError(PersonnelApplicationValidationError):
    """Registration requires vacancy_check_status = confirmed_visually."""

    def __init__(self) -> None:
        super().__init__(
            "Registration requires vacancy_check_status='confirmed_visually'."
        )


class PersonnelApplicationDuplicateActiveError(PersonnelApplicationConflictError):
    def __init__(self, *, person_id: int, application_id: int) -> None:
        super().__init__(
            f"Active application already exists for person_id={person_id}.",
            code="ACTIVE_APPLICATION_EXISTS",
        )
        self.person_id = person_id
        self.application_id = application_id


class PersonnelApplicationResolutionError(PersonnelApplicationError):
    """Director resolution workflow violation."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


class PersonnelApplicationHireOrderError(PersonnelApplicationError):
    """HIRE order draft creation violation."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


class PersonnelApplicationApplyError(PersonnelApplicationError):
    """HIRE apply / application completion violation."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


class PersonnelApplicationLifecycleError(PersonnelApplicationError):
    """Lifecycle transition violation (cancel, expire)."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code
