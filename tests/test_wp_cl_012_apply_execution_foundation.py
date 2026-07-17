# tests/test_wp_cl_012_apply_execution_foundation.py
"""Unit tests for WP-CL-012 apply execution foundation."""
from __future__ import annotations

import copy
import inspect
from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from app.control_list_import.apply_execution.dispatcher import ApplyActionDispatcher
from app.control_list_import.apply_execution.errors import (
    ApplyActionTransitionError,
    ApplyExecutionInProgress,
    ApplyExecutionRetryRequired,
    ApplyIdempotencyConflict,
    ApplyPreconditionError,
    ApplyRunTransitionError,
)
from app.control_list_import.apply_execution.executors import SkipApplyActionExecutor
from app.control_list_import.apply_execution.models import (
    ActionExecutionOutcome,
    ApplyActionExecution,
    ApplyActionExecutionStatus,
    ApplyExecutionRun,
    ApplyRunStatus,
    assert_action_transition,
    assert_run_transition,
)
from app.control_list_import.apply_execution.plan_snapshot import (
    compute_action_fingerprint,
    compute_plan_fingerprint,
    plan_snapshot_and_fingerprint,
)
from app.control_list_import.apply_execution.service import ApplyExecutionService
from app.control_list_import.infrastructure.apply_execution_repository import SqlAlchemyApplyExecutionRepository
from app.control_list_import.domain.contact_candidate import ContactCandidate, ContactReadinessStatus, NormalizedEmail
from app.control_list_import.domain.employment_candidate import (
    EmploymentCandidate,
    EmploymentReadinessStatus,
    NormalizedEmploymentStartDate,
    NormalizedRate,
)
from app.control_list_import.domain.person_candidate import (
    NormalizedBirthDate,
    NormalizedFullName,
    NormalizedIin,
    NormalizedPhone,
    NormalizedPlainText,
    NormalizedSex,
    PersonCandidate,
)
from app.control_list_import.domain.person_match_models import MatchReason, MatchStatus, PersonMatchResult
from app.control_list_import.domain.review_models import ApplyAction, ApplyActionType, ApplyPlan, ReviewDecision
from app.control_list_import.domain.person_candidate import NormalizedPhone as PersonPhone
from app.control_list_import.review.assembler import ReviewAssembler
from app.control_list_import.review.decisions import apply_review_decision
from app.control_list_import.review.normalization_bundle import NormalizationRunBundle
from app.db.models.control_list_mapping import EMPLOYMENT_MODE_CONCURRENT


class FakeApplyExecutionUnitOfWork:
    def __init__(self, repo: "FakeApplyExecutionRepository") -> None:
        self._repo = repo

    @property
    def repository(self) -> "FakeApplyExecutionRepository":
        return self._repo

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


