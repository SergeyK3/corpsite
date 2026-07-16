"""Composite read orchestrator — assembles immutable PPR DTO (R6, read-only)."""
from __future__ import annotations

from datetime import UTC, datetime

from app.ppr.domain.identity_models import IdentityResolution
from app.ppr.domain.models import HR_RELATIONSHIP_CANDIDATE, PprEnvelope
from app.ppr.read.event_summary_reader import PprEventSummaryReader
from app.ppr.read.models import (
    PprCompositeReadMetadata,
    PprCompositeReadModel,
    PprCompositeSummary,
    PprEnvelopeReadSlice,
    PprEventSummary,
    PprIntendedEmploymentReadSlice,
)
from app.services.ppr_candidate_service import load_intended_employment
from app.ppr.read.section_aggregation import PprSectionAggregationReader
from app.ppr.read.uow import PprReadUnitOfWork


class PprCompositeReadOrchestrator:
    """Assembles composite read DTO from read repositories — no writes, no commands."""

    def __init__(self, *, event_limit: int = PprEventSummaryReader.DEFAULT_LIMIT) -> None:
        self._event_limit = event_limit

    def assemble(
        self,
        uow: PprReadUnitOfWork,
        *,
        resolved_person_id: int,
        identity_resolution: IdentityResolution,
        include_events: bool = True,
        include_superseded_void: bool = True,
    ) -> PprCompositeReadModel:
        identity = uow.identity.load_identity(resolved_person_id)
        envelope_slice = self._load_envelope_slice(uow, resolved_person_id)
        general = uow.persons.load_general_read_snapshot(resolved_person_id)

        section_reader = PprSectionAggregationReader(uow.sections, uow.connection)
        education = section_reader.load_education(
            resolved_person_id,
            include_superseded=include_superseded_void,
            include_voided=include_superseded_void,
        )
        training = section_reader.load_training(
            resolved_person_id,
            include_superseded=include_superseded_void,
            include_voided=include_superseded_void,
        )

        events: PprEventSummary | None = None
        if include_events:
            events = PprEventSummaryReader(uow.connection).load_recent(
                resolved_person_id,
                limit=self._event_limit,
            )

        intended_slice: PprIntendedEmploymentReadSlice | None = None
        if envelope_slice.hr_relationship_context == HR_RELATIONSHIP_CANDIDATE:
            intended = load_intended_employment(uow.connection, resolved_person_id)
            if intended is not None and (
                intended.org_unit_id is not None
                or intended.position_id is not None
                or intended.employment_rate is not None
                or intended.org_group_id is not None
            ):
                intended_slice = PprIntendedEmploymentReadSlice(
                    org_group_id=intended.org_group_id,
                    org_unit_id=intended.org_unit_id,
                    position_id=intended.position_id,
                    employment_rate=intended.employment_rate,
                    org_group_name=intended.org_group_name,
                    org_unit_name=intended.org_unit_name,
                    position_name=intended.position_name,
                )

        return PprCompositeReadModel(
            person_id=resolved_person_id,
            employee_id=identity_resolution.employee_id,
            materialized=envelope_slice.materialized,
            lifecycle_state=envelope_slice.lifecycle_state,
            hr_relationship_context=envelope_slice.hr_relationship_context,
            envelope_version=envelope_slice.version,
            envelope_created_at=envelope_slice.created_at,
            envelope_updated_at=envelope_slice.updated_at,
            identity=identity,
            identity_resolution=identity_resolution,
            general=general,
            education=education,
            training=training,
            events=events,
            intended_employment=intended_slice,
            metadata=PprCompositeReadMetadata(
                evaluated_at=datetime.now(UTC),
                source_person_id=identity_resolution.source_person_id,
                merge_redirected=identity_resolution.merge_redirected,
                requested_input_kind=identity_resolution.input_kind,
                requested_input_id=identity_resolution.input_id,
            ),
        )

    def assemble_summary(
        self,
        uow: PprReadUnitOfWork,
        *,
        resolved_person_id: int,
        identity_resolution: IdentityResolution,
    ) -> PprCompositeSummary:
        composite = self.assemble(
            uow,
            resolved_person_id=resolved_person_id,
            identity_resolution=identity_resolution,
            include_events=True,
            include_superseded_void=False,
        )
        recent_event_count = composite.events.returned_count if composite.events is not None else 0
        return PprCompositeSummary(
            person_id=composite.person_id,
            employee_id=composite.employee_id,
            materialized=composite.materialized,
            lifecycle_state=composite.lifecycle_state,
            hr_relationship_context=composite.hr_relationship_context,
            identity=composite.identity,
            identity_resolution=composite.identity_resolution,
            full_name=composite.general.full_name,
            education_active_count=len(composite.education.active),
            training_active_count=len(composite.training.active),
            recent_event_count=recent_event_count,
            metadata=composite.metadata,
        )

    @staticmethod
    def _load_envelope_slice(uow: PprReadUnitOfWork, person_id: int) -> PprEnvelopeReadSlice:
        envelope: PprEnvelope | None = uow.envelopes.load_envelope(person_id)
        if envelope is None:
            return PprEnvelopeReadSlice.not_materialized()
        return PprEnvelopeReadSlice(
            materialized=True,
            lifecycle_state=envelope.lifecycle_state,
            hr_relationship_context=envelope.hr_relationship_context,
            version=envelope.version,
            created_at=envelope.created_at,
            updated_at=envelope.updated_at,
        )
