# tests/ppr/test_external_employment_record_validation.py
"""Unit tests for ExternalEmploymentRecord domain validation (WP-PR-013)."""
from __future__ import annotations

from datetime import date

import pytest

from app.db.models.personnel_migration import (
    EXTERNAL_EMPLOYMENT_RECORD_KIND_ATTESTATION_NONE,
    EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
    EXTERNAL_EMPLOYMENT_RECORD_KIND_NARRATIVE_SUMMARY,
    EXTERNAL_EMPLOYMENT_SOURCE_MANUAL,
    LIFECYCLE_STATUS_DRAFT,
)
from app.ppr.domain.errors import SectionValidationError
from app.ppr.domain.section_models import ExternalEmploymentRecord
from app.ppr.domain.section_record_validation import validate_external_employment_record


def _valid_episode(**overrides) -> ExternalEmploymentRecord:
    base = {
        "person_id": 1,
        "record_kind": EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
        "employer_name": "ТОО «Пример»",
        "position_title": "Инженер",
        "started_at": date(2018, 1, 1),
        "source_system": EXTERNAL_EMPLOYMENT_SOURCE_MANUAL,
    }
    base.update(overrides)
    return ExternalEmploymentRecord(**base)


def test_validate_external_employment_accepts_valid_episode() -> None:
    validate_external_employment_record(_valid_episode())


def test_validate_external_employment_accepts_episode_with_notes_instead_of_started_at() -> None:
    validate_external_employment_record(
        _valid_episode(
            started_at=None,
            notes="Даты уточняются по трудовой книжке",
        )
    )


def test_validate_external_employment_accepts_narrative_summary() -> None:
    validate_external_employment_record(
        ExternalEmploymentRecord(
            person_id=1,
            record_kind=EXTERNAL_EMPLOYMENT_RECORD_KIND_NARRATIVE_SUMMARY,
            notes="Сводный стаж до поступления в ММЦ",
            source_system=EXTERNAL_EMPLOYMENT_SOURCE_MANUAL,
        )
    )


def test_validate_external_employment_accepts_attestation_none() -> None:
    validate_external_employment_record(
        ExternalEmploymentRecord(
            person_id=1,
            record_kind=EXTERNAL_EMPLOYMENT_RECORD_KIND_ATTESTATION_NONE,
            notes="Стаж отсутствует",
            source_system=EXTERNAL_EMPLOYMENT_SOURCE_MANUAL,
        )
    )


def test_validate_external_employment_accepts_attestation_none_without_employer_position_dates() -> None:
    validate_external_employment_record(
        ExternalEmploymentRecord(
            person_id=1,
            record_kind=EXTERNAL_EMPLOYMENT_RECORD_KIND_ATTESTATION_NONE,
            employer_name=None,
            position_title=None,
            started_at=None,
            ended_at=None,
            notes="Стаж отсутствует",
            source_system=EXTERNAL_EMPLOYMENT_SOURCE_MANUAL,
        )
    )


def test_validate_external_employment_rejects_narrative_summary_without_notes() -> None:
    with pytest.raises(SectionValidationError, match="notes is required"):
        validate_external_employment_record(
            ExternalEmploymentRecord(
                person_id=1,
                record_kind=EXTERNAL_EMPLOYMENT_RECORD_KIND_NARRATIVE_SUMMARY,
                notes=None,
                source_system=EXTERNAL_EMPLOYMENT_SOURCE_MANUAL,
            )
        )


def test_validate_external_employment_rejects_draft_lifecycle_status() -> None:
    with pytest.raises(SectionValidationError, match="lifecycle_status must be one of"):
        validate_external_employment_record(_valid_episode(lifecycle_status=LIFECYCLE_STATUS_DRAFT))


def test_validate_external_employment_rejects_episode_without_employer_name() -> None:
    with pytest.raises(SectionValidationError, match="employer_name is required"):
        validate_external_employment_record(_valid_episode(employer_name="   "))


def test_validate_external_employment_rejects_episode_without_position_title() -> None:
    with pytest.raises(SectionValidationError, match="position_title is required"):
        validate_external_employment_record(_valid_episode(position_title=""))


def test_validate_external_employment_rejects_episode_without_dates_or_notes() -> None:
    with pytest.raises(SectionValidationError, match="started_at or notes"):
        validate_external_employment_record(_valid_episode(started_at=None, notes=None))


def test_validate_external_employment_rejects_inverted_date_range() -> None:
    with pytest.raises(SectionValidationError, match="ended_at must be on or after started_at"):
        validate_external_employment_record(
            _valid_episode(started_at=date(2020, 1, 1), ended_at=date(2019, 1, 1))
        )


def test_validate_external_employment_rejects_non_positive_person_id() -> None:
    with pytest.raises(SectionValidationError, match="person_id must be positive"):
        validate_external_employment_record(_valid_episode(person_id=0))
