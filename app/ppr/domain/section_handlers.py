"""Domain command handlers for PPR sections (R4 — no commit, events, or BC calls)."""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from app.db.models.personnel_migration import (
    EDUCATION_KINDS,
    EXTERNAL_EMPLOYMENT_SOURCE_MANUAL,
    LIFECYCLE_STATUS_ACTIVE,
    SECTION_SOURCE_TYPE_ENTERED,
    TRAINING_KINDS,
)
from app.ppr.domain.errors import (
    SectionDuplicateRecordError,
    SectionRecordNotFoundError,
    SectionValidationError,
)
from app.ppr.domain.section_commands import (
    AddEducationRecord,
    AddExternalEmploymentRecord,
    AddRelativeRecord,
    AddTrainingRecord,
    CreateMilitaryServiceRecord,
    SupersedeEducationRecord,
    SupersedeExternalEmploymentRecord,
    SupersedeMilitaryServiceRecord,
    SupersedeRelativeRecord,
    SupersedeTrainingRecord,
    UpdateEducationRecord,
    UpdateRelativeRecord,
    UpdateTrainingRecord,
    VoidEducationRecord,
    VoidExternalEmploymentRecord,
    VoidMilitaryServiceRecord,
    VoidRelativeRecord,
    VoidTrainingRecord,
)
from app.ppr.domain.section_models import (
    MUTATION_KIND_INSERT,
    MUTATION_KIND_SUPERSEDE,
    MUTATION_KIND_UPDATE,
    MUTATION_KIND_VOID,
    SECTION_CODE_PPR_EDUCATION,
    SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY,
    SECTION_CODE_PPR_FAMILY,
    SECTION_CODE_PPR_MILITARY,
    SECTION_CODE_PPR_TRAINING,
    EducationRecord,
    ExternalEmploymentRecord,
    MilitaryServiceRecord,
    RelativeRecord,
    SectionMutationResult,
    TrainingRecord,
)
from app.ppr.domain.section_record_validation import (
    validate_external_employment_record,
    validate_military_service_record,
    validate_relative_record,
)
from app.ppr.domain.unit_of_work import UnitOfWork


def _require_positive_person_id(person_id: int) -> None:
    if person_id <= 0:
        raise SectionValidationError("person_id must be positive")


def _require_non_empty(value: str | None, field: str) -> None:
    if not value or not str(value).strip():
        raise SectionValidationError(f"{field} is required")


def _education_fingerprint(record: EducationRecord) -> tuple[Any, ...]:
    return (record.education_kind, record.institution_name or "")


def _training_fingerprint(record: TrainingRecord) -> tuple[Any, ...]:
    return (record.training_kind, record.title or "", record.organization_name or "")


def _assert_no_duplicate_education(
    uow: UnitOfWork,
    *,
    person_id: int,
    candidate: EducationRecord,
    exclude_record_id: int | None = None,
) -> None:
    active = uow.sections.load_active_records(person_id, SECTION_CODE_PPR_EDUCATION)
    fp = _education_fingerprint(candidate)
    for existing in active:
        if not isinstance(existing, EducationRecord):
            continue
        if exclude_record_id is not None and existing.record_id == exclude_record_id:
            continue
        if _education_fingerprint(existing) == fp:
            raise SectionDuplicateRecordError(
                f"Duplicate active education record for person_id={person_id}: "
                f"kind={candidate.education_kind!r}, institution={candidate.institution_name!r}"
            )


def _assert_no_duplicate_training(
    uow: UnitOfWork,
    *,
    person_id: int,
    candidate: TrainingRecord,
    exclude_record_id: int | None = None,
) -> None:
    active = uow.sections.load_active_records(person_id, SECTION_CODE_PPR_TRAINING)
    fp = _training_fingerprint(candidate)
    for existing in active:
        if not isinstance(existing, TrainingRecord):
            continue
        if exclude_record_id is not None and existing.record_id == exclude_record_id:
            continue
        if _training_fingerprint(existing) == fp:
            raise SectionDuplicateRecordError(
                f"Duplicate active training record for person_id={person_id}: "
                f"kind={candidate.training_kind!r}, title={candidate.title!r}"
            )


