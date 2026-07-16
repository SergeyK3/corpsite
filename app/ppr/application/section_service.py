"""PPR section application service — orchestrates R4 handlers + canonical events (R5)."""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Callable

from app.ppr.application.command_models import (
    COMMAND_TYPE_ADD_EDUCATION,
    COMMAND_TYPE_ADD_EXTERNAL_EMPLOYMENT,
    COMMAND_TYPE_ADD_RELATIVE,
    COMMAND_TYPE_ADD_TRAINING,
    COMMAND_TYPE_SUPERSEDE_EDUCATION,
    COMMAND_TYPE_SUPERSEDE_EXTERNAL_EMPLOYMENT,
    COMMAND_TYPE_SUPERSEDE_RELATIVE,
    COMMAND_TYPE_SUPERSEDE_TRAINING,
    COMMAND_TYPE_UPDATE_EDUCATION,
    COMMAND_TYPE_UPDATE_RELATIVE,
    COMMAND_TYPE_UPDATE_TRAINING,
    COMMAND_TYPE_VOID_EDUCATION,
    COMMAND_TYPE_VOID_EXTERNAL_EMPLOYMENT,
    COMMAND_TYPE_VOID_RELATIVE,
    COMMAND_TYPE_VOID_TRAINING,
    PprCommandEnvelope,
)
from app.ppr.application.command_service import PprCommandApplicationService
from app.ppr.application.event_builder import build_section_event
from app.ppr.application.results import PprApplicationResult, RESULT_STATUS_COMMITTED
from app.ppr.domain.errors import PprNotMaterializedError
from app.ppr.domain.lifecycle_transitions import assert_lifecycle_allows_section_mutation
from app.ppr.domain.section_commands import (
    AddEducationRecord,
    AddExternalEmploymentRecord,
    AddRelativeRecord,
    AddTrainingRecord,
    SupersedeEducationRecord,
    SupersedeExternalEmploymentRecord,
    SupersedeRelativeRecord,
    SupersedeTrainingRecord,
    UpdateEducationRecord,
    UpdateRelativeRecord,
    UpdateTrainingRecord,
    VoidEducationRecord,
    VoidExternalEmploymentRecord,
    VoidRelativeRecord,
    VoidTrainingRecord,
)
from app.ppr.domain.section_handlers import (
    handle_add_education_record,
    handle_add_external_employment_record,
    handle_add_relative_record,
    handle_add_training_record,
    handle_supersede_education_record,
    handle_supersede_external_employment_record,
    handle_supersede_relative_record,
    handle_supersede_training_record,
    handle_update_education_record,
    handle_update_relative_record,
    handle_update_training_record,
    handle_void_education_record,
    handle_void_external_employment_record,
    handle_void_relative_record,
    handle_void_training_record,
)
from app.ppr.domain.section_models import SectionMutationResult
from app.ppr.infrastructure.application_unit_of_work import PprApplicationUnitOfWork


def _payload_dict(payload: Any) -> dict[str, Any]:
    if is_dataclass(payload):
        return asdict(payload)
    if isinstance(payload, dict):
        return dict(payload)
    raise TypeError("section command payload must be dataclass or dict")


