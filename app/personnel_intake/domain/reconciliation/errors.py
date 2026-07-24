"""Domain errors for reconciliation decision foundation."""
from __future__ import annotations


class ReconciliationError(Exception):
    """Base error for reconciliation decision persistence."""


class ReconciliationValidationError(ReconciliationError):
    """Invalid action, status, transition, or create payload."""

    def __init__(self, message: str, *, code: str = "RECONCILIATION_VALIDATION") -> None:
        super().__init__(message)
        self.code = code


class ReconciliationNotFoundError(ReconciliationError):
    """Decision not found."""

    def __init__(self, message: str, *, code: str = "RECONCILIATION_NOT_FOUND") -> None:
        super().__init__(message)
        self.code = code


class ReconciliationConflictError(ReconciliationError):
    """Idempotency key reused with a different intent payload."""

    def __init__(self, message: str, *, code: str = "RECONCILIATION_IDEMPOTENCY_CONFLICT") -> None:
        super().__init__(message)
        self.code = code


class ReconciliationConcurrencyError(ReconciliationError):
    """Optimistic concurrency failure (stale row_version)."""

    def __init__(self, message: str, *, code: str = "RECONCILIATION_STALE_ROW_VERSION") -> None:
        super().__init__(message)
        self.code = code