def _require_active_education(uow: UnitOfWork, person_id: int, record_id: int) -> EducationRecord:
    loaded = uow.sections.load_record(person_id, SECTION_CODE_PPR_EDUCATION, record_id)
    if loaded is None or not isinstance(loaded, EducationRecord):
        raise SectionRecordNotFoundError(
            f"Education record not found: person_id={person_id}, record_id={record_id}"
        )
    if loaded.lifecycle_status != LIFECYCLE_STATUS_ACTIVE:
        raise SectionValidationError(
            f"Education record {record_id} is not active (status={loaded.lifecycle_status!r})"
        )
    return loaded


def _require_active_training(uow: UnitOfWork, person_id: int, record_id: int) -> TrainingRecord:
    loaded = uow.sections.load_record(person_id, SECTION_CODE_PPR_TRAINING, record_id)
    if loaded is None or not isinstance(loaded, TrainingRecord):
        raise SectionRecordNotFoundError(
            f"Training record not found: person_id={person_id}, record_id={record_id}"
        )
    if loaded.lifecycle_status != LIFECYCLE_STATUS_ACTIVE:
        raise SectionValidationError(
            f"Training record {record_id} is not active (status={loaded.lifecycle_status!r})"
        )
    return loaded


def handle_add_education_record(
    command: AddEducationRecord,
    uow: UnitOfWork,
) -> SectionMutationResult:
    _require_positive_person_id(command.person_id)
    _require_non_empty(command.education_kind, "education_kind")
    if command.education_kind not in EDUCATION_KINDS:
        raise SectionValidationError(f"invalid education_kind: {command.education_kind!r}")

    candidate = EducationRecord(
        person_id=command.person_id,
        education_kind=command.education_kind,
        employee_context_id=command.employee_context_id,
        institution_type=command.institution_type,
        institution_name=command.institution_name,
        specialty=command.specialty,
        qualification=command.qualification,
        started_at=command.started_at,
        completed_at=command.completed_at,
        diploma_number=command.diploma_number,
        document_date=command.document_date,
        metadata=dict(command.metadata) if command.metadata is not None else None,
    )
    _assert_no_duplicate_education(uow, person_id=command.person_id, candidate=candidate)
    mutations = uow.section_mutations()
    inserted = mutations.insert_record(candidate)
    if not isinstance(inserted, EducationRecord):
        raise SectionValidationError("insert_record returned unexpected section type")
    return SectionMutationResult(record=inserted, mutation_kind=MUTATION_KIND_INSERT)


def handle_update_education_record(
    command: UpdateEducationRecord,
    uow: UnitOfWork,
) -> SectionMutationResult:
    _require_positive_person_id(command.person_id)
    current = _require_active_education(uow, command.person_id, command.record_id)
    if current.person_id != command.person_id:
        raise SectionValidationError("person_id does not match loaded education record")

    updated = replace(
        current,
        education_kind=command.education_kind if command.education_kind is not None else current.education_kind,
        institution_type=(
            command.institution_type if command.institution_type is not None else current.institution_type
        ),
        institution_name=(
            command.institution_name if command.institution_name is not None else current.institution_name
        ),
        specialty=command.specialty if command.specialty is not None else current.specialty,
        qualification=command.qualification if command.qualification is not None else current.qualification,
        started_at=command.started_at if command.started_at is not None else current.started_at,
        completed_at=command.completed_at if command.completed_at is not None else current.completed_at,
        diploma_number=command.diploma_number if command.diploma_number is not None else current.diploma_number,
        document_date=command.document_date if command.document_date is not None else current.document_date,
        metadata=dict(command.metadata) if command.metadata is not None else current.metadata,
    )
    if updated.education_kind not in EDUCATION_KINDS:
        raise SectionValidationError(f"invalid education_kind: {updated.education_kind!r}")

    _assert_no_duplicate_education(
        uow,
        person_id=command.person_id,
        candidate=updated,
        exclude_record_id=command.record_id,
    )
    persisted = uow.section_mutations().update_record(
        updated,
        expected_updated_at=command.expected_updated_at,
    )
    if not isinstance(persisted, EducationRecord):
        raise SectionValidationError("update_record returned unexpected section type")
    return SectionMutationResult(record=persisted, mutation_kind=MUTATION_KIND_UPDATE)