class PprSectionApplicationService(PprCommandApplicationService):
    def add_education(self, envelope: PprCommandEnvelope) -> PprApplicationResult:
        return self._run_section_command(
            envelope,
            command_type=COMMAND_TYPE_ADD_EDUCATION,
            domain_factory=lambda person_id, payload: AddEducationRecord(person_id=person_id, **payload),
            handler=handle_add_education_record,
            section_code="PPR-EDUCATION",
        )

    def update_education(self, envelope: PprCommandEnvelope) -> PprApplicationResult:
        return self._run_section_command(
            envelope,
            command_type=COMMAND_TYPE_UPDATE_EDUCATION,
            domain_factory=lambda person_id, payload: UpdateEducationRecord(person_id=person_id, **payload),
            handler=handle_update_education_record,
            section_code="PPR-EDUCATION",
        )

    def void_education(self, envelope: PprCommandEnvelope) -> PprApplicationResult:
        return self._run_section_command(
            envelope,
            command_type=COMMAND_TYPE_VOID_EDUCATION,
            domain_factory=lambda person_id, payload: VoidEducationRecord(person_id=person_id, **payload),
            handler=handle_void_education_record,
            section_code="PPR-EDUCATION",
        )

    def supersede_education(self, envelope: PprCommandEnvelope) -> PprApplicationResult:
        return self._run_section_command(
            envelope,
            command_type=COMMAND_TYPE_SUPERSEDE_EDUCATION,
            domain_factory=self._supersede_education_factory,
            handler=handle_supersede_education_record,
            section_code="PPR-EDUCATION",
        )

    def add_training(self, envelope: PprCommandEnvelope) -> PprApplicationResult:
        return self._run_section_command(
            envelope,
            command_type=COMMAND_TYPE_ADD_TRAINING,
            domain_factory=lambda person_id, payload: AddTrainingRecord(person_id=person_id, **payload),
            handler=handle_add_training_record,
            section_code="PPR-TRAINING",
        )

    def update_training(self, envelope: PprCommandEnvelope) -> PprApplicationResult:
        return self._run_section_command(
            envelope,
            command_type=COMMAND_TYPE_UPDATE_TRAINING,
            domain_factory=lambda person_id, payload: UpdateTrainingRecord(person_id=person_id, **payload),
            handler=handle_update_training_record,
            section_code="PPR-TRAINING",
        )

    def void_training(self, envelope: PprCommandEnvelope) -> PprApplicationResult:
        return self._run_section_command(
            envelope,
            command_type=COMMAND_TYPE_VOID_TRAINING,
            domain_factory=lambda person_id, payload: VoidTrainingRecord(person_id=person_id, **payload),
            handler=handle_void_training_record,
            section_code="PPR-TRAINING",
        )

    def supersede_training(self, envelope: PprCommandEnvelope) -> PprApplicationResult:
        return self._run_section_command(
            envelope,
            command_type=COMMAND_TYPE_SUPERSEDE_TRAINING,
            domain_factory=self._supersede_training_factory,
            handler=handle_supersede_training_record,
            section_code="PPR-TRAINING",
        )

    def add_relative(self, envelope: PprCommandEnvelope) -> PprApplicationResult:
        return self._run_section_command(
            envelope,
            command_type=COMMAND_TYPE_ADD_RELATIVE,
            domain_factory=lambda person_id, payload: AddRelativeRecord(person_id=person_id, **payload),
            handler=handle_add_relative_record,
            section_code="PPR-FAMILY",
        )

    def update_relative(self, envelope: PprCommandEnvelope) -> PprApplicationResult:
        return self._run_section_command(
            envelope,
            command_type=COMMAND_TYPE_UPDATE_RELATIVE,
            domain_factory=lambda person_id, payload: UpdateRelativeRecord(person_id=person_id, **payload),
            handler=handle_update_relative_record,
            section_code="PPR-FAMILY",
        )

    def void_relative(self, envelope: PprCommandEnvelope) -> PprApplicationResult:
        return self._run_section_command(
            envelope,
            command_type=COMMAND_TYPE_VOID_RELATIVE,
            domain_factory=lambda person_id, payload: VoidRelativeRecord(person_id=person_id, **payload),
            handler=handle_void_relative_record,
            section_code="PPR-FAMILY",
        )

    def supersede_relative(self, envelope: PprCommandEnvelope) -> PprApplicationResult:
        return self._run_section_command(
            envelope,
            command_type=COMMAND_TYPE_SUPERSEDE_RELATIVE,
            domain_factory=self._supersede_relative_factory,
            handler=handle_supersede_relative_record,
            section_code="PPR-FAMILY",
        )

    def add_external_employment(self, envelope: PprCommandEnvelope) -> PprApplicationResult:
        return self._run_section_command(
            envelope,
            command_type=COMMAND_TYPE_ADD_EXTERNAL_EMPLOYMENT,
            domain_factory=lambda person_id, payload: AddExternalEmploymentRecord(
                person_id=person_id,
                **payload,
            ),
            handler=handle_add_external_employment_record,
            section_code="PPR-EMPLOYMENT-BIOGRAPHY",
        )

    def void_external_employment(self, envelope: PprCommandEnvelope) -> PprApplicationResult:
        return self._run_section_command(
            envelope,
            command_type=COMMAND_TYPE_VOID_EXTERNAL_EMPLOYMENT,
            domain_factory=lambda person_id, payload: VoidExternalEmploymentRecord(
                person_id=person_id,
                **payload,
            ),
            handler=handle_void_external_employment_record,
            section_code="PPR-EMPLOYMENT-BIOGRAPHY",
        )

    def supersede_external_employment(self, envelope: PprCommandEnvelope) -> PprApplicationResult:
        return self._run_section_command(
            envelope,
            command_type=COMMAND_TYPE_SUPERSEDE_EXTERNAL_EMPLOYMENT,
            domain_factory=self._supersede_external_employment_factory,
            handler=handle_supersede_external_employment_record,
            section_code="PPR-EMPLOYMENT-BIOGRAPHY",
        )

    @staticmethod
    def _supersede_education_factory(person_id: int, payload: dict[str, Any]) -> SupersedeEducationRecord:
        replacement_data = dict(payload["replacement"])
        replacement_data["person_id"] = person_id
        return SupersedeEducationRecord(
            person_id=person_id,
            record_id=int(payload["record_id"]),
            expected_updated_at=payload["expected_updated_at"],
            replacement=AddEducationRecord(**replacement_data),
        )

    @staticmethod
    def _supersede_training_factory(person_id: int, payload: dict[str, Any]) -> SupersedeTrainingRecord:
        replacement_data = dict(payload["replacement"])
        replacement_data["person_id"] = person_id
        return SupersedeTrainingRecord(
            person_id=person_id,
            record_id=int(payload["record_id"]),
            expected_updated_at=payload["expected_updated_at"],
            replacement=AddTrainingRecord(**replacement_data),
        )

    @staticmethod
    def _supersede_relative_factory(person_id: int, payload: dict[str, Any]) -> SupersedeRelativeRecord:
        replacement_data = dict(payload["replacement"])
        replacement_data["person_id"] = person_id
        return SupersedeRelativeRecord(
            person_id=person_id,
            record_id=int(payload["record_id"]),
            expected_updated_at=payload["expected_updated_at"],
            replacement=AddRelativeRecord(**replacement_data),
        )

    @staticmethod
    def _supersede_external_employment_factory(
        person_id: int,
        payload: dict[str, Any],
    ) -> SupersedeExternalEmploymentRecord:
        replacement_data = dict(payload["replacement"])
        replacement_data["person_id"] = person_id
        return SupersedeExternalEmploymentRecord(
            person_id=person_id,
            record_id=int(payload["record_id"]),
            expected_updated_at=payload["expected_updated_at"],
            replacement=AddExternalEmploymentRecord(**replacement_data),
        )

    def _run_section_command(
        self,
        envelope: PprCommandEnvelope,
        *,
        command_type: str,
        domain_factory: Callable[[int, dict[str, Any]], Any],
        handler: Callable[[Any, PprApplicationUnitOfWork], SectionMutationResult],
        section_code: str,
    ) -> PprApplicationResult:
        raw_payload = _payload_dict(envelope.payload)

        def mutate(uow: PprApplicationUnitOfWork, person_id: int) -> PprApplicationResult:
            envelope_row = uow.envelopes.load_envelope(person_id)
            if envelope_row is None:
                raise PprNotMaterializedError(f"PPR envelope not materialized for person_id={person_id}")
            assert_lifecycle_allows_section_mutation(envelope_row.lifecycle_state)
            if (
                envelope.expected_envelope_version is not None
                and envelope_row.version != envelope.expected_envelope_version
            ):
                from app.ppr.domain.errors import PprOptimisticConcurrencyConflictError

                raise PprOptimisticConcurrencyConflictError(
                    f"Stale envelope version for person_id={person_id}"
                )

            domain_command = domain_factory(person_id, raw_payload)
            mutation = handler(domain_command, uow)
            event = uow.events.append(
                build_section_event(
                    person_id=person_id,
                    actor_id=envelope.actor_id,
                    command_id=envelope.command_id,
                    correlation_id=envelope.correlation_id,
                    employee_context_id=envelope.employee_context_id or envelope.employee_id,
                    mutation=mutation,
                )
            )
            return PprApplicationResult(
                command_id=envelope.command_id,
                command_type=envelope.command_type,
                resolved_person_id=person_id,
                status=RESULT_STATUS_COMMITTED,
                envelope_version=envelope_row.version,
                section_record_id=mutation.record.record_id,
                section_mutation_kind=mutation.mutation_kind,
                event_ids=(event.event_id,),
                correlation_id=envelope.correlation_id,
            )

        return self._execute_with_idempotency(
            envelope,
            operation_code=command_type,
            fingerprint_payload=raw_payload,
            section_code=section_code,
            mutate=mutate,
        )

    def _run_section_participating(
        self,
        uow: PprApplicationUnitOfWork,
        envelope: PprCommandEnvelope,
        *,
        command_type: str,
        domain_factory: Callable[[int, dict[str, Any]], Any],
        handler: Callable[[Any, PprApplicationUnitOfWork], SectionMutationResult],
        section_code: str,
    ) -> PprApplicationResult:
        raw_payload = _payload_dict(envelope.payload)

        def mutate(inner_uow: PprApplicationUnitOfWork, person_id: int) -> PprApplicationResult:
            envelope_row = inner_uow.envelopes.load_envelope(person_id)
            if envelope_row is None:
                raise PprNotMaterializedError(f"PPR envelope not materialized for person_id={person_id}")
            assert_lifecycle_allows_section_mutation(envelope_row.lifecycle_state)
            domain_command = domain_factory(person_id, raw_payload)
            mutation = handler(domain_command, inner_uow)
            event = inner_uow.events.append(
                build_section_event(
                    person_id=person_id,
                    actor_id=envelope.actor_id,
                    command_id=envelope.command_id,
                    correlation_id=envelope.correlation_id,
                    employee_context_id=envelope.employee_context_id or envelope.employee_id,
                    mutation=mutation,
                )
            )
            table = "person_education" if section_code == "PPR-EDUCATION" else "person_training"
            return PprApplicationResult(
                command_id=envelope.command_id,
                command_type=envelope.command_type,
                resolved_person_id=person_id,
                status=RESULT_STATUS_COMMITTED,
                envelope_version=envelope_row.version,
                section_record_id=mutation.record.record_id,
                section_mutation_kind=mutation.mutation_kind,
                event_ids=(event.event_id,),
                correlation_id=envelope.correlation_id,
                extra={"target_table_name": table},
            )

        return self.execute_participating(
            uow,
            envelope,
            operation_code=command_type,
            fingerprint_payload=raw_payload,
            section_code=section_code,
            mutate=mutate,
        )

    def add_education_participating(
        self, uow: PprApplicationUnitOfWork, envelope: PprCommandEnvelope
    ) -> PprApplicationResult:
        return self._run_section_participating(
            uow,
            envelope,
            command_type=COMMAND_TYPE_ADD_EDUCATION,
            domain_factory=lambda person_id, payload: AddEducationRecord(person_id=person_id, **payload),
            handler=handle_add_education_record,
            section_code="PPR-EDUCATION",
        )

    def void_education_participating(
        self, uow: PprApplicationUnitOfWork, envelope: PprCommandEnvelope
    ) -> PprApplicationResult:
        return self._run_section_participating(
            uow,
            envelope,
            command_type=COMMAND_TYPE_VOID_EDUCATION,
            domain_factory=lambda person_id, payload: VoidEducationRecord(person_id=person_id, **payload),
            handler=handle_void_education_record,
            section_code="PPR-EDUCATION",
        )

    def supersede_education_participating(
        self, uow: PprApplicationUnitOfWork, envelope: PprCommandEnvelope
    ) -> PprApplicationResult:
        return self._run_section_participating(
            uow,
            envelope,
            command_type=COMMAND_TYPE_SUPERSEDE_EDUCATION,
            domain_factory=self._supersede_education_factory,
            handler=handle_supersede_education_record,
            section_code="PPR-EDUCATION",
        )

    def add_training_participating(
        self, uow: PprApplicationUnitOfWork, envelope: PprCommandEnvelope
    ) -> PprApplicationResult:
        return self._run_section_participating(
            uow,
            envelope,
            command_type=COMMAND_TYPE_ADD_TRAINING,
            domain_factory=lambda person_id, payload: AddTrainingRecord(person_id=person_id, **payload),
            handler=handle_add_training_record,
            section_code="PPR-TRAINING",
        )

    def void_training_participating(
        self, uow: PprApplicationUnitOfWork, envelope: PprCommandEnvelope
    ) -> PprApplicationResult:
        return self._run_section_participating(
            uow,
            envelope,
            command_type=COMMAND_TYPE_VOID_TRAINING,
            domain_factory=lambda person_id, payload: VoidTrainingRecord(person_id=person_id, **payload),
            handler=handle_void_training_record,
            section_code="PPR-TRAINING",
        )

    def supersede_training_participating(
        self, uow: PprApplicationUnitOfWork, envelope: PprCommandEnvelope
    ) -> PprApplicationResult:
        return self._run_section_participating(
            uow,
            envelope,
            command_type=COMMAND_TYPE_SUPERSEDE_TRAINING,
            domain_factory=self._supersede_training_factory,
            handler=handle_supersede_training_record,
            section_code="PPR-TRAINING",
        )
