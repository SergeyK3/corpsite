"""Unit tests for date normalization in profile overrides."""
from __future__ import annotations

import pytest

from app.services.hr_import_profile_override_service import (
    _normalize_date_value,
    is_year_only_date,
    prepare_profile_override_for_storage,
)


def test_normalize_year_to_default_date():
    assert _normalize_date_value("2018") == "01.01.2018"
    assert _normalize_date_value(" 2020 ") == "01.01.2020"


def test_normalize_keeps_full_dates():
    assert _normalize_date_value("15.03.2019") == "15.03.2019"
    assert _normalize_date_value("2021-05-10") == "2021-05-10"
    assert _normalize_date_value("постоянно") == "постоянно"


def test_is_year_only_date():
    assert is_year_only_date("01.01.2018") is True
    assert is_year_only_date("15.03.2018") is False
    assert is_year_only_date("2018") is False


def test_prepare_profile_override_normalizes_training_year_field():
    override = prepare_profile_override_for_storage(
        {
            "training": [
                {"title": "Курс", "organization": "Org", "year": "2023", "hours": 36},
            ],
        }
    )
    assert override["training"][0]["date"] == "01.01.2023"
    assert "year" not in override["training"][0]


def test_prepare_profile_override_normalizes_degree_list():
    override = prepare_profile_override_for_storage(
        {
            "degree": [
                {"label": "Кандидат медицинских наук", "date": "2015"},
            ],
        }
    )
    assert override["degree"][0]["label"] == "Кандидат медицинских наук"
    assert override["degree"][0]["date"] == "01.01.2015"


def test_prepare_profile_override_accepts_legacy_degree_string():
    override = prepare_profile_override_for_storage({"degree": "доктор медицинских наук"})
    assert override["degree"] == "доктор медицинских наук"


def test_prepare_profile_override_normalizes_education():
    override = prepare_profile_override_for_storage(
        {
            "education": [
                {
                    "institution": "КазНМУ",
                    "specialty": "Лечебное дело",
                    "date": "2010",
                    "record_type": "basic",
                },
            ],
        }
    )
    assert override["education"][0]["date"] == "01.01.2010"
    assert override["education"][0]["institution"] == "КазНМУ"


def test_prepare_profile_override_rejects_invalid_date():
    with pytest.raises(ValueError, match="training\\[1\\].date"):
        prepare_profile_override_for_storage(
            {
                "training": [
                    {"title": "Курс", "organization": "Org", "year": "не год", "hours": 36},
                ],
            }
        )
