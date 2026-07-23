"""Tests for intake draft date validation."""
from __future__ import annotations

import pytest

from app.personnel_intake.application.intake_mapper import parse_date_value
from app.personnel_intake.application.intake_service import _validate_submit_payload
from app.personnel_intake.domain.date_validation import (
    collect_intake_date_validation_errors,
    is_incomplete_intake_birth_date,
    is_incomplete_intake_period_date,
    is_valid_intake_full_date_iso,
)
from app.personnel_intake.domain.errors import PersonnelIntakeValidationError
from app.personnel_intake.domain.models import empty_intake_draft_payload


def test_is_valid_intake_full_date_iso() -> None:
    assert is_valid_intake_full_date_iso("1990-05-20") is True
    assert is_valid_intake_full_date_iso("2020-01-01") is True
    assert is_valid_intake_full_date_iso("2020-02-30") is False
    assert is_valid_intake_full_date_iso("2018") is False


def test_incomplete_period_dates() -> None:
    assert is_incomplete_intake_period_date("2018") is True
    assert is_incomplete_intake_period_date("2018-01-01") is True
    assert is_incomplete_intake_period_date("2018-09-15") is False
    assert is_incomplete_intake_period_date("") is False


def test_incomplete_birth_date_allows_january_first() -> None:
    assert is_incomplete_intake_birth_date("1990-01-01") is False
    assert is_incomplete_intake_birth_date("1990") is True


def test_collect_intake_date_validation_errors_training_period() -> None:
    payload = empty_intake_draft_payload()
    payload["training"] = [
        {
            "institution": "Центр",
            "course_name": "Охрана труда",
            "year_from": "2021-03-12",
            "year_to": "2021-03-10",
            "hours": "",
        }
    ]

    assert "training[0].year_from" in collect_intake_date_validation_errors(payload)


def test_collect_intake_date_validation_errors() -> None:
    payload = empty_intake_draft_payload()
    payload["personal"]["birth_date"] = "1990-05-20"
    payload["education"] = [
        {
            "education_type": "basic",
            "institution": "КазНУ",
            "year_from": "2014",
            "year_to": "2018-06-30",
            "specialty": "",
            "qualification": "",
            "diploma_number": "",
        }
    ]

    assert collect_intake_date_validation_errors(payload) == ["education[0].year_from"]


def test_validate_submit_payload_rejects_incomplete_dates() -> None:
    payload = empty_intake_draft_payload()
    payload["personal"]["last_name"] = "Петров"
    payload["personal"]["first_name"] = "Пётр"
    payload["contacts"]["mobile_phone"] = "+77005554433"
    payload["education"] = [
        {
            "education_type": "basic",
            "institution": "КазНУ",
            "year_from": "2014",
            "year_to": "2018-06-30",
            "specialty": "",
            "qualification": "",
            "diploma_number": "",
        }
    ]

    with pytest.raises(PersonnelIntakeValidationError, match="education\\[0\\]\\.year_from"):
        _validate_submit_payload(payload)


def test_parse_date_value_does_not_invent_january_first_for_year_only() -> None:
    assert parse_date_value("2018") is None
    assert parse_date_value("2018-09-15") is not None
    assert parse_date_value("2018-09-15").isoformat() == "2018-09-15"