def handle_void_education_record(
    command: VoidEducationRecord,
    uow: UnitOfWork,
) -> SectionMutationResult:
    _require_positive_person_id(command.person_id)
    _require_non_empty(command.reason, "reason")
    _require_active_education(uow, command.person_id, command.record_id)
    voided = uow.section_mutations().void_record(
        command.person_id,
        SECTION_CODE_PPR_EDUCATION,
        command.record_id,
        expected_updated_at=command.expected_updated_at,
    )
    if not isinstance(voided, EducationRecord):
        raise SectionValidationError("void_record returned unexpected section type")
    return SectionMutationResult(record=voided, mutation_kind=MUTATION_KIND_VOID)


def handle_supersede_education_record(
    command: SupersedeEducationRecord,
    uow: UnitOfWork,
) -> SectionMutationResult:
    _require_positive_person_id(command.person_id)
    _require_active_education(uow, command.person_id, command.record_id)
    if command.replacement.person_id != command.person_id:
        raise SectionValidationError("replacement.person_id must match supersede person_id")

    replacement = EducationRecord(
        person_id=command.replacement.person_id,
        education_kind=command.replacement.education_kind,
        employee_context_id=command.replacement.employee_context_id,
        institution_type=command.replacement.institution_type,
        institution_name=command.replacement.institution_name,
        specialty=command.replacement.specialty,
        qualification=command.replacement.qualification,
        started_at=command.replacement.started_at,
        completed_at=command.replacement.completed_at,
        diploma_number=command.replacement.diploma_number,
        document_date=command.replacement.document_date,
        metadata=dict(command.replacement.metadata) if command.replacement.metadata is not None else None,
    )
    if replacement.education_kind not in EDUCATION_KINDS:
        raise SectionValidationError(f"invalid education_kind: {replacement.education_kind!r}")
    _require_non_empty(replacement.education_kind, "education_kind")

    old_record, new_record = uow.section_mutations().supersede_pair(
        command.person_id,
        SECTION_CODE_PPR_EDUCATION,
        command.record_id,
        replacement,
        expected_updated_at=command.expected_updated_at,
    )
    if not isinstance(old_record, EducationRecord) or not isinstance(new_record, EducationRecord):
        raise SectionValidationError("supersede_pair returned unexpected section types")
    return SectionMutationResult(
        record=new_record,
        mutation_kind=MUTATION_KIND_SUPERSEDE,
        prior_record=old_record,
    )


def _relative_fingerprint(record: RelativeRecord) -> tuple[Any, ...]:
    return (record.relationship_type, record.full_name.strip())


def _relative_from_add(command: AddRelativeRecord) -> RelativeRecord:
    record = RelativeRecord(
        person_id=command.person_id,
        relationship_type=command.relationship_type,
        full_name=str(command.full_name).strip(),
        birth_date=command.birth_date,
        birth_place=command.birth_place,
        organization_name=command.organization_name,
        residence_address=command.residence_address,
        notes=command.notes,
        source_type=command.source_type or SECTION_SOURCE_TYPE_ENTERED,
        metadata=dict(command.metadata) if command.metadata is not None else None,
    )
    validate_relative_record(record)
    return record


def _assert_no_duplicate_relative(
    uow: UnitOfWork,
    *,
    person_id: int,
    candidate: RelativeRecord,
    exclude_record_id: int | None = None,
) -> None:
    active = uow.sections.load_active_records(person_id, SECTION_CODE_PPR_FAMILY)
    fp = _relative_fingerprint(candidate)
    for existing in active:
        if not isinstance(existing, RelativeRecord):
            continue
        if exclude_record_id is not None and existing.record_id == exclude_record_id:
            continue
        if _relative_fingerprint(existing) == fp:
            raise SectionDuplicateRecordError(
                f"Duplicate active relative record for person_id={person_id}: "
                f"relationship_type={candidate.relationship_type!r}, full_name={candidate.full_name!r}"
            )


def _require_active_relative(uow: UnitOfWork, person_id: int, record_id: int) -> RelativeRecord:
    loaded = uow.sections.load_record(person_id, SECTION_CODE_PPR_FAMILY, record_id)
    if loaded is None or not isinstance(loaded, RelativeRecord):
        raise SectionRecordNotFoundError(
            f"Relative record not found: person_id={person_id}, record_id={record_id}"
        )
    if loaded.lifecycle_status != LIFECYCLE_STATUS_ACTIVE:
        raise SectionValidationError(
            f"Relative record {record_id} is not active (status={loaded.lifecycle_status!r})"
        )
    return loaded


