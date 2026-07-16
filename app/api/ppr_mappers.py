"""Adapters from R6 immutable DTOs to PPR API schemas (R7)."""
from __future__ import annotations

from datetime import date

from app.api.ppr_schemas import (
    PprCompositeReadResponse,
    PprCompositeSummaryResponse,
    PprEducationRecordResponse,
    PprEventSummaryItemResponse,
    PprEventSummaryResponse,
    PprExternalEmploymentRecordResponse,
    PprGeneralResponse,
    PprIdentityResponse,
    PprIntendedEmploymentResponse,
    PprMaterializationResponse,
    PprMilitaryRecordDetailsResponse,
    PprMilitaryRecordResponse,
    PprReadMetadataResponse,
    PprRelativeRecordResponse,
    PprSectionResponse,
    PprTrainingRecordResponse,
)
from app.ppr.domain.identity_models import INPUT_KIND_EMPLOYEE_ID, INPUT_KIND_PERSON_ID
from app.ppr.domain.section_models import (
    EducationRecord,
    ExternalEmploymentRecord,
    MilitaryServiceRecord,
    RelativeRecord,
    SECTION_CODE_PPR_EDUCATION,
    SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY,
    SECTION_CODE_PPR_FAMILY,
    SECTION_CODE_PPR_MILITARY,
    SECTION_CODE_PPR_TRAINING,
    TrainingRecord,
)
from app.ppr.read.models import PprCompositeReadModel, PprCompositeSummary, PprSectionAggregation

RELATIONSHIP_TYPE_LABELS: dict[str, str] = {
    "father": "Отец",
    "mother": "Мать",
    "brother": "Брат",
    "sister": "Сестра",
    "son": "Сын",
    "daughter": "Дочь",
    "spouse": "Супруг(а)",
    "other_close": "Иной близкий родственник",
}


def _relationship_type_label(relationship_type: str) -> str:
    return RELATIONSHIP_TYPE_LABELS.get(relationship_type, relationship_type)


def _mask_iin(iin: str | None) -> str | None:
    if not iin:
        return None
    digits = "".join(ch for ch in iin if ch.isdigit())
    if len(digits) != 12:
        return None
    return f"********{digits[-4:]}"


def _education_record(record: EducationRecord) -> PprEducationRecordResponse:
    return PprEducationRecordResponse(
        record_id=record.record_id,
        education_kind=record.education_kind,
        institution_type=record.institution_type,
        institution_name=record.institution_name,
        specialty=record.specialty,
        qualification=record.qualification,
        started_at=record.started_at,
        completed_at=record.completed_at,
        diploma_number=record.diploma_number,
        document_date=record.document_date,
        verification_status=record.verification_status,
        lifecycle_status=record.lifecycle_status,
    )


def _training_record(record: TrainingRecord) -> PprTrainingRecordResponse:
    return PprTrainingRecordResponse(
        record_id=record.record_id,
        training_kind=record.training_kind,
        title=record.title,
        organization_name=record.organization_name,
        hours=record.hours,
        started_at=record.started_at,
        completed_at=record.completed_at,
        certificate_number=record.certificate_number,
        document_date=record.document_date,
        verification_status=record.verification_status,
        lifecycle_status=record.lifecycle_status,
    )


def _relative_record(record: RelativeRecord) -> PprRelativeRecordResponse:
    return PprRelativeRecordResponse(
        record_id=record.record_id,
        relationship_type=record.relationship_type,
        relationship_label=_relationship_type_label(record.relationship_type),
        full_name=record.full_name,
        birth_date=record.birth_date,
        birth_place=record.birth_place,
        organization_name=record.organization_name,
        residence_address=record.residence_address,
        notes=record.notes,
        verification_status=record.verification_status,
        lifecycle_status=record.lifecycle_status,
    )


