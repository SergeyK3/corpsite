"""Apply execution domain models (WP-CL-012) — no SQLAlchemy dependency."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Optional

from app.control_list_import.apply_execution.errors import (
    ApplyActionTransitionError,
    ApplyRunTransitionError,
)


class ApplyRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ApplyActionExecutionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    SKIPPED = "skipped"
    DEFERRED = "deferred"
    FAILED = "failed"


TERMINAL_RUN_STATUSES = frozenset(
    {
        ApplyRunStatus.SUCCEEDED,
        ApplyRunStatus.PARTIALLY_SUCCEEDED,
        ApplyRunStatus.FAILED,
        ApplyRunStatus.CANCELLED,
    }
)

TERMINAL_ACTION_STATUSES = frozenset(
    {
        ApplyActionExecutionStatus.SUCCEEDED,
        ApplyActionExecutionStatus.SKIPPED,
        ApplyActionExecutionStatus.DEFERRED,
        ApplyActionExecutionStatus.FAILED,
    }
)

ALLOWED_RUN_TRANSITIONS: dict[ApplyRunStatus, frozenset[ApplyRunStatus]] = {
    ApplyRunStatus.PENDING: frozenset({ApplyRunStatus.RUNNING, ApplyRunStatus.CANCELLED}),
    ApplyRunStatus.RUNNING: frozenset(
        {
            ApplyRunStatus.SUCCEEDED,
            ApplyRunStatus.PARTIALLY_SUCCEEDED,
            ApplyRunStatus.FAILED,
            ApplyRunStatus.CANCELLED,
        }
    ),
    ApplyRunStatus.SUCCEEDED: frozenset(),
    ApplyRunStatus.PARTIALLY_SUCCEEDED: frozenset(),
    ApplyRunStatus.FAILED: frozenset(),
    ApplyRunStatus.CANCELLED: frozenset(),
}

ALLOWED_ACTION_TRANSITIONS: dict[ApplyActionExecutionStatus, frozenset[ApplyActionExecutionStatus]] = {
    ApplyActionExecutionStatus.PENDING: frozenset({ApplyActionExecutionStatus.RUNNING}),
    ApplyActionExecutionStatus.RUNNING: frozenset(
        {
            ApplyActionExecutionStatus.SUCCEEDED,
            ApplyActionExecutionStatus.SKIPPED,
            ApplyActionExecutionStatus.DEFERRED,
            ApplyActionExecutionStatus.FAILED,
        }
    ),
    ApplyActionExecutionStatus.SUCCEEDED: frozenset(),
    ApplyActionExecutionStatus.SKIPPED: frozenset(),
    ApplyActionExecutionStatus.DEFERRED: frozenset(),
    ApplyActionExecutionStatus.FAILED: frozenset(),
}


def assert_run_transition(current: ApplyRunStatus, target: ApplyRunStatus) -> None:
    allowed = ALLOWED_RUN_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise ApplyRunTransitionError(
            f"Invalid apply run transition: {current.value} -> {target.value}"
        )


def assert_action_transition(
    current: ApplyActionExecutionStatus,
    target: ApplyActionExecutionStatus,
) -> None:
    allowed = ALLOWED_ACTION_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise ApplyActionTransitionError(
            f"Invalid apply action transition: {current.value} -> {target.value}"
        )


@dataclass(frozen=True, slots=True)
class ActionExecutionOutcome:
    status: ApplyActionExecutionStatus
    result_payload: dict[str, Any] = field(default_factory=dict)
    error_code: Optional[str] = None
    error_message: Optional[str] = None


@dataclass(frozen=True, slots=True)
class ApplyActionExecution:
    apply_action_execution_id: Optional[int]
    apply_run_id: Optional[int]
    action_index: int
    action_type: str
    target_aggregate: str
    source_reference: str
    idempotency_key: str
    action_fingerprint: str
    status: ApplyActionExecutionStatus = ApplyActionExecutionStatus.PENDING
    attempt_count: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    result_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ApplyExecutionRun:
    apply_run_id: Optional[int]
    import_run_id: int
    review_run_key: str
    plan_key: str
    plan_fingerprint: str
    plan_snapshot: dict[str, Any]
    status: ApplyRunStatus = ApplyRunStatus.PENDING
    requested_by_user_id: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None
    actions: tuple[ApplyActionExecution, ...] = ()


@dataclass(frozen=True, slots=True)
class ApplyExecutionResult:
    apply_run_id: int
    import_run_id: int
    review_run_key: str
    plan_fingerprint: str
    status: ApplyRunStatus
    action_outcomes: tuple[ActionExecutionOutcome, ...]
    idempotent_replay: bool = False
    summary: dict[str, Any] = field(default_factory=dict)