def handle_add_relative_record(
    command: AddRelativeRecord,
    uow: UnitOfWork,
) -> SectionMutationResult:
    _require_positive_person_id(command.person_id)
    candidate = _relative_from_add(command)
    _assert_no_duplicate_relative(uow, person_id=command.person_id, candidate=candidate)
    inserted = uow.section_mutations().insert_record(candidate)
    if not isinstance(inserted, RelativeRecord):
        raise SectionValidationError("insert_record returned unexpected section type")
    return SectionMutationResult(record=inserted, mutation_kind=MUTATION_KIND_INSERT)


def handle_update_relative_record(
    command: UpdateRelativeRecord,
    uow: UnitOfWork,
) -> SectionMutationResult:
    _require_positive_person_id(command.person_id)
    current = _require_active_relative(uow, command.person_id, command.record_id)

    updated = replace(
        current,
        relationship_type=(
            command.relationship_type if command.relationship_type is not None else current.relationship_type
        ),
        full_name=str(command.full_name).strip() if command.full_name is not None else current.full_name,
        birth_date=command.birth_date if command.birth_date is not None else current.birth_date,
        birth_place=command.birth_place if command.birth_place is not None else current.birth_place,
        organization_name=(
            command.organization_name if command.organization_name is not None else current.organization_name
        ),
        residence_address=(
            command.residence_address if command.residence_address is not None else current.residence_address
        ),
        notes=command.notes if command.notes is not None else current.notes,
        source_type=command.source_type if command.source_type is not None else current.source_type,
        metadata=dict(command.metadata) if command.metadata is not None else current.metadata,
    )
    validate_relative_record(updated)
    _assert_no_duplicate_relative(
        uow,
        person_id=command.person_id,
        candidate=updated,
        exclude_record_id=command.record_id,
    )
    persisted = uow.section_mutations().update_record(
        updated,
        expected_updated_at=command.expected_updated_at,
    )
    if not isinstance(persisted, RelativeRecord):
        raise SectionValidationError("update_record returned unexpected section type")
    return SectionMutationResult(record=persisted, mutation_kind=MUTATION_KIND_UPDATE)


def handle_void_relative_record(
    command: VoidRelativeRecord,
    uow: UnitOfWork,
) -> SectionMutationResult:
    _require_positive_person_id(command.person_id)
    _require_non_empty(command.reason, "reason")
    _require_active_relative(uow, command.person_id, command.record_id)
    voided = uow.section_mutations().void_record(
        command.person_id,
        SECTION_CODE_PPR_FAMILY,
        command.record_id,
        expected_updated_at=command.expected_updated_at,
    )
    if not isinstance(voided, RelativeRecord):
        raise SectionValidationError("void_record returned unexpected section type")
    return SectionMutationResult(record=voided, mutation_kind=MUTATION_KIND_VOID)


def handle_supersede_relative_record(
    command: SupersedeRelativeRecord,
    uow: UnitOfWork,
) -> SectionMutationResult:
    _require_positive_person_id(command.person_id)
    _require_active_relative(uow, command.person_id, command.record_id)
    if command.replacement.person_id != command.person_id:
        raise SectionValidationError("replacement.person_id must match supersede person_id")

    replacement = _relative_from_add(command.replacement)
    old_record, new_record = uow.section_mutations().supersede_pair(
        command.person_id,
        SECTION_CODE_PPR_FAMILY,
        command.record_id,
        replacement,
        expected_updated_at=command.expected_updated_at,
    )
    if not isinstance(old_record, RelativeRecord) or not isinstance(new_record, RelativeRecord):
        raise SectionValidationError("supersede_pair returned unexpected section types")
    return SectionMutationResult(
        record=new_record,
        mutation_kind=MUTATION_KIND_SUPERSEDE,
        prior_record=old_record,
    )


