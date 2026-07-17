"""ApplyPlanner — declarative apply plans without mutation (WP-CL-011)."""
from __future__ import annotations

import hashlib

from app.control_list_import.domain.contact_candidate import ContactCandidate
from app.control_list_import.domain.education_candidate import EducationCandidate
from app.control_list_import.domain.employment_candidate import EmploymentCandidate
from app.control_list_import.domain.other_ppr_candidate import OtherPprCandidate
from app.control_list_import.domain.person_match_models import MatchStatus
from app.control_list_import.domain.review_models import (
    ApplyAction,
    ApplyActionType,
    ApplyPlan,
    ControlListReviewItem,
    ControlListReviewRun,
    ReviewDecision,
)
from app.control_list_import.domain.training_candidate import TrainingCandidate
from app.db.models.control_list_mapping import EMPLOYMENT_MODE_PRIMARY

_OTHER_PPR_UNSUPPORTED_ISSUE = "other_ppr_unsupported_semantic_field"


class ApplyPlanner:
    """Build immutable declarative apply plans — no canonical writes."""

    def plan_run(self, review_run: ControlListReviewRun) -> tuple[ApplyPlan, ...]:
        return tuple(self.plan_item(item) for item in review_run.items)

    def plan_item(self, item: ControlListReviewItem) -> ApplyPlan:
        if item.decision == ReviewDecision.REJECTED:
            return self._rejected_plan(item)

        if item.decision == ReviewDecision.PENDING and _is_not_found(item):
            return ApplyPlan(
                import_run_id=item.import_run_id,
                source_row_id=item.source_row_id,
                decision=item.decision,
                actions=(
                    self._create_person_action(
                        item,
                        is_ready=False,
                        blocking_reason="review.person_not_found",
                    ),
                ),
                is_executable=False,
                blocking_reasons=("review.person_not_found",),
            )

        if item.decision != ReviewDecision.APPROVED:
            return ApplyPlan(
                import_run_id=item.import_run_id,
                source_row_id=item.source_row_id,
                decision=item.decision,
                actions=(),
                is_executable=False,
                blocking_reasons=("review.decision_not_approved",),
            )

        if item.has_blocking_issues:
            return ApplyPlan(
                import_run_id=item.import_run_id,
                source_row_id=item.source_row_id,
                decision=item.decision,
                actions=(),
                is_executable=False,
                blocking_reasons=tuple(issue.code for issue in item.blocking_issues),
            )

        person_match = item.person_match
        if person_match is None:
            return ApplyPlan(
                import_run_id=item.import_run_id,
                source_row_id=item.source_row_id,
                decision=item.decision,
                actions=(),
                is_executable=False,
                blocking_reasons=("review.person_match_missing",),
            )

        if person_match.status in {
            MatchStatus.NOT_FOUND,
            MatchStatus.AMBIGUOUS,
            MatchStatus.INVALID,
        }:
            return ApplyPlan(
                import_run_id=item.import_run_id,
                source_row_id=item.source_row_id,
                decision=item.decision,
                actions=(),
                is_executable=False,
                blocking_reasons=(f"review.person_match_{person_match.status.value}",),
            )

        actions = _dedupe_actions(self._matched_person_actions(item))
        all_ready = bool(actions) and all(action.is_ready for action in actions)
        blocking_reasons = tuple(
            action.blocking_reason
            for action in actions
            if action.blocking_reason is not None
        )
        return ApplyPlan(
            import_run_id=item.import_run_id,
            source_row_id=item.source_row_id,
            decision=item.decision,
            actions=actions,
            is_executable=all_ready and not blocking_reasons,
            blocking_reasons=blocking_reasons,
        )

    def _rejected_plan(self, item: ControlListReviewItem) -> ApplyPlan:
        return ApplyPlan(
            import_run_id=item.import_run_id,
            source_row_id=item.source_row_id,
            decision=ReviewDecision.REJECTED,
            actions=(
                ApplyAction(
                    action_type=ApplyActionType.SKIP,
                    target_aggregate="review_item",
                    source_candidate_ref=f"row:{item.source_row_id}",
                    preconditions=("review.decision_rejected",),
                    idempotency_key=_idempotency_key(
                        import_run_id=item.import_run_id,
                        source_row_id=item.source_row_id,
                        action_type=ApplyActionType.SKIP,
                        ref_suffix="rejected",
                    ),
                    is_ready=True,
                ),
            ),
            is_executable=False,
            blocking_reasons=("review.decision_rejected",),
        )

    def _matched_person_actions(self, item: ControlListReviewItem) -> tuple[ApplyAction, ...]:
        actions: list[ApplyAction] = []
        person_id = item.person_match.recommended_person_id if item.person_match else None
        preconditions = (
            "review.decision_approved",
            "person_match.exact_or_probable",
            f"person_id={person_id}",
        )

        if item.contact_candidate is not None:
            actions.append(self._contact_action(item, item.contact_candidate, preconditions))

        if item.employment_candidate is not None:
            actions.append(self._employment_action(item, item.employment_candidate, preconditions))

        for candidate in item.education_candidates:
            actions.append(self._education_action(item, candidate, preconditions))

        for candidate in item.training_candidates:
            actions.append(self._training_action(item, candidate, preconditions))

        for candidate in item.other_ppr_candidates:
            actions.append(self._other_ppr_action(item, candidate, preconditions))

        return tuple(actions)

    def _contact_action(
        self,
        item: ControlListReviewItem,
        candidate: ContactCandidate,
        base_preconditions: tuple[str, ...],
    ) -> ApplyAction:
        ready = candidate.is_normalization_ready
        return ApplyAction(
            action_type=ApplyActionType.UPDATE_PERSON_CONTACT,
            target_aggregate="person.contacts",
            source_candidate_ref=f"contact:row:{candidate.source_row_id}",
            preconditions=base_preconditions + ("contact.normalization_ready",),
            idempotency_key=_idempotency_key(
                import_run_id=item.import_run_id,
                source_row_id=item.source_row_id,
                action_type=ApplyActionType.UPDATE_PERSON_CONTACT,
                ref_suffix="contact",
            ),
            is_ready=ready,
            blocking_reason=None if ready else "contact.not_normalization_ready",
        )

    def _employment_action(
        self,
        item: ControlListReviewItem,
        candidate: EmploymentCandidate,
        base_preconditions: tuple[str, ...],
    ) -> ApplyAction:
        """Employment BC assignment resolution for primary and concurrent internal modes."""
        ready = candidate.is_normalization_ready
        employment_mode = candidate.employment_mode or EMPLOYMENT_MODE_PRIMARY
        return ApplyAction(
            action_type=ApplyActionType.RESOLVE_ASSIGNMENT,
            target_aggregate="employment.assignment",
            source_candidate_ref=f"employment:row:{candidate.source_row_id}",
            preconditions=base_preconditions
            + (
                "employment.normalization_ready",
                f"employment_mode={employment_mode}",
            ),
            idempotency_key=_idempotency_key(
                import_run_id=item.import_run_id,
                source_row_id=item.source_row_id,
                action_type=ApplyActionType.RESOLVE_ASSIGNMENT,
                ref_suffix=f"employment:assignment:{employment_mode}",
            ),
            is_ready=ready,
            blocking_reason=None if ready else "employment.not_normalization_ready",
        )

    def _education_action(
        self,
        item: ControlListReviewItem,
        candidate: EducationCandidate,
        base_preconditions: tuple[str, ...],
    ) -> ApplyAction:
        ready = candidate.is_normalization_ready
        ref_suffix = f"education:{candidate.source_column_index}:{candidate.source_fragment_index}"
        return ApplyAction(
            action_type=ApplyActionType.ADD_EDUCATION,
            target_aggregate="ppr.education",
            source_candidate_ref=(
                f"education:row:{candidate.source_row_id}:"
                f"col:{candidate.source_column_index}:frag:{candidate.source_fragment_index}"
            ),
            preconditions=base_preconditions + ("education.normalization_ready",),
            idempotency_key=_idempotency_key(
                import_run_id=item.import_run_id,
                source_row_id=item.source_row_id,
                action_type=ApplyActionType.ADD_EDUCATION,
                ref_suffix=ref_suffix,
            ),
            is_ready=ready,
            blocking_reason=None if ready else "education.not_normalization_ready",
        )

    def _training_action(
        self,
        item: ControlListReviewItem,
        candidate: TrainingCandidate,
        base_preconditions: tuple[str, ...],
    ) -> ApplyAction:
        ready = candidate.is_normalization_ready
        ref_suffix = f"training:{candidate.source_column_index}:{candidate.source_fragment_index}"
        return ApplyAction(
            action_type=ApplyActionType.ADD_TRAINING,
            target_aggregate="ppr.training",
            source_candidate_ref=(
                f"training:row:{candidate.source_row_id}:"
                f"col:{candidate.source_column_index}:frag:{candidate.source_fragment_index}"
            ),
            preconditions=base_preconditions + ("training.normalization_ready",),
            idempotency_key=_idempotency_key(
                import_run_id=item.import_run_id,
                source_row_id=item.source_row_id,
                action_type=ApplyActionType.ADD_TRAINING,
                ref_suffix=ref_suffix,
            ),
            is_ready=ready,
            blocking_reason=None if ready else "training.not_normalization_ready",
        )

    def _other_ppr_action(
        self,
        item: ControlListReviewItem,
        candidate: OtherPprCandidate,
        base_preconditions: tuple[str, ...],
    ) -> ApplyAction:
        unsupported = _OTHER_PPR_UNSUPPORTED_ISSUE in candidate.all_issues
        ready = candidate.is_normalization_ready and not unsupported
        ref_suffix = f"other_ppr:{candidate.source_column_index}:{candidate.semantic_field}"
        blocking_reason: str | None
        if unsupported:
            blocking_reason = "other_ppr.unsupported_semantic_field"
        elif not ready:
            blocking_reason = "other_ppr.not_normalization_ready"
        else:
            blocking_reason = None
        return ApplyAction(
            action_type=ApplyActionType.UPDATE_OTHER_PPR_FIELD,
            target_aggregate="ppr.other_fields",
            source_candidate_ref=(
                f"other_ppr:row:{candidate.source_row_id}:"
                f"col:{candidate.source_column_index}:field:{candidate.semantic_field}"
            ),
            preconditions=base_preconditions
            + ("other_ppr.normalization_ready", f"semantic_field={candidate.semantic_field}"),
            idempotency_key=_idempotency_key(
                import_run_id=item.import_run_id,
                source_row_id=item.source_row_id,
                action_type=ApplyActionType.UPDATE_OTHER_PPR_FIELD,
                ref_suffix=ref_suffix,
            ),
            is_ready=ready,
            blocking_reason=blocking_reason,
        )

    def _create_person_action(
        self,
        item: ControlListReviewItem,
        *,
        is_ready: bool,
        blocking_reason: str,
    ) -> ApplyAction:
        return ApplyAction(
            action_type=ApplyActionType.CREATE_PERSON,
            target_aggregate="person",
            source_candidate_ref=f"person:row:{item.source_row_id}",
            preconditions=("review.explicit_create_person_required",),
            idempotency_key=_idempotency_key(
                import_run_id=item.import_run_id,
                source_row_id=item.source_row_id,
                action_type=ApplyActionType.CREATE_PERSON,
                ref_suffix="create_person",
            ),
            is_ready=is_ready,
            blocking_reason=blocking_reason,
        )


def _is_not_found(item: ControlListReviewItem) -> bool:
    return (
        item.person_match is not None
        and item.person_match.status == MatchStatus.NOT_FOUND
    )


def _dedupe_actions(actions: tuple[ApplyAction, ...]) -> tuple[ApplyAction, ...]:
    seen: set[str] = set()
    deduped: list[ApplyAction] = []
    for action in actions:
        if action.idempotency_key in seen:
            continue
        seen.add(action.idempotency_key)
        deduped.append(action)
    return tuple(deduped)


def _idempotency_key(
    *,
    import_run_id: int | None,
    source_row_id: int | None,
    action_type: ApplyActionType,
    ref_suffix: str,
) -> str:
    payload = f"cl:{import_run_id}:row:{source_row_id}:{action_type.value}:{ref_suffix}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"cl-apply:{digest[:32]}"
