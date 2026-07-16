"""SQLAlchemy adapters for section read/mutation repositories."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping

from app.db.models.personnel_migration import (
    EXTERNAL_EMPLOYMENT_SOURCE_MANUAL,
    LIFECYCLE_STATUS_ACTIVE,
    LIFECYCLE_STATUS_SUPERSEDED,
    LIFECYCLE_STATUS_VOIDED,
    VERIFICATION_STATUS_PENDING,
)
from app.ppr.domain.errors import (
    SectionOptimisticConcurrencyConflictError,
    SectionRecordNotFoundError,
    SectionValidationError,
    UnknownSectionTypeError,
)
from app.ppr.domain.section_models import (
    SECTION_CODE_PPR_EDUCATION,
    SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY,
    SECTION_CODE_PPR_FAMILY,
    SECTION_CODE_PPR_TRAINING,
    SECTION_OPTIMISTIC_TOKEN_FIELD,
    EducationRecord,
    ExternalEmploymentRecord,
    RelativeRecord,
    SectionRecord,
    TrainingRecord,
)

_SECTION_SPECS: dict[str, dict[str, str]] = {
    SECTION_CODE_PPR_EDUCATION: {
        "table": "person_education",
        "id_col": "education_id",
    },
    SECTION_CODE_PPR_TRAINING: {
        "table": "person_training",
        "id_col": "training_id",
    },
    SECTION_CODE_PPR_FAMILY: {
        "table": "person_relatives",
        "id_col": "relative_id",
    },
    SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY: {
        "table": "person_external_employment",
        "id_col": "employment_id",
    },
}

_EDUCATION_SELECT = """
    education_id,
    person_id,
    employee_context_id,
    education_kind,
    institution_type,
    institution_name,
    specialty,
    qualification,
    started_at,
    completed_at,
    diploma_number,
    document_date,
    verification_status,
    lifecycle_status,
    created_at,
    updated_at,
    metadata
"""

_TRAINING_SELECT = """
    training_id,
    person_id,
    employee_context_id,
    training_kind,
    title,
    organization_name,
    hours,
    started_at,
    completed_at,
    certificate_number,
    document_date,
    verification_status,
    lifecycle_status,
    created_at,
    updated_at,
    metadata
"""

_RELATIVE_SELECT = """
    relative_id,
    person_id,
    relationship_type,
    full_name,
    birth_date,
    birth_place,
    organization_name,
    residence_address,
    notes,
    verification_status,
    lifecycle_status,
    source_type,
    created_at,
    updated_at,
    metadata
"""

_EXTERNAL_EMPLOYMENT_SELECT = """
    employment_id,
    person_id,
    record_kind,
    employer_name,
    department_name,
    position_title,
    employment_type,
    started_at,
    ended_at,
    termination_reason,
    document_reference,
    source_system,
    source_id,
    provenance,
    verification_status,
    lifecycle_status,
    notes,
    employee_context_id,
    created_at,
    updated_at,
    metadata
