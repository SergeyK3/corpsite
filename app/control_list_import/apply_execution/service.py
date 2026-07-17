"""Apply execution service (WP-CL-012)."""
from __future__ import annotations

import re
from typing import Any, Callable, Optional

from app.control_list_import.apply_execution.dispatcher import ApplyActionDispatcher
from app.control_list_import.apply_execution.errors import (
    ApplyExecutionInProgress,
    ApplyExecutionRetryRequired,
    ApplyIdempotencyConflict,
    ApplyPreconditionError,
)
from app.control_list_import.apply_execution.executors import DEFERRED_REASON_BY_ACTION
from app.control_list_import.apply_execution.models import (
    ActionExecutionOutcome,
    ApplyActionExecution,
    ApplyActionExecutionStatus,
    ApplyExecutionResult,
    ApplyExecutionRun,
    ApplyRunStatus,
    assert_action_transition,
)
from app.control_list_import.apply_execution.plan_snapshot import (
    compute_action_fingerprint,
    compute_plan_fingerprint,
    plan_snapshot_and_fingerprint,
    validate_plan_fingerprint,
)
from app.control_list_import.apply_execution.ports import ApplyExecutionContext, ApplyExecutionUnitOfWork
from app.control_list_import.domain.review_models import ApplyAction, ApplyActionType, ApplyPlan, ReviewDecision

_PERSON_ID_PATTERN = re.compile(r"^person_id=(\d+)$")


