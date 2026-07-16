# tests/ppr/test_relative_record_validation.py
"""Unit tests for RelativeRecord domain validation (WP-PR-P4-001-A)."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.db.models.personnel_migration import (
    RELATIONSHIP_TYPE_FATHER,
    SECTION_SOURCE_TYPE_ENTERED,
)
from app.ppr.domain.errors import SectionValidationError
from app.ppr.domain.section_models import RelativeRecord
from app.ppr.domain.section_record_validation import validate_relative_record


def _valid_record(**overrides) -> RelativeRecord:
    base = {
        "person_id": 1,
        "relationship_type": RELATIONSHIP_TYPE_FATHER,
        "full_name": "Иванов Иван Иванович",
        "source_type": SECTION_SOURCE_TYPE_ENTERED,
    }
    base.update(overrides)
    return RelativeRecord(**base)


def test_validate_relative_record_accepts_valid_record() -> None:
    validate_relative_record(_valid_record())


def test_validate_relative_record_rejects_empty_full_name() -> None:
    with pytest.raises(SectionValidationError, match="full_name is required"):
        validate_relative_record(_valid_record(full_name="   "))


def test_validate_relative_record_rejects_unknown_relationship_type() -> None:
    with pytest.raises(SectionValidationError, match="relationship_type must be one of"):
        validate_relative_record(_valid_record(relationship_type="cousin"))


def test_validate_relative_record_rejects_future_birth_date() -> None:
    future = date.today() + timedelta(days=1)
    with pytest.raises(SectionValidationError, match="birth_date must not be in the future"):
        validate_relative_record(_valid_record(birth_date=future))


def test_validate_relative_record_rejects_non_positive_person_id() -> None:
    with pytest.raises(SectionValidationError, match="person_id must be positive"):
        validate_relative_record(_valid_record(person_id=0))
