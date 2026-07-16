"""Domain validation for PPR section records (P4-001-A — no handlers)."""
from __future__ import annotations

from datetime import date

from app.db.models.personnel_migration import (
    LIFECYCLE_STATUSES,
    RELATIONSHIP_TYPES,
    SECTION_SOURCE_TYPES,
    VERIFICATION_STATUSES,
)
from app.ppr.domain.errors import SectionValidationError
from app.ppr.domain.section_models import RelativeRecord


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
