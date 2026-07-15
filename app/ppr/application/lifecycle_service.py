"""PPR lifecycle application service — MaterializePPR, StartCollection, ActivatePPR (R5)."""
from __future__ import annotations

from datetime import UTC, datetime

from app.ppr.application.command_models import (
    COMMAND_TYPE_ACTIVATE_PPR,
    COMMAND_TYPE_MATERIALIZE_PPR,
    COMMAND_TYPE_START_COLLECTION,
    MaterializePprPayload,
    PprCommandEnvelope,
)
from app.ppr.application.command_service import PprCommandApplicationService
from app.ppr.application.event_builder import build_lifecycle_changed_event, build_ppr_created_event
from app.ppr.application.results import (
    PprApplicationResult,
    RESULT_STATUS_ALREADY_MATERIALIZED,
    RESULT_STATUS_COMMITTED,
    RESULT_STATUS_IDEMPOTENT_REPLAY,
    RESULT_STATUS_NO_OP,
)
from app.ppr.domain.errors import PprEnvelopeNotFoundError, PprNotMaterializedError
from app.ppr.domain.lifecycle_transitions import validate_activate_ppr, validate_start_collection
from app.ppr.domain.models import (
    PPR_ENVELOPE_INITIAL_HR_RELATIONSHIP_CONTEXT,
    PPR_ENVELOPE_INITIAL_LIFECYCLE_STATE,
    PPR_ENVELOPE_INITIAL_VERSION,
    PPR_LIFECYCLE_ACTIVE,
    PPR_LIFECYCLE_COLLECTING,
    PPR_LIFECYCLE_CREATED,
    HR_RELATIONSHIP_CONTEXTS,
    PprEnvelope,
)
from app.ppr.infrastructure.application_unit_of_work import PprApplicationUnitOfWork