def _external_employment_record(record: ExternalEmploymentRecord) -> PprExternalEmploymentRecordResponse:
    provenance = dict(record.provenance) if record.provenance is not None else None
    return PprExternalEmploymentRecordResponse(
        record_id=record.record_id,
        record_kind=record.record_kind,
        employer_name=record.employer_name,
        department_name=record.department_name,
        position_title=record.position_title,
        employment_type=record.employment_type,
        started_at=record.started_at,
        ended_at=record.ended_at,
        termination_reason=record.termination_reason,
        document_reference=record.document_reference,
        source_system=record.source_system,
        source_id=record.source_id,
        provenance=provenance,
        notes=record.notes,
        employee_context_id=record.employee_context_id,
        verification_status=record.verification_status,
        lifecycle_status=record.lifecycle_status,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _military_record_base(record: MilitaryServiceRecord) -> dict:
    provenance = dict(record.provenance) if record.provenance is not None else None
    metadata = dict(record.metadata) if record.metadata is not None else None
    return {
        "record_id": record.record_id,
        "record_kind": record.record_kind,
        "obligation_status": record.obligation_status,
        "registration_category": record.registration_category,
        "military_rank": record.military_rank,
        "military_specialty_code": record.military_specialty_code,
        "personnel_composition": record.personnel_composition,
        "fitness_category": record.fitness_category,
        "registration_status": record.registration_status,
        "commissariat_name": record.commissariat_name,
        "registered_at": record.registered_at,
        "deregistered_at": record.deregistered_at,
        "notes": record.notes,
        "source_type": record.source_type,
        "provenance": provenance,
        "metadata": metadata,
        "employee_context_id": record.employee_context_id,
        "verification_status": record.verification_status,
        "lifecycle_status": record.lifecycle_status,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def _military_record(
    record: MilitaryServiceRecord,
    *,
    include_restricted: bool,
) -> PprMilitaryRecordResponse | PprMilitaryRecordDetailsResponse:
    base = _military_record_base(record)
    if include_restricted:
        return PprMilitaryRecordDetailsResponse(
            **base,
            military_id_book_series=record.military_id_book_series,
            military_id_book_number=record.military_id_book_number,
            registration_certificate_series=record.registration_certificate_series,
            registration_certificate_number=record.registration_certificate_number,
        )
    return PprMilitaryRecordResponse(**base)


def _section_response(
    section: PprSectionAggregation,
    *,
    include_military_restricted: bool = False,
) -> PprSectionResponse:
    if section.section_code == SECTION_CODE_PPR_EDUCATION:
        mapper = _education_record
        active = [mapper(record) for record in section.active]  # type: ignore[arg-type]
        superseded = [mapper(record) for record in section.superseded]  # type: ignore[arg-type]
        voided = [mapper(record) for record in section.voided]  # type: ignore[arg-type]
    elif section.section_code == SECTION_CODE_PPR_TRAINING:
        mapper = _training_record
        active = [mapper(record) for record in section.active]  # type: ignore[arg-type]
        superseded = [mapper(record) for record in section.superseded]  # type: ignore[arg-type]
        voided = [mapper(record) for record in section.voided]  # type: ignore[arg-type]
    elif section.section_code == SECTION_CODE_PPR_FAMILY:
        mapper = _relative_record
        active = [mapper(record) for record in section.active]  # type: ignore[arg-type]
        superseded = [mapper(record) for record in section.superseded]  # type: ignore[arg-type]
        voided = [mapper(record) for record in section.voided]  # type: ignore[arg-type]
    elif section.section_code == SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY:
        mapper = _external_employment_record
        active = [mapper(record) for record in section.active]  # type: ignore[arg-type]
        superseded = [mapper(record) for record in section.superseded]  # type: ignore[arg-type]
        voided = [mapper(record) for record in section.voided]  # type: ignore[arg-type]
    elif section.section_code == SECTION_CODE_PPR_MILITARY:
        active = [
            _military_record(record, include_restricted=include_military_restricted)  # type: ignore[arg-type]
            for record in section.active
        ]
        superseded = [
            _military_record(record, include_restricted=include_military_restricted)  # type: ignore[arg-type]
            for record in section.superseded
        ]
        voided = [
            _military_record(record, include_restricted=include_military_restricted)  # type: ignore[arg-type]
            for record in section.voided
        ]
    else:
        raise ValueError(f"Unsupported section_code for API mapping: {section.section_code!r}")
    return PprSectionResponse(
        section_code=section.section_code,
        active=active,
        superseded=superseded,
        voided=voided,
    )


def composite_to_response(
    composite: PprCompositeReadModel,
    *,
    read_mode: str,
    source: str,
    include_sensitive_identity: bool,
    include_military_restricted: bool = False,
    warnings: list[str] | None = None,
) -> PprCompositeReadResponse:
    resolution = composite.identity_resolution
    requested_person_id = resolution.input_id if resolution.input_kind == INPUT_KIND_PERSON_ID else None
    requested_employee_id = resolution.input_id if resolution.input_kind == INPUT_KIND_EMPLOYEE_ID else None
    iin_value = composite.general.iin if include_sensitive_identity else _mask_iin(composite.general.iin)

    intended_response: PprIntendedEmploymentResponse | None = None
    if composite.intended_employment is not None:
        intended = composite.intended_employment
        intended_response = PprIntendedEmploymentResponse(
            org_group_id=intended.org_group_id,
            org_unit_id=intended.org_unit_id,
            position_id=intended.position_id,
            employment_rate=intended.employment_rate,
            org_group_name=intended.org_group_name,
            org_unit_name=intended.org_unit_name,
            position_name=intended.position_name,
        )

    return PprCompositeReadResponse(
        identity=PprIdentityResponse(
            requested_person_id=requested_person_id,
            requested_employee_id=requested_employee_id,
            resolved_person_id=composite.person_id,
            merge_redirected=composite.metadata.merge_redirected,
            merge_chain=list(resolution.merge_chain),
            employee_context_id=composite.employee_id,
            person_status=composite.identity.person_status,
            match_key=composite.identity.match_key,
            iin=iin_value,
        ),
        materialization=PprMaterializationResponse(
            materialized=composite.materialized,
            lifecycle_state=composite.lifecycle_state,
            hr_relationship_context=composite.hr_relationship_context,
            envelope_version=composite.envelope_version,
            created_at=composite.envelope_created_at,
            updated_at=composite.envelope_updated_at,
        ),
        general=PprGeneralResponse(
            full_name=composite.general.full_name,
            last_name=composite.general.last_name,
            first_name=composite.general.first_name,
            middle_name=composite.general.middle_name,
            birth_date=composite.general.birth_date,
            iin=iin_value,
            created_at=composite.general.created_at,
            updated_at=composite.general.updated_at,
        ),
        sections={
            SECTION_CODE_PPR_EDUCATION: _section_response(composite.education),
            SECTION_CODE_PPR_TRAINING: _section_response(composite.training),
            SECTION_CODE_PPR_FAMILY: _section_response(composite.family),
            SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY: _section_response(composite.external_employment),
            SECTION_CODE_PPR_MILITARY: _section_response(
                composite.military,
                include_military_restricted=include_military_restricted,
            ),
        },
        events=(
            PprEventSummaryResponse(
                recent=[
                    PprEventSummaryItemResponse(
                        event_id=item.event_id,
                        event_type=item.event_type,
                        category=item.category,
                        record_table_name=item.record_table_name,
                        record_id=item.record_id,
                        occurred_at=item.occurred_at,
                        section_code=item.section_code,
                        domain_code=item.domain_code,
                    )
                    for item in composite.events.recent
                ],
                returned_count=composite.events.returned_count,
                limit=composite.events.limit,
            )
            if composite.events is not None
            else None
        ),
        intended_employment=intended_response,
        metadata=PprReadMetadataResponse(
            read_mode=read_mode,
            source=source,
            generated_at=composite.metadata.evaluated_at,
            warnings=list(warnings or ()),
            transitional=False,
            merge_redirected=composite.metadata.merge_redirected,
            source_person_id=composite.metadata.source_person_id,
            requested_input_kind=composite.metadata.requested_input_kind,
            requested_input_id=composite.metadata.requested_input_id,
        ),
    )


def summary_to_response(
    summary: PprCompositeSummary,
    *,
    read_mode: str,
    source: str,
    include_sensitive_identity: bool,
) -> PprCompositeSummaryResponse:
    resolution = summary.identity_resolution
    requested_person_id = resolution.input_id if resolution.input_kind == INPUT_KIND_PERSON_ID else None
    requested_employee_id = resolution.input_id if resolution.input_kind == INPUT_KIND_EMPLOYEE_ID else None
    iin_value = summary.identity.iin if include_sensitive_identity else _mask_iin(summary.identity.iin)

    return PprCompositeSummaryResponse(
        identity=PprIdentityResponse(
            requested_person_id=requested_person_id,
            requested_employee_id=requested_employee_id,
            resolved_person_id=summary.person_id,
            merge_redirected=summary.metadata.merge_redirected,
            merge_chain=list(resolution.merge_chain),
            employee_context_id=summary.employee_id,
            person_status=summary.identity.person_status,
            match_key=summary.identity.match_key,
            iin=iin_value,
        ),
        materialization=PprMaterializationResponse(
            materialized=summary.materialized,
            lifecycle_state=summary.lifecycle_state,
            hr_relationship_context=summary.hr_relationship_context,
            envelope_version=None,
            created_at=None,
            updated_at=None,
        ),
        full_name=summary.full_name,
        education_active_count=summary.education_active_count,
        training_active_count=summary.training_active_count,
        family_active_count=summary.family_active_count,
        external_employment_active_count=summary.external_employment_active_count,
        military_active_count=summary.military_active_count,
        recent_event_count=summary.recent_event_count,
        metadata=PprReadMetadataResponse(
            read_mode=read_mode,
            source=source,
            generated_at=summary.metadata.evaluated_at,
            warnings=[],
            transitional=False,
            merge_redirected=summary.metadata.merge_redirected,
            source_person_id=summary.metadata.source_person_id,
            requested_input_kind=summary.metadata.requested_input_kind,
            requested_input_id=summary.metadata.requested_input_id,
        ),
    )
