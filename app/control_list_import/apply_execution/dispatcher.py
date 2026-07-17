"""Apply action dispatcher (WP-CL-012)."""
from __future__ import annotations

from app.control_list_import.apply_execution.executors import (
    DEFERRED_REASON_BY_ACTION,
    DeferredApplyActionExecutor,
    SkipApplyActionExecutor,
)
from app.control_list_import.apply_execution.ports import ApplyActionExecutor
from app.control_list_import.domain.review_models import ApplyActionType


class ApplyActionDispatcher:
    """Select executor by ApplyActionType — no direct ORM canonical writes."""

    def __init__(self, executors: dict[ApplyActionType, ApplyActionExecutor] | None = None) -> None:
        if executors is not None:
            self._executors = executors
            return
        skip = SkipApplyActionExecutor()
        self._executors = {
            ApplyActionType.SKIP: skip,
        }
        for action_type, reason in DEFERRED_REASON_BY_ACTION.items():
            self._executors[action_type] = DeferredApplyActionExecutor(reason=reason)

    def resolve(self, action_type: ApplyActionType) -> ApplyActionExecutor:
        if action_type not in self._executors:
            return DeferredApplyActionExecutor(reason="unsupported_action_type")
        return self._executors[action_type]