def handle_add_training_record(
    command: AddTrainingRecord,
    uow: UnitOfWork,
) -> SectionMutationResult:
    _require_positive_person_id(command.person_id)
    _require_non_empty(command.training_kind, "training_kind")
    if command.training_kind not in TRAINING_KINDS:
        raise SectionValidationError(f"invalid training_kind: {command.training_kind!r}")

    candidate = TrainingRecord(
        person_id=command.person_id,
        training_kind=command.training_kind,
        employee_context_id=command.employee_context_id,
        title=command.title,
        organization_name=command.organization_name,
        hours=command.hours,
        started_at=command.started_at,
        completed_at=command.completed_at,
        certificate_number=command.certificate_number,
        document_date=command.document_date,
        metadata=dict(command.metadata) if command.metadata is not None else None,
    )
    _assert_no_duplicate_training(uow, person_id=command.person_id, candidate=candidate)
    inserted = uow.section_mutations().insert_record(candidate)
    if not isinstance(inserted, TrainingRecord):
        raise SectionValidationError("insert_record returned unexpected section type")
    return SectionMutationResult(record=inserted, mutation_kind=MUTATION_KIND_INSERT)


def handle_update_training_record(
    command: UpdateTrainingRecord,
    uow: UnitOfWork,
) -> SectionMutationResult:
    _require_positive_person_id(command.person_id)
    current = _require_active_training(uow, command.person_id, command.record_id)

    updated = replace(
        current,
        training_kind=command.training_kind if command.training_kind is not None else current.training_kind,
        title=command.title if command.title is not None else current.title,
        organization_name=(
            command.organization_name if command.organization_name is not None else current.organization_name
        ),
        hours=command.hours if command.hours is not None else current.hours,
        started_at=command.started_at if command.started_at is not None else current.started_at,
        completed_at=command.completed_at if command.completed_at is not None else current.completed_at,
        certificate_number=(
            command.certificate_number if command.certificate_number is not None else current.certificate_number
        ),
        document_date=command.document_date if command.document_date is not None else current.document_date,
        metadata=dict(command.metadata) if command.metadata is not None else current.metadata,
    )
    if updated.training_kind not in TRAINING_KINDS:
        raise SectionValidationError(f"invalid training_kind: {updated.training_kind!r}")

    _assert_no_duplicate_training(
        uow,
        person_id=command.person_id,
        candidate=updated,
        exclude_record_id=command.record_id,
    )
    persisted = uow.section_mutations().update_record(
        updated,
        expected_updated_at=command.expected_updated_at,
    )
    if not isinstance(persisted, TrainingRecord):
        raise SectionValidationError("update_record returned unexpected section type")
    return SectionMutationResult(record=persisted, mutation_kind=MUTATION_KIND_UPDATE)


def handle_void_training_record(
    command: VoidTrainingRecord,
    uow: UnitOfWork,
) -> SectionMutationResult:
    _require_positive_person_id(command.person_id)
    _require_non_empty(command.reason, "reason")
    _require_active_training(uow, command.person_id, command.record_id)
    voided = uow.section_mutations().void_record(
        command.person_id,
        SECTION_CODE_PPR_TRAINING,
        command.record_id,
        expected_updated_at=command.expected_updated_at,
    )
    if not isinstance(voided, TrainingRecord):
        raise SectionValidationError("void_record returned unexpected section type")
    return SectionMutationResult(record=voided, mutation_kind=MUTATION_KIND_VOID)


def handle_supersede_training_record(
    command: SupersedeTrainingRecord,
    uow: UnitOfWork,
) -> SectionMutationResult:
    _require_positive_person_id(command.person_id)
    _require_active_training(uow, command.person_id, command.record_id)
    if command.replacement.person_id != command.person_id:
        raise SectionValidationError("replacement.person_id must match supersede person_id")

    replacement = TrainingRecord(
        person_id=command.replacement.person_id,
        training_kind=command.replacement.training_kind,
        employee_context_id=command.replacement.employee_context_id,
        title=command.replacement.title,
        organization_name=command.replacement.organization_name,
        hours=command.replacement.hours,
        started_at=command.replacement.started_at,
        completed_at=command.replacement.completed_at,
        certificate_number=command.replacement.certificate_number,
        document_date=command.replacement.document_date,
        metadata=dict(command.replacement.metadata) if command.replacement.metadata is not None else None,
    )
    if replacement.training_kind not in TRAINING_KINDS:
        raise SectionValidationError(f"invalid training_kind: {replacement.training_kind!r}")
    _require_non_empty(replacement.training_kind, "training_kind")

    old_record, new_record = uow.section_mutations().supersede_pair(
        command.person_id,
        SECTION_CODE_PPR_TRAINING,
        command.record_id,
        replacement,
        expected_updated_at=command.expected_updated_at,
    )
    if not isinstance(old_record, TrainingRecord) or not isinstance(new_record, TrainingRecord):
        raise SectionValidationError("supersede_pair returned unexpected section types")
    return SectionMutationResult(
        record=new_record,
        mutation_kind=MUTATION_KIND_SUPERSEDE,
        prior_record=old_record,
    )