class PprLifecycleApplicationService(PprCommandApplicationService):
    def materialize_ppr(self, envelope: PprCommandEnvelope) -> PprApplicationResult:
        payload = envelope.payload
        if not isinstance(payload, MaterializePprPayload):
            payload = MaterializePprPayload()
        hr_context = payload.hr_relationship_context or PPR_ENVELOPE_INITIAL_HR_RELATIONSHIP_CONTEXT
        if hr_context not in HR_RELATIONSHIP_CONTEXTS:
            raise PprNotMaterializedError(f"invalid hr_relationship_context: {hr_context!r}")

        def mutate(uow: PprApplicationUnitOfWork, person_id: int) -> PprApplicationResult:
            uow.identity.load_identity(person_id)
            if uow.envelopes.exists_envelope(person_id):
                loaded = uow.envelopes.load_envelope(person_id)
                assert loaded is not None
                return PprApplicationResult(
                    command_id=envelope.command_id,
                    command_type=envelope.command_type,
                    resolved_person_id=person_id,
                    status=RESULT_STATUS_ALREADY_MATERIALIZED,
                    envelope_version=loaded.version,
                    correlation_id=envelope.correlation_id,
                )

            now = datetime.now(UTC)
            created = uow.envelopes.insert_envelope(
                PprEnvelope(
                    person_id=person_id,
                    lifecycle_state=PPR_ENVELOPE_INITIAL_LIFECYCLE_STATE,
                    hr_relationship_context=hr_context,
                    version=PPR_ENVELOPE_INITIAL_VERSION,
                    created_at=now,
                    updated_at=now,
                )
            )
            event = uow.events.append(
                build_ppr_created_event(
                    person_id=person_id,
                    actor_id=envelope.actor_id,
                    command_id=envelope.command_id,
                    correlation_id=envelope.correlation_id,
                    hr_relationship_context=hr_context,
                    envelope_version=created.version,
                )
            )
            return PprApplicationResult(
                command_id=envelope.command_id,
                command_type=envelope.command_type,
                resolved_person_id=person_id,
                status=RESULT_STATUS_COMMITTED,
                envelope_version=created.version,
                event_ids=(event.event_id,),
                correlation_id=envelope.correlation_id,
            )

        return self._execute_with_idempotency(
            envelope,
            operation_code=COMMAND_TYPE_MATERIALIZE_PPR,
            fingerprint_payload={"hr_relationship_context": hr_context},
            section_code=None,
            mutate=mutate,
        )

    def materialize_ppr_participating(
        self,
        uow: PprApplicationUnitOfWork,
        envelope: PprCommandEnvelope,
    ) -> PprApplicationResult:
        payload = envelope.payload
        if not isinstance(payload, MaterializePprPayload):
            payload = MaterializePprPayload()
        hr_context = payload.hr_relationship_context or PPR_ENVELOPE_INITIAL_HR_RELATIONSHIP_CONTEXT

        def mutate(inner_uow: PprApplicationUnitOfWork, person_id: int) -> PprApplicationResult:
            inner_uow.identity.load_identity(person_id)
            if inner_uow.envelopes.exists_envelope(person_id):
                loaded = inner_uow.envelopes.load_envelope(person_id)
                assert loaded is not None
                return PprApplicationResult(
                    command_id=envelope.command_id,
                    command_type=envelope.command_type,
                    resolved_person_id=person_id,
                    status=RESULT_STATUS_ALREADY_MATERIALIZED,
                    envelope_version=loaded.version,
                    correlation_id=envelope.correlation_id,
                )
            now = datetime.now(UTC)
            created = inner_uow.envelopes.insert_envelope(
                PprEnvelope(
                    person_id=person_id,
                    lifecycle_state=PPR_ENVELOPE_INITIAL_LIFECYCLE_STATE,
                    hr_relationship_context=hr_context,
                    version=PPR_ENVELOPE_INITIAL_VERSION,
                    created_at=now,
                    updated_at=now,
                )
            )
            event = inner_uow.events.append(
                build_ppr_created_event(
                    person_id=person_id,
                    actor_id=envelope.actor_id,
                    command_id=envelope.command_id,
                    correlation_id=envelope.correlation_id,
                    hr_relationship_context=hr_context,
                    envelope_version=created.version,
                )
            )
            return PprApplicationResult(
                command_id=envelope.command_id,
                command_type=envelope.command_type,
                resolved_person_id=person_id,
                status=RESULT_STATUS_COMMITTED,
                envelope_version=created.version,
                event_ids=(event.event_id,),
                correlation_id=envelope.correlation_id,
            )

        return self.execute_participating(
            uow,
            envelope,
            operation_code=COMMAND_TYPE_MATERIALIZE_PPR,
            fingerprint_payload={"hr_relationship_context": hr_context},
            section_code=None,
            mutate=mutate,
        )

    def start_collection(self, envelope: PprCommandEnvelope) -> PprApplicationResult:
        return self._lifecycle_transition(
            envelope,
            command_type=COMMAND_TYPE_START_COLLECTION,
            transition=validate_start_collection,
        )

    def activate_ppr(self, envelope: PprCommandEnvelope) -> PprApplicationResult:
        return self._lifecycle_transition(
            envelope,
            command_type=COMMAND_TYPE_ACTIVATE_PPR,
            transition=validate_activate_ppr,
        )

    def _lifecycle_transition(
        self,
        envelope: PprCommandEnvelope,
        *,
        command_type: str,
        transition,
    ) -> PprApplicationResult:
        def mutate(uow: PprApplicationUnitOfWork, person_id: int) -> PprApplicationResult:
            loaded = uow.envelopes.load_envelope(person_id)
            if loaded is None:
                raise PprNotMaterializedError(f"PPR envelope not materialized for person_id={person_id}")

            if (
                envelope.expected_envelope_version is not None
                and loaded.version != envelope.expected_envelope_version
            ):
                from app.ppr.domain.errors import PprOptimisticConcurrencyConflictError

                raise PprOptimisticConcurrencyConflictError(
                    f"Stale envelope version for person_id={person_id}"
                )

            previous = loaded.lifecycle_state
            try:
                new_state = transition(previous)
            except Exception:
                raise

            if new_state == previous and command_type == COMMAND_TYPE_ACTIVATE_PPR:
                return PprApplicationResult(
                    command_id=envelope.command_id,
                    command_type=envelope.command_type,
                    resolved_person_id=person_id,
                    status=RESULT_STATUS_NO_OP,
                    envelope_version=loaded.version,
                    correlation_id=envelope.correlation_id,
                    extra={"lifecycle_state": previous},
                )
            if new_state == previous and command_type == COMMAND_TYPE_START_COLLECTION:
                return PprApplicationResult(
                    command_id=envelope.command_id,
                    command_type=envelope.command_type,
                    resolved_person_id=person_id,
                    status=RESULT_STATUS_NO_OP,
                    envelope_version=loaded.version,
                    correlation_id=envelope.correlation_id,
                    extra={"lifecycle_state": previous},
                )

            updated = uow.envelopes.update_envelope(
                loaded.with_updates(lifecycle_state=new_state),
                expected_version=loaded.version,
            )
            event = uow.events.append(
                build_lifecycle_changed_event(
                    person_id=person_id,
                    actor_id=envelope.actor_id,
                    command_id=envelope.command_id,
                    correlation_id=envelope.correlation_id,
                    previous_state=previous,
                    new_state=new_state,
                    command_type=command_type,
                    envelope_version=updated.version,
                )
            )
            return PprApplicationResult(
                command_id=envelope.command_id,
                command_type=envelope.command_type,
                resolved_person_id=person_id,
                status=RESULT_STATUS_COMMITTED,
                envelope_version=updated.version,
                event_ids=(event.event_id,),
                correlation_id=envelope.correlation_id,
                extra={"previous_state": previous, "new_state": new_state},
            )

        return self._execute_with_idempotency(
            envelope,
            operation_code=command_type,
            fingerprint_payload={"expected_envelope_version": envelope.expected_envelope_version},
            section_code=None,
            mutate=mutate,
        )
