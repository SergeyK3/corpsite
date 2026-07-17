"""Apply execution ports (WP-CL-012)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Protocol

from app.control_list_import.apply_execution.models import (
    ActionExecutionOutcome,
    ApplyActionExecution,
    ApplyActionExecutionStatus,
    ApplyExecutionResult,
    ApplyExecutionRun,
    ApplyRunStatus,
)
from app.control_list_import.domain.review_models import ApplyAction


@dataclass(frozen=True, slots=True)
class ApplyExecutionContext:
    import_run_id: int
    review_run_key: str
    apply_run_id: int
    requested_by_user_id: Optional[int]


class ApplyActionExecutor(Protocol):
    """Canonical mutation boundary for one ApplyActionType."""

    def execute(
        self,
        action: ApplyAction,
        *,
        context: ApplyExecutionContext,
    ) -> ActionExecutionOutcome: ...


class ApplyExecutionRepository(Protocol):
    def get_run_by_fingerprint(self, plan_fingerprint: str) -> Optional[ApplyExecutionRun]: ...

    def get_action_by_idempotency_key(self, idempotency_key: str) -> Optional[ApplyActionExecution]: ...

    def create_run(
        self,
        *,
        import_run_id: int,
        review_run_key: str,
        plan_key: str,
        plan_fingerprint: str,
        plan_snapshot: dict[str, Any],
        requested_by_user_id: Optional[int],
        actions: tuple[ApplyActionExecution, ...],
    ) -> ApplyExecutionRun: ...

    def transition_run_status(
        self,
        apply_run_id: int,
        *,
        expected_status: ApplyRunStatus,
        target_status: ApplyRunStatus,
        failure_code: Optional[str] = None,
        failure_message: Optional[str] = None,
    ) -> ApplyExecutionRun: ...

    def transition_action_status(
        self,
        apply_action_execution_id: int,
        *,
        expected_status: ApplyActionExecutionStatus,
        target_status: ApplyActionExecutionStatus,
        result_payload: Optional[dict[str, Any]] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> ApplyActionExecution: ...

    def load_run(self, apply_run_id: int) -> Optional[ApplyExecutionRun]: ...


class ApplyExecutionUnitOfWork(Protocol):
    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    @property
    def repository(self) -> ApplyExecutionRepository: ...