def _external_employment_from_add(command: AddExternalEmploymentRecord) -> ExternalEmploymentRecord:
    record = ExternalEmploymentRecord(
        person_id=command.person_id,
        record_kind=command.record_kind,
        employee_context_id=command.employee_context_id,
        employer_name=command.employer_name,
        department_name=command.department_name,
        position_title=command.position_title,
        employment_type=command.employment_type,
        started_at=command.started_at,
        ended_at=command.ended_at,
        termination_reason=command.termination_reason,
        document_reference=command.document_reference,
        source_system=command.source_system or EXTERNAL_EMPLOYMENT_SOURCE_MANUAL,
        source_id=command.source_id,
        provenance=dict(command.provenance) if command.provenance is not None else None,
        notes=command.notes,
        metadata=dict(command.metadata) if command.metadata is not None else None,
    )
    validate_external_employment_record(record)
    return record


def _require_active_external_employment(
    uow: UnitOfWork,
    person_id: int,
    record_id: int,
) -> ExternalEmploymentRecord:
    loaded = uow.sections.load_record(person_id, SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY, record_id)
    if loaded is None or not isinstance(loaded, ExternalEmploymentRecord):
        raise SectionRecordNotFoundError(
            f"External employment record not found: person_id={person_id}, record_id={record_id}"
        )
    if loaded.lifecycle_status != LIFECYCLE_STATUS_ACTIVE:
        raise SectionValidationError(
            f"External employment record {record_id} is not active (status={loaded.lifecycle_status!r})"
        )
    return loaded


def handle_add_external_employment_record(
    command: AddExternalEmploymentRecord,
    uow: UnitOfWork,
) -> SectionMutationResult:
    _require_positive_person_id(command.person_id)
    candidate = _external_employment_from_add(command)
    inserted = uow.section_mutations().insert_record(candidate)
    if not isinstance(inserted, ExternalEmploymentRecord):
        raise SectionValidationError("insert_record returned unexpected section type")
    return SectionMutationResult(record=inserted, mutation_kind=MUTATION_KIND_INSERT)


def handle_void_external_employment_record(
    command: VoidExternalEmploymentRecord,
    uow: UnitOfWork,
) -> SectionMutationResult:
    _require_positive_person_id(command.person_id)
    _require_non_empty(command.reason, "reason")
    _require_active_external_employment(uow, command.person_id, command.record_id)
    voided = uow.section_mutations().void_record(
        command.person_id,
        SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY,
        command.record_id,
        expected_updated_at=command.expected_updated_at,
    )
    if not isinstance(voided, ExternalEmploymentRecord):
        raise SectionValidationError("void_record returned unexpected section type")
    return SectionMutationResult(record=voided, mutation_kind=MUTATION_KIND_VOID)


def handle_supersede_external_employment_record(
    command: SupersedeExternalEmploymentRecord,
    uow: UnitOfWork,
) -> SectionMutationResult:
    _require_positive_person_id(command.person_id)
    _require_active_external_employment(uow, command.person_id, command.record_id)
    if command.replacement.person_id != command.person_id:
        raise SectionValidationError("replacement.person_id must match supersede person_id")

    replacement = _external_employment_from_add(command.replacement)
    old_record, new_record = uow.section_mutations().supersede_pair(
        command.person_id,
        SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY,
        command.record_id,
        replacement,
        expected_updated_at=command.expected_updated_at,
    )
    if not isinstance(old_record, ExternalEmploymentRecord) or not isinstance(new_record, ExternalEmploymentRecord):
        raise SectionValidationError("supersede_pair returned unexpected section types")
    return SectionMutationResult(
        record=new_record,
        mutation_kind=MUTATION_KIND_SUPERSEDE,
        prior_record=old_record,
    )


