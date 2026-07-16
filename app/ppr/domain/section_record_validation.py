"""Domain validation for PPR section records (P4-001-A — no handlers)."""
from __future__ import annotations

from datetime import date

from app.db.models.personnel_migration import (
    EXTERNAL_EMPLOYMENT_LIFECYCLE_STATUSES,
    EXTERNAL_EMPLOYMENT_RECORD_KIND_ATTESTATION_NONE,
    EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
    EXTERNAL_EMPLOYMENT_RECORD_KIND_NARRATIVE_SUMMARY,
    EXTERNAL_EMPLOYMENT_RECORD_KINDS,
    EXTERNAL_EMPLOYMENT_SOURCE_SYSTEMS,
    EXTERNAL_EMPLOYMENT_TYPES,
    EXTERNAL_EMPLOYMENT_VERIFICATION_STATUSES,
    LIFECYCLE_STATUSES,
    RELATIONSHIP_TYPES,
    SECTION_SOURCE_TYPES,
    VERIFICATION_STATUSES,
)
from app.ppr.domain.errors import SectionValidationError
from app.ppr.domain.section_models import ExternalEmploymentRecord, RelativeRecord


def _require_positive_person_id(person_id: int) -> None:
    if person_id <= 0:
        raise SectionValidationError("person_id must be positive")


def _require_non_empty(value: str | None, field: str) -> None:
    if not value or not str(value).strip():
        raise SectionValidationError(f"{field} is required")


def _require_enum(value: str, field: str, allowed: tuple[str, ...]) -> None:
    if value not in allowed:
        raise SectionValidationError(f"{field} must be one of: {', '.join(allowed)}")


def validate_relative_record(record: RelativeRecord) -> None:
    """Validate RelativeRecord invariants (WP-PR-P4-001 §4.6 FAM-1…FAM-4)."""
    _require_positive_person_id(record.person_id)
    _require_non_empty(record.relationship_type, "relationship_type")
    _require_enum(record.relationship_type, "relationship_type", RELATIONSHIP_TYPES)
    _require_non_empty(record.full_name, "full_name")
    _require_enum(record.verification_status, "verification_status", VERIFICATION_STATUSES)
    _require_enum(record.lifecycle_status, "lifecycle_status", LIFECYCLE_STATUSES)
    _require_enum(record.source_type, "source_type", SECTION_SOURCE_TYPES)
    if record.birth_date is not None and record.birth_date > date.today():
        raise SectionValidationError("birth_date must not be in the future")


def validate_external_employment_record(record: ExternalEmploymentRecord) -> None:
    """Validate ExternalEmploymentRecord invariants (ADR-056 §12.1)."""
    _require_positive_person_id(record.person_id)
    _require_non_empty(record.record_kind, "record_kind")
    _require_enum(record.record_kind, "record_kind", EXTERNAL_EMPLOYMENT_RECORD_KINDS)
    _require_enum(record.verification_status, "verification_status", EXTERNAL_EMPLOYMENT_VERIFICATION_STATUSES)
    _require_enum(record.lifecycle_status, "lifecycle_status", EXTERNAL_EMPLOYMENT_LIFECYCLE_STATUSES)
    _require_enum(record.source_system, "source_system", EXTERNAL_EMPLOYMENT_SOURCE_SYSTEMS)
    if record.employment_type is not None:
        _require_enum(record.employment_type, "employment_type", EXTERNAL_EMPLOYMENT_TYPES)
    if record.started_at is not None and record.ended_at is not None and record.ended_at < record.started_at:
        raise SectionValidationError("ended_at must be on or after started_at")
    if record.record_kind == EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE:
        _require_non_empty(record.employer_name, "employer_name")
        _require_non_empty(record.position_title, "position_title")
        if record.started_at is None and (not record.notes or not str(record.notes).strip()):
            raise SectionValidationError(
                "episode requires started_at or notes explaining missing dates"
            )
    elif record.record_kind == EXTERNAL_EMPLOYMENT_RECORD_KIND_NARRATIVE_SUMMARY:
        _require_non_empty(record.notes, "notes")
    elif record.record_kind == EXTERNAL_EMPLOYMENT_RECORD_KIND_ATTESTATION_NONE:
        if record.employer_name and str(record.employer_name).strip():
            raise SectionValidationError("attestation_none must not include employer_name")
        if record.position_title and str(record.position_title).strip():
            raise SectionValidationError("attestation_none must not include position_title")
        if record.started_at is not None:
            raise SectionValidationError("attestation_none must not include started_at")
        if record.ended_at is not None:
            raise SectionValidationError("attestation_none must not include ended_at")