class FakeApplyExecutionRepository:
    def __init__(self) -> None:
        self._runs_by_fingerprint: dict[str, ApplyExecutionRun] = {}
        self._runs_by_id: dict[int, ApplyExecutionRun] = {}
        self._actions_by_key: dict[str, ApplyActionExecution] = {}
        self._next_run_id = 1
        self._next_action_id = 1

    def get_run_by_fingerprint(self, plan_fingerprint: str) -> ApplyExecutionRun | None:
        return copy.deepcopy(self._runs_by_fingerprint.get(plan_fingerprint))

    def get_action_by_idempotency_key(self, idempotency_key: str) -> ApplyActionExecution | None:
        action = self._actions_by_key.get(idempotency_key)
        return copy.deepcopy(action) if action else None

    def create_run(
        self,
        *,
        import_run_id: int,
        review_run_key: str,
        plan_key: str,
        plan_fingerprint: str,
        plan_snapshot: dict,
        requested_by_user_id: int | None,
        actions: tuple[ApplyActionExecution, ...],
    ) -> ApplyExecutionRun:
        apply_run_id = self._next_run_id
        self._next_run_id += 1
        persisted_actions: list[ApplyActionExecution] = []
        for action in actions:
            action_id = self._next_action_id
            self._next_action_id += 1
            persisted = replace(
                action,
                apply_action_execution_id=action_id,
                apply_run_id=apply_run_id,
            )
            persisted_actions.append(persisted)
            self._actions_by_key[persisted.idempotency_key] = persisted
        run = ApplyExecutionRun(
            apply_run_id=apply_run_id,
            import_run_id=import_run_id,
            review_run_key=review_run_key,
            plan_key=plan_key,
            plan_fingerprint=plan_fingerprint,
            plan_snapshot=plan_snapshot,
            requested_by_user_id=requested_by_user_id,
            actions=tuple(persisted_actions),
        )
        self._runs_by_fingerprint[plan_fingerprint] = run
        self._runs_by_id[apply_run_id] = run
        return copy.deepcopy(run)

    def transition_run_status(
        self,
        apply_run_id: int,
        *,
        expected_status: ApplyRunStatus,
        target_status: ApplyRunStatus,
        failure_code: str | None = None,
        failure_message: str | None = None,
    ) -> ApplyExecutionRun:
        run = self._runs_by_id[apply_run_id]
        if run.status != expected_status:
            raise AssertionError("unexpected run status")
        assert_run_transition(run.status, target_status)
        updated = replace(
            run,
            status=target_status,
            failure_code=failure_code,
            failure_message=failure_message,
        )
        self._runs_by_id[apply_run_id] = updated
        self._runs_by_fingerprint[updated.plan_fingerprint] = updated
        return copy.deepcopy(updated)

    def transition_action_status(
        self,
        apply_action_execution_id: int,
        *,
        expected_status: ApplyActionExecutionStatus,
        target_status: ApplyActionExecutionStatus,
        result_payload: dict | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> ApplyActionExecution:
        run = self._find_run_by_action_id(apply_action_execution_id)
        actions = []
        updated_action = None
        for action in run.actions:
            if action.apply_action_execution_id != apply_action_execution_id:
                actions.append(action)
                continue
            if action.status != expected_status:
                raise AssertionError("unexpected action status")
            assert_action_transition(action.status, target_status)
            attempt_count = action.attempt_count + (
                1 if target_status == ApplyActionExecutionStatus.RUNNING else 0
            )
            updated_action = replace(
                action,
                status=target_status,
                attempt_count=attempt_count,
                result_payload=result_payload or {},
                error_code=error_code,
                error_message=error_message,
            )
            actions.append(updated_action)
            self._actions_by_key[updated_action.idempotency_key] = updated_action
        assert updated_action is not None
        updated_run = replace(run, actions=tuple(actions))
        self._runs_by_id[run.apply_run_id] = updated_run
        self._runs_by_fingerprint[run.plan_fingerprint] = updated_run
        return copy.deepcopy(updated_action)

    def load_run(self, apply_run_id: int) -> ApplyExecutionRun | None:
        run = self._runs_by_id.get(apply_run_id)
        return copy.deepcopy(run) if run else None

    def _find_run_by_action_id(self, action_id: int) -> ApplyExecutionRun:
        for run in self._runs_by_id.values():
            if any(action.apply_action_execution_id == action_id for action in run.actions):
                return run
        raise KeyError(action_id)


def _action(action_type: ApplyActionType, *, ref: str, key: str, ready: bool = True) -> ApplyAction:
    return ApplyAction(
        action_type=action_type,
        target_aggregate="employment.assignment" if action_type == ApplyActionType.RESOLVE_ASSIGNMENT else "person",
        source_candidate_ref=ref,
        preconditions=("review.decision_approved", "person_match.exact_or_probable", "person_id=42"),
        idempotency_key=key,
        is_ready=ready,
    )


def _executable_plan(*, actions: tuple[ApplyAction, ...] | None = None) -> ApplyPlan:
    if actions is None:
        actions = (
            _action(ApplyActionType.RESOLVE_ASSIGNMENT, ref="employment:row:100", key="cl-apply:employment"),
            _action(ApplyActionType.UPDATE_PERSON_CONTACT, ref="contact:row:100", key="cl-apply:contact"),
        )
    return ApplyPlan(
        import_run_id=7,
        source_row_id=100,
        decision=ReviewDecision.APPROVED,
        actions=actions,
        is_executable=True,
    )


def _service(repo: FakeApplyExecutionRepository | None = None) -> ApplyExecutionService:
    repository = repo or FakeApplyExecutionRepository()
    return ApplyExecutionService(
        unit_of_work_factory=lambda: FakeApplyExecutionUnitOfWork(repository),
    )


def test_run_transition_matrix_allows_expected_paths():
    assert_run_transition(ApplyRunStatus.PENDING, ApplyRunStatus.RUNNING)
    assert_run_transition(ApplyRunStatus.RUNNING, ApplyRunStatus.SUCCEEDED)
    with pytest.raises(Exception):
        assert_run_transition(ApplyRunStatus.SUCCEEDED, ApplyRunStatus.RUNNING)


def test_action_transition_matrix_blocks_terminal_restarts():
    assert_action_transition(ApplyActionExecutionStatus.PENDING, ApplyActionExecutionStatus.RUNNING)
    assert_action_transition(ApplyActionExecutionStatus.RUNNING, ApplyActionExecutionStatus.DEFERRED)
    with pytest.raises(Exception):
        assert_action_transition(ApplyActionExecutionStatus.DEFERRED, ApplyActionExecutionStatus.RUNNING)


def test_plan_fingerprint_is_stable_and_order_insensitive_keys():
    plan = _executable_plan()
    snapshot_a, fingerprint_a, _ = plan_snapshot_and_fingerprint(plan, review_run_key="review:7:100")
    snapshot_b = copy.deepcopy(snapshot_a)
    snapshot_b["actions"] = list(reversed(snapshot_b["actions"]))
    fingerprint_b = compute_plan_fingerprint(snapshot_b)
    assert fingerprint_a != fingerprint_b
    _, fingerprint_c, _ = plan_snapshot_and_fingerprint(plan, review_run_key="review:7:100")
    assert fingerprint_a == fingerprint_c


def test_precondition_change_changes_fingerprint():
    plan = _executable_plan()
    _, fp1, _ = plan_snapshot_and_fingerprint(plan, review_run_key="review:7:100")
    changed_actions = (
        replace(plan.actions[0], preconditions=plan.actions[0].preconditions + ("extra=1",)),
        plan.actions[1],
    )
    changed = replace(plan, actions=changed_actions)
    _, fp2, _ = plan_snapshot_and_fingerprint(changed, review_run_key="review:7:100")
    assert fp1 != fp2


def test_only_approved_executable_plan_runs():
    service = _service()
    with pytest.raises(ApplyPreconditionError):
        service.execute_approved_plan(
            import_run_id=7,
            review_run_key="review:7:100",
            apply_plan=replace(_executable_plan(), decision=ReviewDecision.PENDING),
        )


def test_reexecute_returns_existing_result_without_duplicate_mutation():
    repo = FakeApplyExecutionRepository()
    service = _service(repo)
    plan = _executable_plan()
    first = service.execute_approved_plan(import_run_id=7, review_run_key="review:7:100", apply_plan=plan)
    second = service.execute_approved_plan(import_run_id=7, review_run_key="review:7:100", apply_plan=plan)
    assert second.idempotent_replay is True
    assert second.apply_run_id == first.apply_run_id
    assert len(repo._runs_by_id) == 1


def test_failed_plan_requires_explicit_retry():
    repo = FakeApplyExecutionRepository()
    service = ApplyExecutionService(
        unit_of_work_factory=lambda: FakeApplyExecutionUnitOfWork(repo),
        dispatcher=ApplyActionDispatcher(
            {
                ApplyActionType.SKIP: SkipApplyActionExecutor(),
                ApplyActionType.RESOLVE_ASSIGNMENT: _FailingExecutor(),
            }
        ),
    )
    plan = ApplyPlan(
        import_run_id=7,
        source_row_id=100,
        decision=ReviewDecision.APPROVED,
        actions=(_action(ApplyActionType.RESOLVE_ASSIGNMENT, ref="employment:row:100", key="cl-apply:fail"),),
        is_executable=True,
    )
    result = service.execute_approved_plan(import_run_id=7, review_run_key="review:7:100", apply_plan=plan)
    assert result.status == ApplyRunStatus.FAILED
    with pytest.raises(ApplyExecutionRetryRequired):
        service.execute_approved_plan(import_run_id=7, review_run_key="review:7:100", apply_plan=plan)


class _FailingExecutor:
    def execute(self, action, *, context):
        return ActionExecutionOutcome(
            status=ApplyActionExecutionStatus.FAILED,
            error_code="test_failure",
            error_message="sanitised failure",
        )


def test_skip_action_is_skipped_not_failed():
    service = _service()
    plan = ApplyPlan(
        import_run_id=7,
        source_row_id=100,
        decision=ReviewDecision.APPROVED,
        actions=(_action(ApplyActionType.SKIP, ref="row:100", key="cl-apply:skip"),),
        is_executable=True,
    )
    result = service.execute_approved_plan(import_run_id=7, review_run_key="review:7:100", apply_plan=plan)
    assert result.status == ApplyRunStatus.SUCCEEDED
    assert result.action_outcomes[0].status == ApplyActionExecutionStatus.SKIPPED


def test_unsupported_actions_are_deferred_not_failed():
    service = _service()
    plan = _executable_plan()
    result = service.execute_approved_plan(import_run_id=7, review_run_key="review:7:100", apply_plan=plan)
    assert result.status == ApplyRunStatus.PARTIALLY_SUCCEEDED
    assert all(
        outcome.status in {ApplyActionExecutionStatus.DEFERRED, ApplyActionExecutionStatus.SKIPPED}
        for outcome in result.action_outcomes
    )
    assert not any(outcome.status == ApplyActionExecutionStatus.FAILED for outcome in result.action_outcomes)


def test_all_deferred_results_in_partially_succeeded():
    service = _service()
    plan = ApplyPlan(
        import_run_id=7,
        source_row_id=100,
        decision=ReviewDecision.APPROVED,
        actions=(
            _action(ApplyActionType.ADD_EDUCATION, ref="education:1", key="cl-apply:edu"),
            _action(ApplyActionType.ADD_TRAINING, ref="training:1", key="cl-apply:train"),
        ),
        is_executable=True,
    )
    result = service.execute_approved_plan(import_run_id=7, review_run_key="review:7:100", apply_plan=plan)
    assert result.status == ApplyRunStatus.PARTIALLY_SUCCEEDED


def test_duplicate_idempotency_key_with_different_fingerprint_conflicts():
    repo = FakeApplyExecutionRepository()
    service = _service(repo)
    action_a = _action(ApplyActionType.ADD_EDUCATION, ref="education:1", key="same-key")
    action_b = replace(action_a, preconditions=action_a.preconditions + ("changed=1",))
    plan = ApplyPlan(
        import_run_id=7,
        source_row_id=100,
        decision=ReviewDecision.APPROVED,
        actions=(action_a, action_b),
        is_executable=True,
    )
    with pytest.raises(ApplyIdempotencyConflict):
        service.execute_approved_plan(import_run_id=7, review_run_key="review:7:100", apply_plan=plan)


def test_failed_action_stops_following_actions():
    repo = FakeApplyExecutionRepository()
    service = ApplyExecutionService(
        unit_of_work_factory=lambda: FakeApplyExecutionUnitOfWork(repo),
        dispatcher=ApplyActionDispatcher(
            {
                ApplyActionType.SKIP: SkipApplyActionExecutor(),
                ApplyActionType.RESOLVE_ASSIGNMENT: _FailingExecutor(),
                ApplyActionType.UPDATE_PERSON_CONTACT: SkipApplyActionExecutor(),
            }
        ),
    )
    plan = ApplyPlan(
        import_run_id=7,
        source_row_id=100,
        decision=ReviewDecision.APPROVED,
        actions=(
            _action(ApplyActionType.RESOLVE_ASSIGNMENT, ref="employment:row:100", key="cl-apply:1"),
            _action(ApplyActionType.UPDATE_PERSON_CONTACT, ref="contact:row:100", key="cl-apply:2"),
        ),
        is_executable=True,
    )
    result = service.execute_approved_plan(import_run_id=7, review_run_key="review:7:100", apply_plan=plan)
    assert result.status == ApplyRunStatus.FAILED
    assert len(result.action_outcomes) == 1


def test_apply_execution_has_no_direct_canonical_orm_writes():
    modules = (
        ApplyExecutionService,
        ApplyActionDispatcher,
    )
    forbidden = (
        "insert into public.persons",
        "insert into public.employees",
        "insert into public.person_assignments",
        "insert into public.person_education",
        "insert into public.person_training",
        "insert into public.person_external_employment",
        "session.add(",
        "persons",
        "employees",
    )
    for module in modules:
        source = inspect.getsource(module).lower()
        for token in forbidden:
            assert token not in source, f"{module.__name__} must not reference {token}"


def test_concurrent_assignment_plan_uses_resolve_assignment_executor_path():
    bundle = _approved_concurrent_bundle()
    item = apply_review_decision(ReviewAssembler().assemble(bundle).items[0], ReviewDecision.APPROVED)
    plan = item.apply_plan
    assert plan is not None
    employment_action = next(
        action for action in plan.actions if action.action_type == ApplyActionType.RESOLVE_ASSIGNMENT
    )
    assert f"employment_mode={EMPLOYMENT_MODE_CONCURRENT}" in employment_action.preconditions
    result = _service().execute_approved_plan(
        import_run_id=7,
        review_run_key="review:7:100",
        apply_plan=plan,
    )
    deferred = next(
        outcome
        for outcome in result.action_outcomes
        if outcome.result_payload.get("action_type") == ApplyActionType.RESOLVE_ASSIGNMENT.value
    )
    assert deferred.status == ApplyActionExecutionStatus.DEFERRED
    assert deferred.result_payload["reason"] == "assignment_resolution_requires_explicit_hr_decision"


def _approved_concurrent_bundle() -> NormalizationRunBundle:
    person = PersonCandidate(
        import_run_id=7,
        profile_id=10,
        profile_code="control_list_default",
        profile_version=1,
        source_row_id=100,
        source_sheet_name="врачи совместители",
        source_excel_row_number=5,
        personnel_category="doctor",
        employment_mode="concurrent",
        full_name=NormalizedFullName(raw="Иванов Иван", display="Иванов Иван", normalized_key="ivanov ivan"),
        iin=NormalizedIin(raw="850101300123", digits="850101300123"),
        birth_date=NormalizedBirthDate(raw="01.01.1985", value=date(1985, 1, 1)),
        phone=NormalizedPhone(raw="+77001234567", digits="77001234567"),
        sex=NormalizedSex(raw="М", code="M"),
        department_name=NormalizedPlainText(raw="Терапия", text="Терапия"),
        position_title=NormalizedPlainText(raw="Врач", text="Врач"),
    )
    match = PersonMatchResult(
        import_run_id=7,
        source_row_id=100,
        status=MatchStatus.EXACT,
        match_candidates=(),
        primary_reason=MatchReason.EXACT_IIN,
        reasons=(MatchReason.EXACT_IIN,),
        confidence=1.0,
        recommended_person_id=42,
    )
    employment = EmploymentCandidate(
        import_run_id=7,
        profile_id=10,
        profile_code="control_list_default",
        profile_version=1,
        source_row_id=100,
        source_sheet_name="врачи совместители",
        source_excel_row_number=5,
        matched_person_id=42,
        personnel_category="doctor",
        employment_mode=EMPLOYMENT_MODE_CONCURRENT,
        department_name=NormalizedPlainText(raw="Терапия", text="Терапия"),
        position_title=NormalizedPlainText(raw="Врач", text="Врач"),
        rate=NormalizedRate(raw="1", value=Decimal("1")),
        employment_start_date=NormalizedEmploymentStartDate(raw="01.03.2020", value=date(2020, 3, 1)),
        readiness_status=EmploymentReadinessStatus.NORMALIZATION_READY,
    )
    contact = ContactCandidate(
        import_run_id=7,
        profile_id=10,
        profile_code="control_list_default",
        profile_version=1,
        source_row_id=100,
        source_sheet_name="врачи совместители",
        source_excel_row_number=5,
        matched_person_id=42,
        phone=PersonPhone(raw="+77001234567", digits="77001234567"),
        email=NormalizedEmail(raw="a@b.kz", address="a@b.kz"),
        residence_address=NormalizedPlainText(raw="Алматы", text="Алматы"),
        registration_address=NormalizedPlainText(raw="Алматы", text="Алматы"),
        readiness_status=ContactReadinessStatus.NORMALIZATION_READY,
    )
    return NormalizationRunBundle(
        import_run_id=7,
        profile_id=10,
        profile_code="control_list_default",
        profile_version=1,
        person_candidates={100: person},
        person_matches={100: match},
        employment_candidates={100: employment},
        contact_candidates={100: contact},
        education_candidates={100: []},
        training_candidates={100: []},
        other_ppr_candidates={100: []},
    )


def test_retry_execution_is_not_implemented_on_service():
    assert not hasattr(ApplyExecutionService, "retry_failed_run")


def test_repository_has_no_terminal_status_reset_api():
    assert not hasattr(SqlAlchemyApplyExecutionRepository, "reset_failed_run_for_retry")


def test_failed_journal_is_immutable_on_reexecute():
    repo = FakeApplyExecutionRepository()
    executor = _CountingFailingExecutor()
    service = ApplyExecutionService(
        unit_of_work_factory=lambda: FakeApplyExecutionUnitOfWork(repo),
        dispatcher=ApplyActionDispatcher({ApplyActionType.RESOLVE_ASSIGNMENT: executor}),
    )
    plan = ApplyPlan(
        import_run_id=7,
        source_row_id=100,
        decision=ReviewDecision.APPROVED,
        actions=(_action(ApplyActionType.RESOLVE_ASSIGNMENT, ref="employment:row:100", key="cl-apply:fail"),),
        is_executable=True,
    )
    first = service.execute_approved_plan(import_run_id=7, review_run_key="review:7:100", apply_plan=plan)
    run_before = repo._runs_by_id[first.apply_run_id]
    action_before = run_before.actions[0]
    assert first.status == ApplyRunStatus.FAILED
    assert action_before.status == ApplyActionExecutionStatus.FAILED
    assert action_before.attempt_count == 1
    assert action_before.error_code == "test_failure"

    with pytest.raises(ApplyExecutionRetryRequired):
        service.execute_approved_plan(import_run_id=7, review_run_key="review:7:100", apply_plan=plan)

    run_after = repo._runs_by_id[first.apply_run_id]
    action_after = run_after.actions[0]
    assert run_after.status == ApplyRunStatus.FAILED
    assert action_after.status == ApplyActionExecutionStatus.FAILED
    assert action_after.attempt_count == action_before.attempt_count
    assert action_after.error_code == action_before.error_code
    assert action_after.error_message == action_before.error_message
    assert executor.call_count == 1


class _CountingFailingExecutor(_FailingExecutor):
    def __init__(self) -> None:
        self.call_count = 0

    def execute(self, action, *, context):
        self.call_count += 1
        return super().execute(action, context=context)


def test_terminal_run_status_cannot_return_to_running():
    with pytest.raises(ApplyRunTransitionError):
        assert_run_transition(ApplyRunStatus.FAILED, ApplyRunStatus.PENDING)
    with pytest.raises(ApplyRunTransitionError):
        assert_run_transition(ApplyRunStatus.SUCCEEDED, ApplyRunStatus.RUNNING)


def test_terminal_action_statuses_cannot_return_to_running():
    for terminal in (
        ApplyActionExecutionStatus.SUCCEEDED,
        ApplyActionExecutionStatus.SKIPPED,
        ApplyActionExecutionStatus.DEFERRED,
        ApplyActionExecutionStatus.FAILED,
    ):
        with pytest.raises(ApplyActionTransitionError):
            assert_action_transition(terminal, ApplyActionExecutionStatus.RUNNING)
        with pytest.raises(ApplyActionTransitionError):
            assert_action_transition(terminal, ApplyActionExecutionStatus.PENDING)


def test_succeeded_replay_does_not_call_executors_or_create_rows():
    repo = FakeApplyExecutionRepository()
    executor = _CountingDeferredExecutor()
    service = ApplyExecutionService(
        unit_of_work_factory=lambda: FakeApplyExecutionUnitOfWork(repo),
        dispatcher=ApplyActionDispatcher({ApplyActionType.ADD_EDUCATION: executor}),
    )
    plan = ApplyPlan(
        import_run_id=7,
        source_row_id=100,
        decision=ReviewDecision.APPROVED,
        actions=(_action(ApplyActionType.ADD_EDUCATION, ref="education:1", key="cl-apply:edu"),),
        is_executable=True,
    )
    first = service.execute_approved_plan(import_run_id=7, review_run_key="review:7:100", apply_plan=plan)
    second = service.execute_approved_plan(import_run_id=7, review_run_key="review:7:100", apply_plan=plan)
    assert second.idempotent_replay is True
    assert second.apply_run_id == first.apply_run_id
    assert len(repo._runs_by_id) == 1
    assert executor.call_count == 1


class _CountingDeferredExecutor:
    def __init__(self) -> None:
        self.call_count = 0

    def execute(self, action, *, context):
        self.call_count += 1
        return ActionExecutionOutcome(
            status=ApplyActionExecutionStatus.DEFERRED,
            result_payload={"reason": "test", "action_type": action.action_type.value},
        )


def test_pending_run_reexecute_raises_in_progress_without_mutation():
    repo = FakeApplyExecutionRepository()
    service = _service(repo)
    plan = _executable_plan(actions=(_action(ApplyActionType.SKIP, ref="row:100", key="cl-apply:pending"),))
    snapshot, fingerprint, plan_key = plan_snapshot_and_fingerprint(plan, review_run_key="review:7:100")
    pending_run = repo.create_run(
        import_run_id=7,
        review_run_key="review:7:100",
        plan_key=plan_key,
        plan_fingerprint=fingerprint,
        plan_snapshot=snapshot,
        requested_by_user_id=None,
        actions=(
            ApplyActionExecution(
                apply_action_execution_id=None,
                apply_run_id=None,
                action_index=0,
                action_type=ApplyActionType.SKIP.value,
                target_aggregate="person",
                source_reference="row:100",
                idempotency_key="cl-apply:pending",
                action_fingerprint=compute_action_fingerprint(plan.actions[0]),
            ),
        ),
    )
    assert pending_run.status == ApplyRunStatus.PENDING
    with pytest.raises(ApplyExecutionInProgress):
        service.execute_approved_plan(import_run_id=7, review_run_key="review:7:100", apply_plan=plan)
    assert repo._runs_by_id[pending_run.apply_run_id].status == ApplyRunStatus.PENDING


def test_running_run_reexecute_raises_in_progress():
    repo = FakeApplyExecutionRepository()
    service = _service(repo)
    plan = _executable_plan(actions=(_action(ApplyActionType.SKIP, ref="row:100", key="cl-apply:running"),))
    snapshot, fingerprint, plan_key = plan_snapshot_and_fingerprint(plan, review_run_key="review:7:100")
    run = repo.create_run(
        import_run_id=7,
        review_run_key="review:7:100",
        plan_key=plan_key,
        plan_fingerprint=fingerprint,
        plan_snapshot=snapshot,
        requested_by_user_id=None,
        actions=(
            ApplyActionExecution(
                apply_action_execution_id=None,
                apply_run_id=None,
                action_index=0,
                action_type=ApplyActionType.SKIP.value,
                target_aggregate="person",
                source_reference="row:100",
                idempotency_key="cl-apply:running",
                action_fingerprint=compute_action_fingerprint(plan.actions[0]),
            ),
        ),
    )
    repo.transition_run_status(run.apply_run_id, expected_status=ApplyRunStatus.PENDING, target_status=ApplyRunStatus.RUNNING)
    with pytest.raises(ApplyExecutionInProgress):
        service.execute_approved_plan(import_run_id=7, review_run_key="review:7:100", apply_plan=plan)


def test_passed_plan_fingerprint_mismatch_is_idempotency_conflict():
    service = _service()
    plan = _executable_plan()
    _, fingerprint, _ = plan_snapshot_and_fingerprint(plan, review_run_key="review:7:100")
    with pytest.raises(ApplyIdempotencyConflict):
        service.execute_approved_plan(
            import_run_id=7,
            review_run_key="review:7:100",
            apply_plan=plan,
            plan_fingerprint="0" * 64,
        )


def test_persisted_snapshot_fingerprint_mismatch_is_idempotency_conflict():
    repo = FakeApplyExecutionRepository()
    service = _service(repo)
    plan = _executable_plan(actions=(_action(ApplyActionType.SKIP, ref="row:100", key="cl-apply:snap"),))
    snapshot, fingerprint, plan_key = plan_snapshot_and_fingerprint(plan, review_run_key="review:7:100")
    tampered_snapshot = copy.deepcopy(snapshot)
    tampered_snapshot["blocking_reasons"] = ["tampered"]
    repo.create_run(
        import_run_id=7,
        review_run_key="review:7:100",
        plan_key=plan_key,
        plan_fingerprint=fingerprint,
        plan_snapshot=tampered_snapshot,
        requested_by_user_id=None,
        actions=(
            ApplyActionExecution(
                apply_action_execution_id=None,
                apply_run_id=None,
                action_index=0,
                action_type=ApplyActionType.SKIP.value,
                target_aggregate="person",
                source_reference="row:100",
                idempotency_key="cl-apply:snap",
                action_fingerprint=compute_action_fingerprint(plan.actions[0]),
            ),
        ),
    )
    with pytest.raises(ApplyIdempotencyConflict):
        service.execute_approved_plan(import_run_id=7, review_run_key="review:7:100", apply_plan=plan)


def test_precondition_key_order_does_not_change_fingerprint():
    plan = _executable_plan()
    pre_a = ("z=1", "a=2", *plan.actions[0].preconditions)
    pre_b = ("a=2", "z=1", *plan.actions[0].preconditions)
    changed_a = replace(plan.actions[0], preconditions=pre_a)
    changed_b = replace(plan.actions[0], preconditions=pre_b)
    _, fp_a, _ = plan_snapshot_and_fingerprint(replace(plan, actions=(changed_a, plan.actions[1])), review_run_key="review:7:100")
    _, fp_b, _ = plan_snapshot_and_fingerprint(replace(plan, actions=(changed_b, plan.actions[1])), review_run_key="review:7:100")
    assert fp_a == fp_b


def test_unicode_snapshot_is_stable():
    plan = ApplyPlan(
        import_run_id=7,
        source_row_id=100,
        decision=ReviewDecision.APPROVED,
        actions=(
            ApplyAction(
                action_type=ApplyActionType.SKIP,
                target_aggregate="person",
                source_candidate_ref="row:100",
                preconditions=("review.decision_approved", "note=Алматы"),
                idempotency_key="cl-apply:unicode",
                is_ready=True,
            ),
        ),
        is_executable=True,
    )
    snapshot, fingerprint, _ = plan_snapshot_and_fingerprint(plan, review_run_key="review:7:100")
    assert compute_plan_fingerprint(snapshot) == fingerprint
    assert "note=Алматы" in snapshot["actions"][0]["preconditions"]


def test_saved_plan_snapshot_matches_computed_fingerprint():
    plan = _executable_plan()
    snapshot, fingerprint, _ = plan_snapshot_and_fingerprint(plan, review_run_key="review:7:100")
    assert compute_plan_fingerprint(snapshot) == fingerprint


def test_failed_action_leaves_following_actions_pending():
    repo = FakeApplyExecutionRepository()
    service = ApplyExecutionService(
        unit_of_work_factory=lambda: FakeApplyExecutionUnitOfWork(repo),
        dispatcher=ApplyActionDispatcher(
            {
                ApplyActionType.RESOLVE_ASSIGNMENT: _FailingExecutor(),
                ApplyActionType.UPDATE_PERSON_CONTACT: _CountingDeferredExecutor(),
            }
        ),
    )
    plan = _executable_plan()
    result = service.execute_approved_plan(import_run_id=7, review_run_key="review:7:100", apply_plan=plan)
    run = repo._runs_by_id[result.apply_run_id]
    assert run.actions[0].status == ApplyActionExecutionStatus.FAILED
    assert run.actions[1].status == ApplyActionExecutionStatus.PENDING


def test_error_message_is_sanitized_without_traceback_or_sql():
    repo = FakeApplyExecutionRepository()
    service = ApplyExecutionService(
        unit_of_work_factory=lambda: FakeApplyExecutionUnitOfWork(repo),
        dispatcher=ApplyActionDispatcher({ApplyActionType.RESOLVE_ASSIGNMENT: _SqlTracebackExecutor()}),
    )
    plan = ApplyPlan(
        import_run_id=7,
        source_row_id=100,
        decision=ReviewDecision.APPROVED,
        actions=(_action(ApplyActionType.RESOLVE_ASSIGNMENT, ref="employment:row:100", key="cl-apply:err"),),
        is_executable=True,
    )
    result = service.execute_approved_plan(import_run_id=7, review_run_key="review:7:100", apply_plan=plan)
    message = result.action_outcomes[0].error_message or ""
    assert "Traceback" not in message
    assert "SELECT" not in message
    assert "postgresql://" not in message
    payload = result.action_outcomes[0].result_payload
    assert "raw_row" not in payload


class _SqlTracebackExecutor:
    def execute(self, action, *, context):
        raise RuntimeError(
            "Traceback (most recent call last):\nSELECT * FROM persons\npostgresql://user:pass@localhost/db"
        )


def test_deferred_executor_payload_has_no_raw_workbook_row():
    service = _service()
    plan = ApplyPlan(
        import_run_id=7,
        source_row_id=100,
        decision=ReviewDecision.APPROVED,
        actions=(_action(ApplyActionType.ADD_EDUCATION, ref="education:1", key="cl-apply:payload"),),
        is_executable=True,
    )
    result = service.execute_approved_plan(import_run_id=7, review_run_key="review:7:100", apply_plan=plan)
    payload = result.action_outcomes[0].result_payload
    assert "raw_row" not in payload
    assert set(payload.keys()) <= {"reason", "action_type", "source_candidate_ref"}


def test_first_action_attempt_count_is_one_after_running():
    repo = FakeApplyExecutionRepository()
    service = _service(repo)
    plan = ApplyPlan(
        import_run_id=7,
        source_row_id=100,
        decision=ReviewDecision.APPROVED,
        actions=(_action(ApplyActionType.SKIP, ref="row:100", key="cl-apply:attempt"),),
        is_executable=True,
    )
    result = service.execute_approved_plan(import_run_id=7, review_run_key="review:7:100", apply_plan=plan)
    action = repo._runs_by_id[result.apply_run_id].actions[0]
    assert action.attempt_count == 1
