"""PPR query application service — read-only facade (R6)."""
from __future__ import annotations

from app.ppr.application.identity_resolution import resolve_canonical_person_id
from app.ppr.domain.errors import PprIdentityInputMismatchError
from app.ppr.domain.identity_models import IdentityResolution, PersonIdentitySnapshot
from app.ppr.domain.section_models import (
    SECTION_CODE_PPR_EDUCATION,
    SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY,
    SECTION_CODE_PPR_FAMILY,
    SECTION_CODE_PPR_MILITARY,
    SECTION_CODE_PPR_TRAINING,
)
from app.ppr.read.models import PprCompositeReadModel, PprCompositeSummary, PprSectionAggregation
from app.ppr.read.orchestrator import PprCompositeReadOrchestrator
from app.ppr.read.section_aggregation import PprSectionAggregationReader
from app.ppr.read.uow import PprReadUnitOfWork


class PprQueryApplicationService:
    """Read path orchestration — identity resolution + composite assembly; no writes."""

    def __init__(
        self,
        *,
        orchestrator: PprCompositeReadOrchestrator | None = None,
        uow_factory: type[PprReadUnitOfWork] = PprReadUnitOfWork,
    ) -> None:
        self._orchestrator = orchestrator or PprCompositeReadOrchestrator()
        self._uow_factory = uow_factory

    def load_by_person_id(
        self,
        person_id: int,
        *,
        include_events: bool = True,
    ) -> PprCompositeReadModel:
        with self._uow_factory() as uow:
            resolution = uow.identity.resolve_person_id(person_id)
            survivor_id = resolution.resolved_person_id
            return self._orchestrator.assemble(
                uow,
                resolved_person_id=survivor_id,
                identity_resolution=resolution,
                include_events=include_events,
            )

    def load_by_employee_id(
        self,
        employee_id: int,
        *,
        include_events: bool = True,
    ) -> PprCompositeReadModel:
        with self._uow_factory() as uow:
            resolution = uow.identity.resolve_employee_id(employee_id)
            survivor_id = resolution.resolved_person_id
            return self._orchestrator.assemble(
                uow,
                resolved_person_id=survivor_id,
                identity_resolution=resolution,
                include_events=include_events,
            )

    def load_identity(
        self,
        *,
        person_id: int | None = None,
        employee_id: int | None = None,
    ) -> tuple[PersonIdentitySnapshot, IdentityResolution]:
        with self._uow_factory() as uow:
            if person_id is not None and employee_id is not None:
                canonical = resolve_canonical_person_id(
                    uow.identity,
                    person_id=person_id,
                    employee_id=employee_id,
                )
                resolution = uow.identity.resolve_person_id(person_id)
                if resolution.resolved_person_id != canonical:
                    resolution = uow.identity.resolve_employee_id(employee_id)
            elif person_id is not None:
                resolution = uow.identity.resolve_person_id(person_id)
                canonical = resolution.resolved_person_id
            elif employee_id is not None:
                resolution = uow.identity.resolve_employee_id(employee_id)
                canonical = resolution.resolved_person_id
            else:
                raise PprIdentityInputMismatchError("person_id or employee_id is required")
            snapshot = uow.identity.load_identity(canonical)
            return snapshot, resolution

    def load_sections(
        self,
        person_id: int,
        *,
        include_superseded_void: bool = True,
    ) -> dict[str, PprSectionAggregation]:
        with self._uow_factory() as uow:
            resolution = uow.identity.resolve_person_id(person_id)
            survivor_id = resolution.resolved_person_id
            reader = PprSectionAggregationReader(uow.sections, uow.connection)
            return {
                SECTION_CODE_PPR_EDUCATION: reader.load_education(
                    survivor_id,
                    include_superseded=include_superseded_void,
                    include_voided=include_superseded_void,
                ),
                SECTION_CODE_PPR_TRAINING: reader.load_training(
                    survivor_id,
                    include_superseded=include_superseded_void,
                    include_voided=include_superseded_void,
                ),
                SECTION_CODE_PPR_FAMILY: reader.load_family(
                    survivor_id,
                    include_superseded=include_superseded_void,
                    include_voided=include_superseded_void,
                ),
                SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY: reader.load_external_employment(
                    survivor_id,
                    include_superseded=include_superseded_void,
                    include_voided=include_superseded_void,
                ),
                SECTION_CODE_PPR_MILITARY: reader.load_military(
                    survivor_id,
                    include_superseded=include_superseded_void,
                    include_voided=include_superseded_void,
                ),
            }

    def load_summary(
        self,
        *,
        person_id: int | None = None,
        employee_id: int | None = None,
    ) -> PprCompositeSummary:
        with self._uow_factory() as uow:
            if person_id is not None and employee_id is not None:
                canonical = resolve_canonical_person_id(
                    uow.identity,
                    person_id=person_id,
                    employee_id=employee_id,
                )
                resolution = uow.identity.resolve_person_id(person_id)
                if resolution.resolved_person_id != canonical:
                    resolution = uow.identity.resolve_employee_id(employee_id)
            elif person_id is not None:
                resolution = uow.identity.resolve_person_id(person_id)
            elif employee_id is not None:
                resolution = uow.identity.resolve_employee_id(employee_id)
            else:
                raise PprIdentityInputMismatchError("person_id or employee_id is required")
            return self._orchestrator.assemble_summary(
                uow,
                resolved_person_id=resolution.resolved_person_id,
                identity_resolution=resolution,
            )