def _military_service_from_create(command: CreateMilitaryServiceRecord) -> MilitaryServiceRecord:
    record = MilitaryServiceRecord(
        person_id=command.person_id,
        record_kind=command.record_kind,
        employee_context_id=command.employee_context_id,
        obligation_status=command.obligation_status,
        registration_category=command.registration_category,
        military_rank=command.military_rank,
        military_specialty_code=command.military_specialty_code,
        personnel_composition=command.personnel_composition,
        fitness_category=command.fitness_category,
        registration_status=command.registration_status,
        commissariat_name=command.commissariat_name,
        registered_at=command.registered_at,
        deregistered_at=command.deregistered_at,
        military_id_book_series=command.military_id_book_series,
        military_id_book_number=command.military_id_book_number,
        registration_certificate_series=command.registration_certificate_series,
        registration_certificate_number=command.registration_certificate_number,
        notes=command.notes,
        source_type=command.source_type or SECTION_SOURCE_TYPE_ENTERED,
        provenance=dict(command.provenance) if command.provenance is not None else None,
        metadata=dict(command.metadata) if command.metadata is not None else None,
    )
    validate_military_service_record(record)
    return record


def _require_active_military_service(
    uow: UnitOfWork,
    person_id: int,
    record_id: int,
) -> MilitaryServiceRecord:
    loaded = uow.sections.load_record(person_id, SECTION_CODE_PPR_MILITARY, record_id)
    if loaded is None or not isinstance(loaded, MilitaryServiceRecord):
        raise SectionRecordNotFoundError(
            f"Military service record not found: person_id={person_id}, record_id={record_id}"
        )
    if loaded.lifecycle_status != LIFECYCLE_STATUS_ACTIVE:
        raise SectionValidationError(
            f"Military service record {record_id} is not active (status={loaded.lifecycle_status!r})"
        )
    return loaded


def handle_create_military_service_record(
    command: CreateMilitaryServiceRecord,
    uow: UnitOfWork,
) -> SectionMutationResult:
    _require_positive_person_id(command.person_id)
    candidate = _military_service_from_create(command)
    inserted = uow.section_mutations().insert_record(candidate)
    if not isinstance(inserted, MilitaryServiceRecord):
        raise SectionValidationError("insert_record returned unexpected section type")
    return SectionMutationResult(record=inserted, mutation_kind=MUTATION_KIND_INSERT)


def handle_void_military_service_record(
    command: VoidMilitaryServiceRecord,
    uow: UnitOfWork,
) -> SectionMutationResult:
    _require_positive_person_id(command.person_id)
    _require_non_empty(command.reason, "reason")
    _require_active_military_service(uow, command.person_id, command.record_id)
    voided = uow.section_mutations().void_record(
        command.person_id,
        SECTION_CODE_PPR_MILITARY,
        command.record_id,
        expected_updated_at=command.expected_updated_at,
    )
    if not isinstance(voided, MilitaryServiceRecord):
        raise SectionValidationError("void_record returned unexpected section type")
    return SectionMutationResult(record=voided, mutation_kind=MUTATION_KIND_VOID)


def handle_supersede_military_service_record(
    command: SupersedeMilitaryServiceRecord,
    uow: UnitOfWork,
) -> SectionMutationResult:
    _require_positive_person_id(command.person_id)
    _require_active_military_service(uow, command.person_id, command.record_id)
    if command.replacement.person_id != command.person_id:
        raise SectionValidationError("replacement.person_id must match supersede person_id")

    replacement = _military_service_from_create(command.replacement)
    old_record, new_record = uow.section_mutations().supersede_pair(
        command.person_id,
        SECTION_CODE_PPR_MILITARY,
        command.record_id,
        replacement,
        expected_updated_at=command.expected_updated_at,
    )
    if not isinstance(old_record, MilitaryServiceRecord) or not isinstance(new_record, MilitaryServiceRecord):
        raise SectionValidationError("supersede_pair returned unexpected section types")
    return SectionMutationResult(
        record=new_record,
        mutation_kind=MUTATION_KIND_SUPERSEDE,
        prior_record=old_record,
    )