"""

_SECTION_SELECTS: dict[str, str] = {
    SECTION_CODE_PPR_EDUCATION: _EDUCATION_SELECT,
    SECTION_CODE_PPR_TRAINING: _TRAINING_SELECT,
    SECTION_CODE_PPR_FAMILY: _RELATIVE_SELECT,
    SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY: _EXTERNAL_EMPLOYMENT_SELECT,
}


def _metadata_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    return dict(value)


def _metadata_json(value: Any) -> str:
    return json.dumps(_metadata_dict(value), ensure_ascii=False)


def _resolve_section(section_code: str) -> dict[str, str]:
    spec = _SECTION_SPECS.get(section_code)
    if spec is None:
        raise UnknownSectionTypeError(f"Unsupported section_code: {section_code!r}")
    return spec


def _mapping_to_education(row: RowMapping) -> EducationRecord:
    return EducationRecord(
        record_id=int(row["education_id"]),
        person_id=int(row["person_id"]),
        employee_context_id=row.get("employee_context_id"),
        education_kind=str(row["education_kind"]),
        institution_type=row.get("institution_type"),
        institution_name=row.get("institution_name"),
        specialty=row.get("specialty"),
        qualification=row.get("qualification"),
        started_at=row.get("started_at"),
        completed_at=row.get("completed_at"),
        diploma_number=row.get("diploma_number"),
        document_date=row.get("document_date"),
        verification_status=str(row["verification_status"]),
        lifecycle_status=str(row["lifecycle_status"]),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
        metadata=_metadata_dict(row.get("metadata")),
    )


def _mapping_to_training(row: RowMapping) -> TrainingRecord:
    return TrainingRecord(
        record_id=int(row["training_id"]),
        person_id=int(row["person_id"]),
        employee_context_id=row.get("employee_context_id"),
        training_kind=str(row["training_kind"]),
        title=row.get("title"),
        organization_name=row.get("organization_name"),
        hours=row.get("hours"),
        started_at=row.get("started_at"),
        completed_at=row.get("completed_at"),
        certificate_number=row.get("certificate_number"),
        document_date=row.get("document_date"),
        verification_status=str(row["verification_status"]),
        lifecycle_status=str(row["lifecycle_status"]),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
        metadata=_metadata_dict(row.get("metadata")),
    )


def _mapping_to_relative(row: RowMapping) -> RelativeRecord:
    return RelativeRecord(
        record_id=int(row["relative_id"]),
        person_id=int(row["person_id"]),
        relationship_type=str(row["relationship_type"]),
        full_name=str(row["full_name"]),
        birth_date=row.get("birth_date"),
        birth_place=row.get("birth_place"),
        organization_name=row.get("organization_name"),
        residence_address=row.get("residence_address"),
        notes=row.get("notes"),
        verification_status=str(row["verification_status"]),
        lifecycle_status=str(row["lifecycle_status"]),
        source_type=str(row["source_type"]),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
        metadata=_metadata_dict(row.get("metadata")),
    )


def _mapping_to_external_employment(row: RowMapping) -> ExternalEmploymentRecord:
    return ExternalEmploymentRecord(
        record_id=int(row["employment_id"]),
        person_id=int(row["person_id"]),
        record_kind=str(row["record_kind"]),
        employer_name=row.get("employer_name"),
        department_name=row.get("department_name"),
        position_title=row.get("position_title"),
        employment_type=row.get("employment_type"),
        started_at=row.get("started_at"),
        ended_at=row.get("ended_at"),
        termination_reason=row.get("termination_reason"),
        document_reference=row.get("document_reference"),
        source_system=str(row["source_system"]),
        source_id=row.get("source_id"),
        provenance=_metadata_dict(row.get("provenance")),
        verification_status=str(row["verification_status"]),
        lifecycle_status=str(row["lifecycle_status"]),
        notes=row.get("notes"),
        employee_context_id=row.get("employee_context_id"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
        metadata=_metadata_dict(row.get("metadata")),
    )


def _row_to_record(section_code: str, row: RowMapping) -> SectionRecord:
    if section_code == SECTION_CODE_PPR_EDUCATION:
        return _mapping_to_education(row)
    if section_code == SECTION_CODE_PPR_TRAINING:
        return _mapping_to_training(row)
    if section_code == SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY:
        return _mapping_to_external_employment(row)
    return _mapping_to_relative(row)


def _select_cols(section_code: str) -> str:
    return _SECTION_SELECTS[section_code]


class _SectionStore:
    """Internal persistence primitives shared by read and mutation adapters."""

    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def load_active_records(self, person_id: int, section_code: str) -> tuple[SectionRecord, ...]:
        spec = _resolve_section(section_code)
        select_cols = _select_cols(section_code)
        rows = (
            self._conn.execute(
                text(
                    f"""
                    SELECT {select_cols}
                    FROM public.{spec['table']}
                    WHERE person_id = :person_id
                      AND lifecycle_status = :lifecycle_status
                    ORDER BY {spec['id_col']} ASC
                    """
                ),
                {
                    "person_id": int(person_id),
                    "lifecycle_status": LIFECYCLE_STATUS_ACTIVE,
                },
            )
            .mappings()
            .all()
        )
        return tuple(_row_to_record(section_code, row) for row in rows)

    def load_record(
        self,
        person_id: int,
        section_code: str,
        record_id: int,
    ) -> SectionRecord | None:
        spec = _resolve_section(section_code)
        select_cols = _select_cols(section_code)
        row = (
            self._conn.execute(
                text(
                    f"""
                    SELECT {select_cols}
                    FROM public.{spec['table']}
                    WHERE {spec['id_col']} = :record_id
                      AND person_id = :person_id
                    """
                ),
                {"record_id": int(record_id), "person_id": int(person_id)},
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        return _row_to_record(section_code, row)

    def insert_record(self, record: SectionRecord) -> SectionRecord:
        if isinstance(record, EducationRecord):
            return self._insert_education(record)
        if isinstance(record, TrainingRecord):
            return self._insert_training(record)
        if isinstance(record, RelativeRecord):
            return self._insert_relative(record)
        if isinstance(record, ExternalEmploymentRecord):
            return self._insert_external_employment(record)
        raise SectionValidationError(f"Unsupported section record type: {type(record)!r}")

    def update_record(
        self,
        record: SectionRecord,
        *,
        expected_updated_at: datetime,
    ) -> SectionRecord:
        if isinstance(record, EducationRecord):
            return self._update_education(record, expected_updated_at=expected_updated_at)
        if isinstance(record, TrainingRecord):
            return self._update_training(record, expected_updated_at=expected_updated_at)
        if isinstance(record, RelativeRecord):
            return self._update_relative(record, expected_updated_at=expected_updated_at)
        if isinstance(record, ExternalEmploymentRecord):
            return self._update_external_employment(record, expected_updated_at=expected_updated_at)
        raise SectionValidationError(f"Unsupported section record type: {type(record)!r}")

    def void_record(
        self,
        person_id: int,
        section_code: str,
        record_id: int,
        *,
        expected_updated_at: datetime,
    ) -> SectionRecord:
        spec = _resolve_section(section_code)
        result = self._conn.execute(
            text(
                f"""
                UPDATE public.{spec['table']}
                SET lifecycle_status = :voided_status,
                    updated_at = now()
                WHERE {spec['id_col']} = :record_id
                  AND person_id = :person_id
                  AND lifecycle_status = :active_status
                  AND updated_at = :expected_updated_at
                """
            ),
            {
                "voided_status": LIFECYCLE_STATUS_VOIDED,
                "record_id": int(record_id),
                "person_id": int(person_id),
                "active_status": LIFECYCLE_STATUS_ACTIVE,
                "expected_updated_at": expected_updated_at,
            },
        )
        if result.rowcount == 1:
            loaded = self.load_record(person_id, section_code, record_id)
            if loaded is None:
                raise SectionRecordNotFoundError(
                    f"Section record missing after void: person_id={person_id}, record_id={record_id}"
                )
            return loaded
        existing = self.load_record(person_id, section_code, record_id)
        if existing is None:
            raise SectionRecordNotFoundError(
                f"Active section record not found for void: "
                f"section_code={section_code}, person_id={person_id}, record_id={record_id}"
            )
        raise SectionOptimisticConcurrencyConflictError(
            f"Stale {SECTION_OPTIMISTIC_TOKEN_FIELD} for void record_id={record_id}"
        )

    def supersede_pair(
        self,
        person_id: int,
        section_code: str,
        old_record_id: int,
        new_record: SectionRecord,
        *,
        expected_updated_at: datetime,
    ) -> tuple[SectionRecord, SectionRecord]:
        spec = _resolve_section(section_code)
        result = self._conn.execute(
            text(
                f"""
                UPDATE public.{spec['table']}
                SET lifecycle_status = :superseded_status,
                    updated_at = now()
                WHERE {spec['id_col']} = :record_id
                  AND person_id = :person_id
                  AND lifecycle_status = :active_status
                  AND updated_at = :expected_updated_at
                """
            ),
            {
                "superseded_status": LIFECYCLE_STATUS_SUPERSEDED,
                "record_id": int(old_record_id),
                "person_id": int(person_id),
                "active_status": LIFECYCLE_STATUS_ACTIVE,
                "expected_updated_at": expected_updated_at,
            },
        )
        if result.rowcount != 1:
            existing = self.load_record(person_id, section_code, old_record_id)
            if existing is None:
                raise SectionRecordNotFoundError(
                    f"Active section record not found for supersede: "
                    f"section_code={section_code}, person_id={person_id}, record_id={old_record_id}"
                )
            raise SectionOptimisticConcurrencyConflictError(
                f"Stale {SECTION_OPTIMISTIC_TOKEN_FIELD} for supersede record_id={old_record_id}"
            )
        if new_record.person_id != person_id:
            raise SectionValidationError("new_record.person_id must match supersede person_id")
        inserted = self.insert_record(new_record)
        old_loaded = self.load_record(person_id, section_code, old_record_id)
        if old_loaded is None:
            raise SectionRecordNotFoundError(
                f"Superseded record missing after update: record_id={old_record_id}"
            )
        return old_loaded, inserted

    def _insert_education(self, record: EducationRecord) -> EducationRecord:
        row = self._conn.execute(
            text(
                f"""
                INSERT INTO public.person_education (
                    person_id,
                    employee_context_id,
                    education_kind,
                    institution_type,
                    institution_name,
                    specialty,
                    qualification,
                    started_at,
                    completed_at,
                    diploma_number,
                    document_date,
                    verification_status,
                    lifecycle_status,
                    metadata
                )
                VALUES (
                    :person_id,
                    :employee_context_id,
                    :education_kind,
                    :institution_type,
                    :institution_name,
                    :specialty,
                    :qualification,
                    :started_at,
                    :completed_at,
                    :diploma_number,
                    :document_date,
                    :verification_status,
                    :lifecycle_status,
                    CAST(:metadata AS jsonb)
                )
                RETURNING {_EDUCATION_SELECT}
                """
            ),
            {
                "person_id": int(record.person_id),
                "employee_context_id": record.employee_context_id,
                "education_kind": record.education_kind,
                "institution_type": record.institution_type,
                "institution_name": record.institution_name,
                "specialty": record.specialty,
                "qualification": record.qualification,
                "started_at": record.started_at,
                "completed_at": record.completed_at,
                "diploma_number": record.diploma_number,
                "document_date": record.document_date,
                "verification_status": record.verification_status or VERIFICATION_STATUS_PENDING,
                "lifecycle_status": record.lifecycle_status or LIFECYCLE_STATUS_ACTIVE,
                "metadata": _metadata_json(record.metadata),
            },
        ).mappings().one()
        return _mapping_to_education(row)

    def _insert_training(self, record: TrainingRecord) -> TrainingRecord:
        row = self._conn.execute(
            text(
                f"""
                INSERT INTO public.person_training (
                    person_id,
                    employee_context_id,
                    training_kind,
                    title,
                    organization_name,
                    hours,
                    started_at,
                    completed_at,
                    certificate_number,
                    document_date,
                    verification_status,
                    lifecycle_status,
                    metadata
                )
                VALUES (
                    :person_id,
                    :employee_context_id,
                    :training_kind,
                    :title,
                    :organization_name,
                    :hours,
                    :started_at,
                    :completed_at,
                    :certificate_number,
                    :document_date,
                    :verification_status,
                    :lifecycle_status,
                    CAST(:metadata AS jsonb)
                )
                RETURNING {_TRAINING_SELECT}
                """
            ),
            {
                "person_id": int(record.person_id),
                "employee_context_id": record.employee_context_id,
                "training_kind": record.training_kind,
                "title": record.title,
                "organization_name": record.organization_name,
                "hours": record.hours,
                "started_at": record.started_at,
                "completed_at": record.completed_at,
                "certificate_number": record.certificate_number,
                "document_date": record.document_date,
                "verification_status": record.verification_status or VERIFICATION_STATUS_PENDING,
                "lifecycle_status": record.lifecycle_status or LIFECYCLE_STATUS_ACTIVE,
                "metadata": _metadata_json(record.metadata),
            },
        ).mappings().one()
        return _mapping_to_training(row)

    def _insert_relative(self, record: RelativeRecord) -> RelativeRecord:
        row = self._conn.execute(
            text(
                f"""
                INSERT INTO public.person_relatives (
                    person_id,
                    relationship_type,
                    full_name,
                    birth_date,
                    birth_place,
                    organization_name,
                    residence_address,
                    notes,
                    verification_status,
                    lifecycle_status,
                    source_type,
                    metadata
                )
                VALUES (
                    :person_id,
                    :relationship_type,
                    :full_name,
                    :birth_date,
                    :birth_place,
                    :organization_name,
                    :residence_address,
                    :notes,
                    :verification_status,
                    :lifecycle_status,
                    :source_type,
                    CAST(:metadata AS jsonb)
                )
                RETURNING {_RELATIVE_SELECT}
                """
            ),
            {
                "person_id": int(record.person_id),
                "relationship_type": record.relationship_type,
                "full_name": record.full_name,
                "birth_date": record.birth_date,
                "birth_place": record.birth_place,
                "organization_name": record.organization_name,
                "residence_address": record.residence_address,
                "notes": record.notes,
                "verification_status": record.verification_status or VERIFICATION_STATUS_PENDING,
                "lifecycle_status": record.lifecycle_status or LIFECYCLE_STATUS_ACTIVE,
                "source_type": record.source_type,
                "metadata": _metadata_json(record.metadata),
            },
        ).mappings().one()
        return _mapping_to_relative(row)

    def _insert_external_employment(self, record: ExternalEmploymentRecord) -> ExternalEmploymentRecord:
        row = self._conn.execute(
            text(
                f"""
                INSERT INTO public.person_external_employment (
                    person_id,
                    record_kind,
                    employer_name,
                    department_name,
                    position_title,
                    employment_type,
                    started_at,
                    ended_at,
                    termination_reason,
                    document_reference,
                    source_system,
                    source_id,
                    provenance,
                    verification_status,
                    lifecycle_status,
                    notes,
                    employee_context_id,
                    metadata
                )
                VALUES (
                    :person_id,
                    :record_kind,
                    :employer_name,
                    :department_name,
                    :position_title,
                    :employment_type,
                    :started_at,
                    :ended_at,
                    :termination_reason,
                    :document_reference,
                    :source_system,
                    :source_id,
                    CAST(:provenance AS jsonb),
                    :verification_status,
                    :lifecycle_status,
                    :notes,
                    :employee_context_id,
                    CAST(:metadata AS jsonb)
                )
                RETURNING {_EXTERNAL_EMPLOYMENT_SELECT}
                """
            ),
            {
                "person_id": int(record.person_id),
                "record_kind": record.record_kind,
                "employer_name": record.employer_name,
                "department_name": record.department_name,
                "position_title": record.position_title,
                "employment_type": record.employment_type,
                "started_at": record.started_at,
                "ended_at": record.ended_at,
                "termination_reason": record.termination_reason,
                "document_reference": record.document_reference,
                "source_system": record.source_system or EXTERNAL_EMPLOYMENT_SOURCE_MANUAL,
                "source_id": record.source_id,
                "provenance": _metadata_json(record.provenance),
                "verification_status": record.verification_status or VERIFICATION_STATUS_PENDING,
                "lifecycle_status": record.lifecycle_status or LIFECYCLE_STATUS_ACTIVE,
                "notes": record.notes,
                "employee_context_id": record.employee_context_id,
                "metadata": _metadata_json(record.metadata),
            },
        ).mappings().one()
        return _mapping_to_external_employment(row)

    def _update_education(
        self,
        record: EducationRecord,
        *,
        expected_updated_at: datetime,
    ) -> EducationRecord:
        if record.record_id is None:
            raise SectionValidationError("education record_id is required for update")
        result = self._conn.execute(
            text(
                f"""
                UPDATE public.person_education
                SET education_kind = :education_kind,
                    institution_type = :institution_type,
                    institution_name = :institution_name,
                    specialty = :specialty,
                    qualification = :qualification,
                    started_at = :started_at,
                    completed_at = :completed_at,
                    diploma_number = :diploma_number,
                    document_date = :document_date,
                    metadata = CAST(:metadata AS jsonb),
                    updated_at = now()
                WHERE education_id = :record_id
                  AND person_id = :person_id
                  AND lifecycle_status = :active_status
                  AND updated_at = :expected_updated_at
                """
            ),
            {
                "education_kind": record.education_kind,
                "institution_type": record.institution_type,
                "institution_name": record.institution_name,
                "specialty": record.specialty,
                "qualification": record.qualification,
                "started_at": record.started_at,
                "completed_at": record.completed_at,
                "diploma_number": record.diploma_number,
                "document_date": record.document_date,
                "metadata": _metadata_json(record.metadata),
                "record_id": int(record.record_id),
                "person_id": int(record.person_id),
                "active_status": LIFECYCLE_STATUS_ACTIVE,
                "expected_updated_at": expected_updated_at,
            },
        )
        if result.rowcount == 0:
            existing = self.load_record(record.person_id, SECTION_CODE_PPR_EDUCATION, record.record_id)
            if existing is None:
                raise SectionRecordNotFoundError(
                    f"Education record not found: record_id={record.record_id}"
                )
            raise SectionOptimisticConcurrencyConflictError(
                f"Stale {SECTION_OPTIMISTIC_TOKEN_FIELD} for education record_id={record.record_id}"
            )
        loaded = self.load_record(record.person_id, SECTION_CODE_PPR_EDUCATION, record.record_id)
        if loaded is None or not isinstance(loaded, EducationRecord):
            raise SectionRecordNotFoundError(
                f"Education record missing after update: record_id={record.record_id}"
            )
        return loaded

    def _update_training(
        self,
        record: TrainingRecord,
        *,
        expected_updated_at: datetime,
    ) -> TrainingRecord:
        if record.record_id is None:
            raise SectionValidationError("training record_id is required for update")
        result = self._conn.execute(
            text(
                f"""
                UPDATE public.person_training
                SET training_kind = :training_kind,
                    title = :title,
                    organization_name = :organization_name,
                    hours = :hours,
                    started_at = :started_at,
                    completed_at = :completed_at,
                    certificate_number = :certificate_number,
                    document_date = :document_date,
                    metadata = CAST(:metadata AS jsonb),
                    updated_at = now()
                WHERE training_id = :record_id
                  AND person_id = :person_id
                  AND lifecycle_status = :active_status
                  AND updated_at = :expected_updated_at
                """
            ),
            {
                "training_kind": record.training_kind,
                "title": record.title,
                "organization_name": record.organization_name,
                "hours": record.hours,
                "started_at": record.started_at,
                "completed_at": record.completed_at,
                "certificate_number": record.certificate_number,
                "document_date": record.document_date,
                "metadata": _metadata_json(record.metadata),
                "record_id": int(record.record_id),
                "person_id": int(record.person_id),
                "active_status": LIFECYCLE_STATUS_ACTIVE,
                "expected_updated_at": expected_updated_at,
            },
        )
        if result.rowcount == 0:
            existing = self.load_record(record.person_id, SECTION_CODE_PPR_TRAINING, record.record_id)
            if existing is None:
                raise SectionRecordNotFoundError(
                    f"Training record not found: record_id={record.record_id}"
                )
            raise SectionOptimisticConcurrencyConflictError(
                f"Stale {SECTION_OPTIMISTIC_TOKEN_FIELD} for training record_id={record.record_id}"
            )
        loaded = self.load_record(record.person_id, SECTION_CODE_PPR_TRAINING, record.record_id)
        if loaded is None or not isinstance(loaded, TrainingRecord):
            raise SectionRecordNotFoundError(
                f"Training record missing after update: record_id={record.record_id}"
            )
        return loaded

    def _update_relative(
        self,
        record: RelativeRecord,
        *,
        expected_updated_at: datetime,
    ) -> RelativeRecord:
        if record.record_id is None:
            raise SectionValidationError("relative record_id is required for update")
        result = self._conn.execute(
            text(
                f"""
                UPDATE public.person_relatives
                SET relationship_type = :relationship_type,
                    full_name = :full_name,
                    birth_date = :birth_date,
                    birth_place = :birth_place,
                    organization_name = :organization_name,
                    residence_address = :residence_address,
                    notes = :notes,
                    source_type = :source_type,
                    metadata = CAST(:metadata AS jsonb),
                    updated_at = now()
                WHERE relative_id = :record_id
                  AND person_id = :person_id
                  AND lifecycle_status = :active_status
                  AND updated_at = :expected_updated_at
                """
            ),
            {
                "relationship_type": record.relationship_type,
                "full_name": record.full_name,
                "birth_date": record.birth_date,
                "birth_place": record.birth_place,
                "organization_name": record.organization_name,
                "residence_address": record.residence_address,
                "notes": record.notes,
                "source_type": record.source_type,
                "metadata": _metadata_json(record.metadata),
                "record_id": int(record.record_id),
                "person_id": int(record.person_id),
                "active_status": LIFECYCLE_STATUS_ACTIVE,
                "expected_updated_at": expected_updated_at,
            },
        )
        if result.rowcount == 0:
            existing = self.load_record(record.person_id, SECTION_CODE_PPR_FAMILY, record.record_id)
            if existing is None:
                raise SectionRecordNotFoundError(
                    f"Relative record not found: record_id={record.record_id}"
                )
            raise SectionOptimisticConcurrencyConflictError(
                f"Stale {SECTION_OPTIMISTIC_TOKEN_FIELD} for relative record_id={record.record_id}"
            )
        loaded = self.load_record(record.person_id, SECTION_CODE_PPR_FAMILY, record.record_id)
        if loaded is None or not isinstance(loaded, RelativeRecord):
            raise SectionRecordNotFoundError(
                f"Relative record missing after update: record_id={record.record_id}"
            )
        return loaded

    def _update_external_employment(
        self,
        record: ExternalEmploymentRecord,
        *,
        expected_updated_at: datetime,
    ) -> ExternalEmploymentRecord:
        if record.record_id is None:
            raise SectionValidationError("external employment record_id is required for update")
        result = self._conn.execute(
            text(
                f"""
                UPDATE public.person_external_employment
                SET record_kind = :record_kind,
                    employer_name = :employer_name,
                    department_name = :department_name,
                    position_title = :position_title,
                    employment_type = :employment_type,
                    started_at = :started_at,
                    ended_at = :ended_at,
                    termination_reason = :termination_reason,
                    document_reference = :document_reference,
                    source_system = :source_system,
                    source_id = :source_id,
                    provenance = CAST(:provenance AS jsonb),
                    notes = :notes,
                    employee_context_id = :employee_context_id,
                    metadata = CAST(:metadata AS jsonb),
                    updated_at = now()
                WHERE employment_id = :record_id
                  AND person_id = :person_id
                  AND lifecycle_status = :active_status
                  AND updated_at = :expected_updated_at
                """
            ),
            {
                "record_kind": record.record_kind,
                "employer_name": record.employer_name,
                "department_name": record.department_name,
                "position_title": record.position_title,
                "employment_type": record.employment_type,
                "started_at": record.started_at,
                "ended_at": record.ended_at,
                "termination_reason": record.termination_reason,
                "document_reference": record.document_reference,
                "source_system": record.source_system,
                "source_id": record.source_id,
                "provenance": _metadata_json(record.provenance),
                "notes": record.notes,
                "employee_context_id": record.employee_context_id,
                "metadata": _metadata_json(record.metadata),
                "record_id": int(record.record_id),
                "person_id": int(record.person_id),
                "active_status": LIFECYCLE_STATUS_ACTIVE,
                "expected_updated_at": expected_updated_at,
            },
        )
        if result.rowcount == 0:
            existing = self.load_record(
                record.person_id,
                SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY,
                record.record_id,
            )
            if existing is None:
                raise SectionRecordNotFoundError(
                    f"External employment record not found: record_id={record.record_id}"
                )
            raise SectionOptimisticConcurrencyConflictError(
                f"Stale {SECTION_OPTIMISTIC_TOKEN_FIELD} for external employment record_id={record.record_id}"
            )
        loaded = self.load_record(
            record.person_id,
            SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY,
            record.record_id,
        )
        if loaded is None or not isinstance(loaded, ExternalEmploymentRecord):
            raise SectionRecordNotFoundError(
                f"External employment record missing after update: record_id={record.record_id}"
            )
        return loaded


class SqlAlchemySectionReadRepository:
    """Read-only section adapter — does not commit."""

    def __init__(self, conn: Connection) -> None:
        self._store = _SectionStore(conn)

    def load_active_records(self, person_id: int, section_code: str) -> tuple[SectionRecord, ...]:
        return self._store.load_active_records(person_id, section_code)

    def load_record(
        self,
        person_id: int,
        section_code: str,
        record_id: int,
    ) -> SectionRecord | None:
        return self._store.load_record(person_id, section_code, record_id)


class SqlAlchemySectionMutationRepository:
    """Mutation-only section adapter — use via SectionMutationContext in handlers."""

    def __init__(self, conn: Connection) -> None:
        self._store = _SectionStore(conn)

    def insert_record(self, record: SectionRecord) -> SectionRecord:
        return self._store.insert_record(record)

    def update_record(
        self,
        record: SectionRecord,
        *,
        expected_updated_at: datetime,
    ) -> SectionRecord:
        return self._store.update_record(record, expected_updated_at=expected_updated_at)

    def void_record(
        self,
        person_id: int,
        section_code: str,
        record_id: int,
        *,
        expected_updated_at: datetime,
    ) -> SectionRecord:
        return self._store.void_record(
            person_id,
            section_code,
            record_id,
            expected_updated_at=expected_updated_at,
        )

    def supersede_pair(
        self,
        person_id: int,
        section_code: str,
        old_record_id: int,
        new_record: SectionRecord,
        *,
        expected_updated_at: datetime,
    ) -> tuple[SectionRecord, SectionRecord]:
        return self._store.supersede_pair(
            person_id,
            section_code,
            old_record_id,
            new_record,
            expected_updated_at=expected_updated_at,
        )
