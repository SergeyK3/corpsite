"""Domain command handlers for PPR sections (R4 — no commit, events, or BC calls)."""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from app.db.models.personnel_migration import (
    EDUCATION_KINDS,
    LIFECYCLE_STATUS_ACTIVE,
    TRAINING_KINDS,
)
from app.ppr.domain.errors import (
    SectionDuplicateRecordError,
    SectionRecordNotFoundError,
    SectionValidationError,
)
from app.ppr.domain.section_commands import (
    AddEducationRecord,
    AddTrainingRecord,
    SupersedeEducationRecord,
    SupersedeTrainingRecord,
    UpdateEducationRecord,
    UpdateTrainingRecord,
    VoidEducationRecord,
    VoidTrainingRecord,
)
from app.ppr.domain.section_models import (
    MUTATION_KIND_INSERT,
    MUTATION_KIND_SUPERSEDE,
    MUTATION_KIND_UPDATE,
    MUTATION_KIND_VOID,
    SECTION_CODE_PPR_EDUCATION,
    SECTION_CODE_PPR_TRAINING,
    EducationRecord,
    SectionMutationResult,
    TrainingRecord,
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
    )
    if not isinstance(old_record, EducationRecord) or not isinstance(new_record, EducationRecord):
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
    )
    if not isinstance(old_record, TrainingRecord) or not isinstance(new_record, TrainingRecord):
        raise SectionValidationError("supersede_pair returned unexpected section types")
    return SectionMutationResult(
        record=new_record,
        mutation_kind=MUTATION_KIND_SUPERSEDE,
        prior_record=old_record,
    )
