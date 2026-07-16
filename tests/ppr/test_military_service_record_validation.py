# tests/ppr/test_military_service_record_validation.py
"""Unit tests for MilitaryServiceRecord domain validation (WP-PR-027)."""
from __future__ import annotations

from datetime import date

import pytest

from app.db.models.personnel_migration import (
    LIFECYCLE_STATUS_DRAFT,
    MILITARY_RECORD_KIND_NOT_APPLICABLE,
    MILITARY_RECORD_KIND_REGISTRATION,
    SECTION_SOURCE_TYPE_ENTERED,
)
from app.ppr.domain.errors import SectionValidationError
from app.ppr.domain.section_models import MilitaryServiceRecord
from app.ppr.domain.section_record_validation import validate_military_service_record


def _valid_registration(**overrides) -> MilitaryServiceRecord:
    base = {
        "person_id": 1,
        "record_kind": MILITARY_RECORD_KIND_REGISTRATION,
        "obligation_status": "liable",
        "registration_category": "II",
        "military_rank": "рядовой",
        "registration_status": "registered",
        "source_type": SECTION_SOURCE_TYPE_ENTERED,
    }
    base.update(overrides)
    return MilitaryServiceRecord(**base)


def test_validate_military_service_accepts_valid_registration() -> None:
    validate_military_service_record(_valid_registration())


def test_validate_military_service_accepts_registration_with_single_structured_field() -> None:
    validate_military_service_record(
        MilitaryServiceRecord(
            person_id=1,
            record_kind=MILITARY_RECORD_KIND_REGISTRATION,
            military_rank="рядовой",
            source_type=SECTION_SOURCE_TYPE_ENTERED,
        )
    )


def test_validate_military_service_accepts_not_applicable_with_notes() -> None:
    validate_military_service_record(
        MilitaryServiceRecord(
            person_id=1,
            record_kind=MILITARY_RECORD_KIND_NOT_APPLICABLE,
            notes="Не подлежит воинскому учёту",
            source_type=SECTION_SOURCE_TYPE_ENTERED,
        )
    )


def test_validate_military_service_rejects_registration_with_notes_only() -> None:
    with pytest.raises(SectionValidationError, match="at least one structured field"):
        validate_military_service_record(
            MilitaryServiceRecord(
                person_id=1,
                record_kind=MILITARY_RECORD_KIND_REGISTRATION,
                notes="Только примечание",
                source_type=SECTION_SOURCE_TYPE_ENTERED,
            )
        )


def test_validate_military_service_rejects_registration_without_structured_fields() -> None:
    with pytest.raises(SectionValidationError, match="at least one structured field"):
        validate_military_service_record(
            MilitaryServiceRecord(
                person_id=1,
                record_kind=MILITARY_RECORD_KIND_REGISTRATION,
                military_specialty_code="123456",
                commissariat_name="Военкомат",
                source_type=SECTION_SOURCE_TYPE_ENTERED,
            )
        )


def test_validate_military_service_rejects_not_applicable_with_obligation_status() -> None:
    with pytest.raises(SectionValidationError, match="not_applicable must not include obligation_status"):
        validate_military_service_record(
            MilitaryServiceRecord(
                person_id=1,
                record_kind=MILITARY_RECORD_KIND_NOT_APPLICABLE,
                obligation_status="liable",
                notes="Не подлежит",
                source_type=SECTION_SOURCE_TYPE_ENTERED,
            )
        )


def test_validate_military_service_rejects_not_applicable_with_document_number() -> None:
    with pytest.raises(
        SectionValidationError,
        match="not_applicable must not include military_id_book_number",
    ):
        validate_military_service_record(
            MilitaryServiceRecord(
                person_id=1,
                record_kind=MILITARY_RECORD_KIND_NOT_APPLICABLE,
                military_id_book_number="123456",
                notes="Не подлежит",
                source_type=SECTION_SOURCE_TYPE_ENTERED,
            )
        )


def test_validate_military_service_rejects_draft_lifecycle_status() -> None:
    with pytest.raises(SectionValidationError, match="lifecycle_status must be one of"):
        validate_military_service_record(_valid_registration(lifecycle_status=LIFECYCLE_STATUS_DRAFT))


def test_validate_military_service_rejects_inverted_date_range() -> None:
    with pytest.raises(SectionValidationError, match="deregistered_at must be on or after registered_at"):
        validate_military_service_record(
            _valid_registration(
                registered_at=date(2020, 1, 1),
                deregistered_at=date(2019, 1, 1),
            )
        )


def test_validate_military_service_rejects_non_positive_person_id() -> None:
    with pytest.raises(SectionValidationError, match="person_id must be positive"):
        validate_military_service_record(_valid_registration(person_id=0))
