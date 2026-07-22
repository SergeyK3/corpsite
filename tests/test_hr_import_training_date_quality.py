"""Tests for ADR-059 training/education date quality checks."""
from __future__ import annotations

from app.services.hr_import_training_date_quality_service import (
    TRAINING_DATE_QUALITY_REMARK,
    assess_normalized_record_date_quality,
    assess_roster_training_raw_quality,
    is_incomplete_date_text,
    is_year_only_iso_date,
)


def test_is_year_only_iso_date() -> None:
    assert is_year_only_iso_date("2022-01-01") is True
    assert is_year_only_iso_date("2022-03-15") is False
    assert is_year_only_iso_date("2022") is False


def test_is_incomplete_date_text() -> None:
    assert is_incomplete_date_text("2022") is True
    assert is_incomplete_date_text("Резидентура 2025") is True
    assert is_incomplete_date_text("15.03.2018") is False
    assert is_incomplete_date_text("2018-03-15") is False


def test_assess_normalized_record_date_quality_year_only_issue_date() -> None:
    remarks = assess_normalized_record_date_quality(
        {
            "record_kind": "training",
            "title": "Курс",
            "issue_date": "2022-01-01",
        }
    )
    assert remarks == [TRAINING_DATE_QUALITY_REMARK]


def test_assess_normalized_record_date_quality_full_date_ok() -> None:
    remarks = assess_normalized_record_date_quality(
        {
            "record_kind": "education",
            "title": "Вуз",
            "issue_date": "2022-06-15",
            "source_text": "Медуниверситет 2022",
        }
    )
    assert remarks == []


def test_assess_normalized_record_date_quality_missing_education_dates() -> None:
    remarks = assess_normalized_record_date_quality(
        {
            "record_kind": "education",
            "title": "Семипалатинская государственная медицинская академия",
            "source_text": "2. Семипалатинская государственная медицинская академия",
        }
    )
    assert remarks == [TRAINING_DATE_QUALITY_REMARK]


def test_assess_roster_training_raw_quality() -> None:
    assert assess_roster_training_raw_quality(training_raw="2022", education_raw="") == [
        TRAINING_DATE_QUALITY_REMARK
    ]
    assert assess_roster_training_raw_quality(
        training_raw="",
        education_raw="Резидентура 2025",
    ) == [TRAINING_DATE_QUALITY_REMARK]
    assert assess_roster_training_raw_quality(
        training_raw="15.03.2020 — курс",
        education_raw="",
    ) == []