class ApplyExecutionService:
    """Execute approved ApplyPlan through canonical executor boundaries."""

    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], ApplyExecutionUnitOfWork],
        dispatcher: ApplyActionDispatcher | None = None,
        import_run_status_checker: Callable[[int], bool] | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._dispatcher = dispatcher or ApplyActionDispatcher()
        self._import_run_status_checker = import_run_status_checker or (lambda _run_id: True)

    def execute_approved_plan(
        self,
        *,
        import_run_id: int,
        review_run_key: str,
        apply_plan: ApplyPlan,
        requested_by_user_id: Optional[int] = None,
        plan_fingerprint: str | None = None,
    ) -> ApplyExecutionResult:
        self._validate_plan_preconditions(import_run_id=import_run_id, apply_plan=apply_plan)

        snapshot, fingerprint, plan_key = plan_snapshot_and_fingerprint(
            apply_plan,
            review_run_key=review_run_key,
        )
        if plan_fingerprint is not None:
            try:
                validate_plan_fingerprint(
                    apply_plan,
                    review_run_key=review_run_key,
                    expected_fingerprint=plan_fingerprint,
                )
            except ValueError as exc:
                raise ApplyIdempotencyConflict(str(exc)) from exc

        uow = self._unit_of_work_factory()
        repo = uow.repository

        existing = repo.get_run_by_fingerprint(fingerprint)
        if existing is not None:
            return self._handle_existing_run(
                existing,
                apply_plan=apply_plan,
                review_run_key=review_run_key,
            )

        action_rows = self._build_action_rows(apply_plan, repo=repo)
        run = repo.create_run(
            import_run_id=import_run_id,
            review_run_key=review_run_key,
            plan_key=plan_key,
            plan_fingerprint=fingerprint,
            plan_snapshot=snapshot,
            requested_by_user_id=requested_by_user_id,
            actions=action_rows,
        )
        uow.commit()

        return self._execute_run(run.apply_run_id, requested_by_user_id=requested_by_user_id)

    def _handle_existing_run(
        self,
        existing: ApplyExecutionRun,
        *,
        apply_plan: ApplyPlan,
        review_run_key: str,
    ) -> ApplyExecutionResult:
        self._validate_persisted_plan_identity(existing, apply_plan=apply_plan, review_run_key=review_run_key)
        if existing.status == ApplyRunStatus.RUNNING:
            raise ApplyExecutionInProgress(
                f"Apply run {existing.apply_run_id} is already running for plan fingerprint"
            )
        if existing.status == ApplyRunStatus.FAILED:
            raise ApplyExecutionRetryRequired(
                f"Apply run {existing.apply_run_id} failed — explicit retry required"
            )
        if existing.status in {ApplyRunStatus.SUCCEEDED, ApplyRunStatus.PARTIALLY_SUCCEEDED}:
            return self._result_from_run(existing, idempotent_replay=True)
        if existing.status == ApplyRunStatus.PENDING:
            raise ApplyExecutionInProgress(
                f"Apply run {existing.apply_run_id} is pending/incomplete for plan fingerprint"
            )
        raise ApplyPreconditionError(
            f"Apply run {existing.apply_run_id} has non-replayable status {existing.status.value}"
        )

    def _execute_run(
        self,
        apply_run_id: int,
        *,
        requested_by_user_id: Optional[int],
    ) -> ApplyExecutionResult:
        uow = self._unit_of_work_factory()
        repo = uow.repository
        run = repo.load_run(apply_run_id)
        if run is None:
            raise ApplyPreconditionError(f"Apply run {apply_run_id} not found")

        run = repo.transition_run_status(
            apply_run_id,
            expected_status=ApplyRunStatus.PENDING,
            target_status=ApplyRunStatus.RUNNING,
        )
        uow.commit()

        outcomes: list[ActionExecutionOutcome] = []
        context = ApplyExecutionContext(
            import_run_id=run.import_run_id,
            review_run_key=run.review_run_key,
            apply_run_id=run.apply_run_id or apply_run_id,
            requested_by_user_id=requested_by_user_id,
        )

        ordered_actions = sorted(run.actions, key=lambda action: action.action_index)
        failed = False
        for action_row in ordered_actions:
            if failed:
                break
            if action_row.status != ApplyActionExecutionStatus.PENDING:
                outcomes.append(
                    ActionExecutionOutcome(
                        status=action_row.status,
                        result_payload=dict(action_row.result_payload),
                        error_code=action_row.error_code,
                        error_message=action_row.error_message,
                    )
                )
                continue
            outcome = self._execute_one_action(action_row, context=context, plan_snapshot=run.plan_snapshot)
            outcomes.append(outcome)
            if outcome.status == ApplyActionExecutionStatus.FAILED:
                failed = True

        final_status = self._derive_run_status(outcomes)
        uow = self._unit_of_work_factory()
        repo = uow.repository
        failure_code = None
        failure_message = None
        if final_status == ApplyRunStatus.FAILED:
            failed_outcome = next(
                outcome for outcome in outcomes if outcome.status == ApplyActionExecutionStatus.FAILED
            )
            failure_code = failed_outcome.error_code
            failure_message = failed_outcome.error_message

        completed = repo.transition_run_status(
            apply_run_id,
            expected_status=ApplyRunStatus.RUNNING,
            target_status=final_status,
            failure_code=failure_code,
            failure_message=failure_message,
        )
        uow.commit()
        return self._result_from_run(completed, idempotent_replay=False, outcomes=outcomes)

    def _execute_one_action(
        self,
        action_row: ApplyActionExecution,
        *,
        context: ApplyExecutionContext,
        plan_snapshot: dict[str, Any],
    ) -> ActionExecutionOutcome:
        uow = self._unit_of_work_factory()
        repo = uow.repository

        existing_by_key = repo.get_action_by_idempotency_key(action_row.idempotency_key)
        if existing_by_key is not None and existing_by_key.apply_action_execution_id != action_row.apply_action_execution_id:
            if existing_by_key.action_fingerprint != action_row.action_fingerprint:
                raise ApplyIdempotencyConflict(
                    f"Idempotency key {action_row.idempotency_key!r} reused with different fingerprint"
                )

        assert_action_transition(action_row.status, ApplyActionExecutionStatus.RUNNING)
        repo.transition_action_status(
            action_row.apply_action_execution_id,
            expected_status=ApplyActionExecutionStatus.PENDING,
            target_status=ApplyActionExecutionStatus.RUNNING,
        )
        uow.commit()

        snapshot_action = _snapshot_action_for_row(plan_snapshot, action_row.action_index)
        apply_action = ApplyAction(
            action_type=ApplyActionType(snapshot_action["action_type"]),
            target_aggregate=str(snapshot_action["target_aggregate"]),
            source_candidate_ref=str(snapshot_action["source_candidate_ref"]),
            preconditions=tuple(snapshot_action.get("preconditions", ())),
            idempotency_key=str(snapshot_action["idempotency_key"]),
            is_ready=bool(snapshot_action.get("is_ready", True)),
            blocking_reason=snapshot_action.get("blocking_reason"),
        )

        try:
            self._validate_action_preconditions(apply_action, context=context)
            executor = self._dispatcher.resolve(apply_action.action_type)
            outcome = executor.execute(apply_action, context=context)
        except ApplyPreconditionError as exc:
            outcome = ActionExecutionOutcome(
                status=ApplyActionExecutionStatus.FAILED,
                error_code=exc.code,
                error_message=_sanitize_error(str(exc)),
            )
        except Exception as exc:  # pragma: no cover - safety net
            outcome = ActionExecutionOutcome(
                status=ApplyActionExecutionStatus.FAILED,
                error_code="apply_action_unhandled_error",
                error_message=_sanitize_error(str(exc)),
            )

        uow = self._unit_of_work_factory()
        repo = uow.repository
        repo.transition_action_status(
            action_row.apply_action_execution_id,
            expected_status=ApplyActionExecutionStatus.RUNNING,
            target_status=outcome.status,
            result_payload=outcome.result_payload,
            error_code=outcome.error_code,
            error_message=outcome.error_message,
        )
        uow.commit()
        return outcome

    def _build_action_rows(
        self,
        apply_plan: ApplyPlan,
        *,
        repo: Any,
    ) -> tuple[ApplyActionExecution, ...]:
        rows: list[ApplyActionExecution] = []
        for index, action in enumerate(apply_plan.actions):
            fingerprint = compute_action_fingerprint(action)
            existing = repo.get_action_by_idempotency_key(action.idempotency_key)
            if existing is not None and existing.action_fingerprint != fingerprint:
                raise ApplyIdempotencyConflict(
                    f"Idempotency key {action.idempotency_key!r} conflicts with different action fingerprint"
                )
            rows.append(
                ApplyActionExecution(
                    apply_action_execution_id=None,
                    apply_run_id=None,
                    action_index=index,
                    action_type=action.action_type.value,
                    target_aggregate=action.target_aggregate,
                    source_reference=action.source_candidate_ref,
                    idempotency_key=action.idempotency_key,
                    action_fingerprint=fingerprint,
                )
            )
        return tuple(rows)

    def _validate_persisted_plan_identity(
        self,
        existing: ApplyExecutionRun,
        *,
        apply_plan: ApplyPlan,
        review_run_key: str,
    ) -> None:
        stored_fingerprint = compute_plan_fingerprint(existing.plan_snapshot)
        if stored_fingerprint != existing.plan_fingerprint:
            raise ApplyIdempotencyConflict(
                "Persisted plan_snapshot does not match stored plan_fingerprint"
            )
        _, computed_fingerprint, _ = plan_snapshot_and_fingerprint(
            apply_plan,
            review_run_key=review_run_key,
        )
        if computed_fingerprint != existing.plan_fingerprint:
            raise ApplyIdempotencyConflict(
                "ApplyPlan content does not match persisted plan_fingerprint"
            )

    def _validate_plan_preconditions(
        self,
        *,
        import_run_id: int,
        apply_plan: ApplyPlan,
    ) -> None:
        if apply_plan.decision != ReviewDecision.APPROVED:
            raise ApplyPreconditionError("Apply plan decision must be approved")
        if not apply_plan.is_executable:
            raise ApplyPreconditionError("Apply plan is not executable")
        if apply_plan.blocking_reasons:
            raise ApplyPreconditionError("Apply plan has blocking reasons")
        if apply_plan.import_run_id is not None and apply_plan.import_run_id != import_run_id:
            raise ApplyPreconditionError("Apply plan import_run_id mismatch")
        if not self._import_run_status_checker(import_run_id):
            raise ApplyPreconditionError("Import run is cancelled or unavailable")
        for action in apply_plan.actions:
            if not action.is_ready:
                raise ApplyPreconditionError(
                    f"Action {action.action_type.value} is not ready: {action.blocking_reason}"
                )
            if not action.idempotency_key:
                raise ApplyPreconditionError("Action idempotency_key is required")

    def _validate_action_preconditions(
        self,
        action: ApplyAction,
        *,
        context: ApplyExecutionContext,
    ) -> None:
        if action.action_type == ApplyActionType.SKIP:
            return
        if action.action_type in DEFERRED_REASON_BY_ACTION:
            return
        person_id = _extract_person_id(action.preconditions)
        if person_id is None and action.action_type not in {ApplyActionType.CREATE_PERSON}:
            raise ApplyPreconditionError("matched_person_id precondition missing")

    def _derive_run_status(self, outcomes: list[ActionExecutionOutcome]) -> ApplyRunStatus:
        if not outcomes:
            return ApplyRunStatus.SUCCEEDED
        if any(outcome.status == ApplyActionExecutionStatus.FAILED for outcome in outcomes):
            return ApplyRunStatus.FAILED
        if all(
            outcome.status in {ApplyActionExecutionStatus.SUCCEEDED, ApplyActionExecutionStatus.SKIPPED}
            for outcome in outcomes
        ):
            return ApplyRunStatus.SUCCEEDED
        if any(outcome.status == ApplyActionExecutionStatus.DEFERRED for outcome in outcomes):
            return ApplyRunStatus.PARTIALLY_SUCCEEDED
        return ApplyRunStatus.PARTIALLY_SUCCEEDED

    def _result_from_run(
        self,
        run: ApplyExecutionRun,
        *,
        idempotent_replay: bool,
        outcomes: list[ActionExecutionOutcome] | None = None,
    ) -> ApplyExecutionResult:
        if outcomes is None:
            outcomes = [
                ActionExecutionOutcome(
                    status=action.status,
                    result_payload=dict(action.result_payload),
                    error_code=action.error_code,
                    error_message=action.error_message,
                )
                for action in sorted(run.actions, key=lambda item: item.action_index)
            ]
        summary = _build_summary(outcomes)
        return ApplyExecutionResult(
            apply_run_id=run.apply_run_id or 0,
            import_run_id=run.import_run_id,
            review_run_key=run.review_run_key,
            plan_fingerprint=run.plan_fingerprint,
            status=run.status,
            action_outcomes=tuple(outcomes),
            idempotent_replay=idempotent_replay,
            summary=summary,
        )


def _extract_person_id(preconditions: tuple[str, ...]) -> int | None:
    for item in preconditions:
        match = _PERSON_ID_PATTERN.match(item)
        if match:
            return int(match.group(1))
    return None


def _sanitize_error(message: str) -> str:
    cleaned = message.replace("\n", " ").strip()
    lowered = cleaned.lower()
    if "traceback" in lowered:
        cleaned = cleaned.split("Traceback", 1)[0].strip() or "apply_action_failed"
    for token in ("SELECT ", "INSERT ", "UPDATE ", "DELETE ", "postgresql://"):
        if token.lower() in lowered:
            cleaned = "apply_action_failed"
            break
    return cleaned[:500]


def _build_summary(outcomes: list[ActionExecutionOutcome]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for outcome in outcomes:
        key = outcome.status.value
        counts[key] = counts.get(key, 0) + 1
    return {"action_status_counts": counts, "total_actions": len(outcomes)}


def _snapshot_action_for_row(plan_snapshot: dict[str, Any], action_index: int) -> dict[str, Any]:
    for action in plan_snapshot.get("actions", []):
        if int(action["action_index"]) == action_index:
            return dict(action)
    raise ApplyPreconditionError(f"Plan snapshot missing action_index={action_index}")
