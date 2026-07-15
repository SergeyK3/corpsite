"""Shared application orchestration helpers (R5).

Write pipeline order (all mutation services):
1. Validate command envelope structure
2. Resolve canonical person_id
3. Authorize for resolved subject
4. Reserve command idempotency (within UoW)
5. Load aggregate / execute domain mutation
6. Append canonical event
7. Complete command execution
8. Commit (standalone) or defer to caller (participating)
9. Post-commit hooks (standalone committed only; not on idempotent replay)
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.ppr.application.authorization import AuthorizationPort
from app.ppr.application.command_models import PprCommandEnvelope
from app.ppr.application.idempotency import (
    begin_idempotent_command,
    build_request_fingerprint,
    complete_idempotent_command,
)
from app.ppr.application.identity_resolution import resolve_canonical_person_id
from app.ppr.application.post_commit import (
    NoOpPostCommitHookRunner,
    PostCommitHookRunner,
    default_post_commit_actions,
)
from app.ppr.application.results import (
    PprApplicationResult,
    RESULT_STATUS_IDEMPOTENT_REPLAY,
    merge_warnings,
)
from app.ppr.domain.errors import PprApplicationValidationError
from app.ppr.infrastructure.application_unit_of_work import PprApplicationUnitOfWork


class PprCommandApplicationService:
    """Base orchestration for PPR application mutations."""

    def __init__(
        self,
        *,
        authorization: AuthorizationPort,
        post_commit: PostCommitHookRunner | None = None,
        uow_factory: Callable[[], PprApplicationUnitOfWork] | None = None,
    ) -> None:
        self._authorization = authorization
        self._post_commit = post_commit or NoOpPostCommitHookRunner()
        self._uow_factory = uow_factory or PprApplicationUnitOfWork

    @staticmethod
    def _validate_envelope(envelope: PprCommandEnvelope) -> None:
        if not envelope.command_id or not str(envelope.command_id).strip():
            raise PprApplicationValidationError("command_id is required")
        if not envelope.command_type or not str(envelope.command_type).strip():
            raise PprApplicationValidationError("command_type is required")
        if not envelope.actor_id or not str(envelope.actor_id).strip():
            raise PprApplicationValidationError("actor_id is required")
        if envelope.person_id is None and envelope.employee_id is None and envelope.employee_context_id is None:
            raise PprApplicationValidationError("person_id or employee_id is required")

    def _resolve_person(self, envelope: PprCommandEnvelope, uow: PprApplicationUnitOfWork) -> int:
        employee_input = envelope.employee_id or envelope.employee_context_id
        return resolve_canonical_person_id(
            uow.identity,
            person_id=envelope.person_id,
            employee_id=employee_input,
        )

    def _authorize(
        self,
        *,
        envelope: PprCommandEnvelope,
        person_id: int,
        operation_code: str,
        section_code: str | None = None,
    ) -> None:
        self._authorization.authorize_mutation(
            actor_id=envelope.actor_id,
            operation_code=operation_code,
            person_id=person_id,
            employee_context_id=envelope.employee_context_id or envelope.employee_id,
            section_code=section_code,
        )

    def _run_pipeline(
        self,
        envelope: PprCommandEnvelope,
        uow: PprApplicationUnitOfWork,
        *,
        operation_code: str,
        fingerprint_payload: dict[str, Any],
        section_code: str | None,
        mutate: Callable[[PprApplicationUnitOfWork, int], PprApplicationResult],
        participating: bool,
    ) -> PprApplicationResult:
        self._validate_envelope(envelope)
        person_id = self._resolve_person(envelope, uow)
        self._authorize(
            envelope=envelope,
            person_id=person_id,
            operation_code=operation_code,
            section_code=section_code,
        )
        fingerprint = build_request_fingerprint(
            command_type=envelope.command_type,
            payload=fingerprint_payload,
        )
        replay = begin_idempotent_command(
            uow.command_idempotency,
            command_id=envelope.command_id,
            command_type=envelope.command_type,
            person_id=person_id,
            request_fingerprint=fingerprint,
        )
        if replay is not None:
            return replay

        result = mutate(uow, person_id)
        if result.status == RESULT_STATUS_IDEMPOTENT_REPLAY:
            return result

        complete_idempotent_command(
            uow.command_idempotency,
            command_id=envelope.command_id,
            result=result,
        )
        if not participating:
            uow.commit()
            return self._finalize(result, run_hooks=True)
        return result

    def execute_participating(
        self,
        uow: PprApplicationUnitOfWork,
        envelope: PprCommandEnvelope,
        *,
        operation_code: str,
        fingerprint_payload: dict[str, Any],
        section_code: str | None,
        mutate: Callable[[PprApplicationUnitOfWork, int], PprApplicationResult],
    ) -> PprApplicationResult:
        """Run pipeline inside caller-owned transaction (no commit/post-commit here)."""
        return self._run_pipeline(
            envelope,
            uow,
            operation_code=operation_code,
            fingerprint_payload=fingerprint_payload,
            section_code=section_code,
            mutate=mutate,
            participating=True,
        )

    def _execute_with_idempotency(
        self,
        envelope: PprCommandEnvelope,
        *,
        operation_code: str,
        fingerprint_payload: dict[str, Any],
        section_code: str | None,
        mutate: Callable[[PprApplicationUnitOfWork, int], PprApplicationResult],
    ) -> PprApplicationResult:
        with self._uow_factory() as uow:
            result = self._run_pipeline(
                envelope,
                uow,
                operation_code=operation_code,
                fingerprint_payload=fingerprint_payload,
                section_code=section_code,
                mutate=mutate,
                participating=False,
            )
            if result.status == RESULT_STATUS_IDEMPOTENT_REPLAY:
                return self._finalize(result, run_hooks=False)
            return result

    def _finalize(self, result: PprApplicationResult, *, run_hooks: bool) -> PprApplicationResult:
        if not run_hooks or result.status == RESULT_STATUS_IDEMPOTENT_REPLAY:
            return result
        warnings = self._post_commit.run(default_post_commit_actions(result))
        return merge_warnings(result, warnings)

    def finalize_after_external_commit(self, result: PprApplicationResult) -> PprApplicationResult:
        """Post-commit hooks after participating caller committed."""
        if result.status == RESULT_STATUS_IDEMPOTENT_REPLAY:
            return result
        return self._finalize(result, run_hooks=True)
