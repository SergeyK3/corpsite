"""Unit tests for date normalization in profile overrides."""
from __future__ import annotations

import pytest

from app.services.hr_import_profile_override_service import (
    _normalize_date_value,
    is_year_only_date,
    prepare_profile_override_for_storage,
)


def test_normalize_preserves_year_only_values():
    assert _normalize_date_value("2018") == "2018"
    assert _normalize_date_value(" 2020 ") == "2020"


def test_normalize_keeps_full_dates():
    assert _normalize_date_value("15.03.2019") == "2019-03-15"
    assert _normalize_date_value("2021-05-10") == "2021-05-10"
    assert _normalize_date_value("постоянно") == "постоянно"


def test_is_year_only_date():
    assert is_year_only_date("01.01.2018") is True
    assert is_year_only_date("2018") is True
    assert is_year_only_date("15.03.2018") is False


def test_prepare_profile_override_accepts_full_training_date():
    override = prepare_profile_override_for_storage(
        {
            "training": [
                {"title": "Курс", "organization": "Org", "year": "15.03.2023", "hours": 36},
            ],
        }
    )
    assert override["training"][0]["date"] == "2023-03-15"
    assert "year" not in override["training"][0]


def test_prepare_profile_override_rejects_incomplete_training_date():
    with pytest.raises(ValueError, match="training\\[1\\]\\.date"):
        prepare_profile_override_for_storage(
            {
                "training": [
                    {"title": "Курс", "organization": "Org", "year": "2023", "hours": 36},
                ],
            }
        )


def test_prepare_profile_override_accepts_full_degree_date():
    override = prepare_profile_override_for_storage(
        {
            "degree": [
                {"label": "Кандидат медицинских наук", "date": "15.03.2015"},
            ],
        }
    )
    assert override["degree"][0]["label"] == "Кандидат медицинских наук"
    assert override["degree"][0]["date"] == "2015-03-15"


def test_prepare_profile_override_accepts_legacy_degree_string():
    override = prepare_profile_override_for_storage({"degree": "доктор медицинских наук"})
    assert override["degree"] == "доктор медицинских наук"


def test_prepare_profile_override_accepts_full_education_date():
    override = prepare_profile_override_for_storage(
        {
            "education": [
                {
                    "institution": "КазНМУ",
                    "specialty": "Лечебное дело",
                    "date": "30.06.2010",
                    "record_type": "basic",
                },
            ],
        }
    )
    assert override["education"][0]["date"] == "2010-06-30"
    assert override["education"][0]["institution"] == "КазНМУ"


def test_prepare_profile_override_rejects_invalid_date():
    with pytest.raises(ValueError, match="training\\[1\\]\\.date"):
        prepare_profile_override_for_storage(
            {
                "training": [
                    {"title": "Курс", "organization": "Org", "year": "не год", "hours": 36},
                ],
            }
        )
