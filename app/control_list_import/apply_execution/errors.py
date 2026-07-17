"""Apply execution errors (WP-CL-012)."""
from __future__ import annotations


class ApplyExecutionError(Exception):
    """Base apply execution failure."""

    code: str = "apply_execution_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class ApplyPreconditionError(ApplyExecutionError):
    code = "apply_precondition_failed"


class ApplyIdempotencyConflict(ApplyExecutionError):
    code = "apply_idempotency_conflict"


class ApplyExecutionInProgress(ApplyExecutionError):
    code = "apply_execution_in_progress"


class ApplyExecutionRetryRequired(ApplyExecutionError):
    code = "apply_execution_retry_required"


class ApplyRunTransitionError(ApplyExecutionError):
    code = "apply_run_transition_invalid"


class ApplyActionTransitionError(ApplyExecutionError):
    code = "apply_action_transition_invalid"
