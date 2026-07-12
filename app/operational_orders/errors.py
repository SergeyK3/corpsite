"""Domain-level errors for Operational Orders intake."""
from __future__ import annotations


class OperationalOrderError(RuntimeError):
    code: str = "OO_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


class OperationalOrderWorkspaceNotFoundError(LookupError):
    code = "OO_WORKSPACE_NOT_FOUND"


class OperationalOrderBlockNotFoundError(LookupError):
    code = "OO_BLOCK_NOT_FOUND"


class OperationalOrderVersionConflictError(OperationalOrderError):
    code = "OO_WORKSPACE_VERSION_CONFLICT"


class OperationalOrderSubmittedTextImmutableError(OperationalOrderError):
    code = "OO_SUBMITTED_TEXT_IMMUTABLE"


class OperationalOrderInvalidWorkspaceStageError(OperationalOrderError):
    code = "OO_INVALID_WORKSPACE_STAGE"


class OperationalOrderValidationBlockedError(OperationalOrderError):
    code = "OO_VALIDATION_BLOCKED"


class OperationalOrderClarificationRequiredError(OperationalOrderError):
    code = "OO_CLARIFICATION_REQUIRED"


class OperationalOrderForbiddenError(PermissionError):
    code = "OO_FORBIDDEN"


class OperationalOrderClarificationNotFoundError(LookupError):
    code = "OO_CLARIFICATION_NOT_FOUND"


class OperationalOrderProvenanceRequiredError(OperationalOrderError):
    code = "OO_PROVENANCE_REQUIRED"


class OperationalOrderValidationError(ValueError):
    """Input validation failure before persistence."""
