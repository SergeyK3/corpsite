"""Employee onboarding domain errors (WP-ONBOARDING-001)."""
from __future__ import annotations


class EmployeeOnboardingError(Exception):
    def __init__(self, message: str, *, code: str = "ONBOARDING_ERROR") -> None:
        super().__init__(message)
        self.code = code


class EmployeeOnboardingNotFoundError(EmployeeOnboardingError):
    def __init__(self, message: str = "Onboarding not found.") -> None:
        super().__init__(message, code="ONBOARDING_NOT_FOUND")


class EmployeeOnboardingChecklistError(EmployeeOnboardingError):
    pass
