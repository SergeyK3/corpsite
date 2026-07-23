"""Tests for document/category/certificate date validation."""
from __future__ import annotations

import pytest

from app.personnel_intake.domain.date_validation import (
    is_incomplete_document_date,
    normalize_document_date_for_storage,
    validate_document_date_field,
)
from app.services.hr_import_profile_override_service import prepare_profile_override_for_storage


def test_normalize_document_date_for_storage() -> None:
    assert normalize_document_date_for_storage("15.03.2018") == "2018-03-15"
    assert normalize_document_date_for_storage("2018") == "2018"
    assert normalize_document_date_for_storage("01.01.2018") == "01.01.2018"


def test_validate_document_date_field_rejects_year_only() -> None:
    errors: list[str] = []
    validate_document_date_field("2018", field="categories[0].date", errors=errors)
    assert errors == ["categories[0].date: Укажите полную дату в формате ДД.ММ.ГГГГ"]


def test_prepare_profile_override_rejects_incomplete_category_date() -> None:
    with pytest.raises(ValueError, match="categories\\[2\\]\\.date"):
        prepare_profile_override_for_storage(
            {
                "categories": [
                    {"category": "Первая", "date": "15.03.2018", "specialty": "Терапия"},
                    {"category": "Вторая", "date": "2018", "specialty": "Хирургия"},
                ],
            }
        )


def test_prepare_profile_override_accepts_full_certificate_dates() -> None:
    override = prepare_profile_override_for_storage(
        {
            "certificates": [
                {
                    "kind": "Удостоверение",
                    "topic": "Охрана труда",
                    "date": "15.03.2018",
                    "valid_until": "15.03.2023",
                    "hours": 36,
                    "link": "",
                },
            ],
        }
    )
    assert override["certificates"][0]["date"] == "2018-03-15"
    assert override["certificates"][0]["valid_until"] == "2023-03-15"
    assert is_incomplete_document_date("2018-03-15") is False


def test_prepare_profile_override_rejects_incomplete_education_training_degree_dates() -> None:
    with pytest.raises(ValueError, match="education\\[1\\]\\.date"):
        prepare_profile_override_for_storage(
            {
                "education": [
                    {"institution": "КазНМУ", "specialty": "Лечебное дело", "date": "2010", "record_type": "basic"},
                ],
            }
        )
    with pytest.raises(ValueError, match="training\\[1\\]\\.date"):
        prepare_profile_override_for_storage(
            {
                "training": [
                    {"title": "Курс", "organization": "Org", "date": "2020", "hours": 36},
                ],
            }
        )
    with pytest.raises(ValueError, match="degree\\[1\\]\\.date"):
        prepare_profile_override_for_storage(
            {
                "degree": [
                    {"label": "Кандидат медицинских наук", "date": "2015"},
                ],
            }
        )
