"""Apply action executors — deferred/skip foundation (WP-CL-012)."""
from __future__ import annotations

from app.control_list_import.apply_execution.models import ActionExecutionOutcome, ApplyActionExecutionStatus
from app.control_list_import.apply_execution.ports import ApplyExecutionContext
from app.control_list_import.domain.review_models import ApplyAction, ApplyActionType


class SkipApplyActionExecutor:
    def execute(
        self,
        action: ApplyAction,
        *,
        context: ApplyExecutionContext,
    ) -> ActionExecutionOutcome:
        return ActionExecutionOutcome(
            status=ApplyActionExecutionStatus.SKIPPED,
            result_payload={
                "reason": "review.decision_rejected",
                "source_candidate_ref": action.source_candidate_ref,
            },
        )


class DeferredApplyActionExecutor:
    def __init__(self, *, reason: str) -> None:
        self._reason = reason

    def execute(
        self,
        action: ApplyAction,
        *,
        context: ApplyExecutionContext,
    ) -> ActionExecutionOutcome:
        return ActionExecutionOutcome(
            status=ApplyActionExecutionStatus.DEFERRED,
            result_payload={
                "reason": self._reason,
                "action_type": action.action_type.value,
                "source_candidate_ref": action.source_candidate_ref,
            },
        )


DEFERRED_REASON_BY_ACTION: dict[ApplyActionType, str] = {
    ApplyActionType.CREATE_PERSON: "explicit_person_creation_command_not_integrated",
    ApplyActionType.UPDATE_PERSON_CONTACT: "contact_update_command_not_integrated",
    ApplyActionType.RESOLVE_ASSIGNMENT: "assignment_resolution_requires_explicit_hr_decision",
    ApplyActionType.CREATE_EXTERNAL_EMPLOYMENT: "external_employment_command_not_integrated",
    ApplyActionType.ADD_EDUCATION: "education_candidate_mapping_not_integrated",
    ApplyActionType.ADD_TRAINING: "training_candidate_mapping_not_integrated",
    ApplyActionType.UPDATE_OTHER_PPR_FIELD: "no_canonical_command_mapping",
}
