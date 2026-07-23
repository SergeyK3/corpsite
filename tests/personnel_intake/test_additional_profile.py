"""Unit tests for canonical additional profile read/write."""
from __future__ import annotations

from app.personnel_intake.domain.additional_profile import (
    merge_additional_profiles,
    normalize_academic_degree_entry,
    normalize_academic_title_entry,
    normalize_additional_profile,
    normalize_award_entry,
)


def test_merge_additional_profiles_prefers_first_non_empty() -> None:
    canonical = normalize_additional_profile(
        {
            "foreign_languages": [{"language": "Английский", "proficiency": "Средний (B1)"}],
        }
    )
    intake = normalize_additional_profile(
        {
            "awards": [{"title": "Благодарность"}],
        }
    )
    merged = merge_additional_profiles(canonical, intake)
    assert merged["foreign_languages"][0]["language"] == "Английский"
    assert merged["awards"] == []


def test_normalize_award_splits_legacy_category_title() -> None:
    normalized = normalize_award_entry({"title": "Ведомственная награда"})
    assert normalized["category"] == "Ведомственная"
    assert normalized["name"] == ""

    exact = normalize_award_entry({"title": "Орден «Парасат»"})
    assert exact["category"] == ""
    assert exact["name"] == "Орден «Парасат»"


def test_normalize_award_structured_fields() -> None:
    normalized = normalize_award_entry(
        {
            "category": "Медаль",
            "name": "Медаль «За доблестный труд»",
            "issued_by": "МЗ РК",
            "awarded_at": "2020-05-10",
            "document_number": "MD-1",
        }
    )
    assert normalized["category"] == "Медаль"
    assert normalized["name"] == "Медаль «За доблестный труд»"
    assert normalized["document_number"] == "MD-1"


def test_normalize_academic_degree_structured_fields() -> None:
    normalized = normalize_academic_degree_entry(
        {
            "degree": "Доктор наук",
            "field_of_science": "Медицина",
            "completed_at": "2018-06-30",
            "document_number": "DOC-1",
        }
    )
    assert normalized["degree"] == "Доктор наук"
    assert normalized["field_of_science"] == "Медицина"
    assert normalized["document_number"] == "DOC-1"
    assert "academic_title" not in normalized


def test_normalize_academic_title_structured_fields() -> None:
    normalized = normalize_academic_title_entry(
        {
            "academic_title": "Профессор",
            "field_of_science": "Экономика",
            "completed_at": "2019-05-01",
            "document_number": "TITLE-1",
        }
    )
    assert normalized["academic_title"] == "Профессор"
    assert normalized["document_number"] == "TITLE-1"


def test_normalize_additional_profile_splits_legacy_combined_academic_row() -> None:
    profile = normalize_additional_profile(
        {
            "academic_degrees": [
                {
                    "degree": "PhD",
                    "field_of_science": "Экономика",
                    "academic_title": "Доцент",
                    "completed_at": "2019-05-01",
                    "document_number": "LEG-1",
                }
            ]
        }
    )
    assert len(profile["academic_degrees"]) == 1
    assert profile["academic_degrees"][0]["degree"] == "PhD"
    assert profile["academic_degrees"][0]["document_number"] == "LEG-1"
    assert len(profile["academic_titles"]) == 1
    assert profile["academic_titles"][0]["academic_title"] == "Доцент"
    assert profile["academic_titles"][0]["document_number"] == "LEG-1"


def test_normalize_additional_profile_keeps_independent_degree_and_title_dates() -> None:
    profile = normalize_additional_profile(
        {
            "academic_degrees": [
                {
                    "degree": "PhD",
                    "field_of_science": "Экономика",
                    "completed_at": "2018-06-30",
                    "document_number": "DEG-1",
                }
            ],
            "academic_titles": [
                {
                    "academic_title": "Доцент",
                    "field_of_science": "Экономика",
                    "completed_at": "2020-01-15",
                    "document_number": "TTL-2",
                }
            ],
        }
    )
    assert profile["academic_degrees"][0]["completed_at"] == "2018-06-30"
    assert profile["academic_degrees"][0]["document_number"] == "DEG-1"
    assert profile["academic_titles"][0]["completed_at"] == "2020-01-15"
    assert profile["academic_titles"][0]["document_number"] == "TTL-2"
