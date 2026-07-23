"""Unit tests for intake additional payload section."""
from __future__ import annotations

from app.personnel_intake.application.intake_mapper import (
    map_academic_degree_records,
    map_academic_title_records,
    map_award_records,
    map_foreign_language_records,
)
from app.personnel_intake.application.intake_section_utils import is_intake_section_empty
from app.personnel_intake.domain.additional_profile import normalize_academic_degree_entry, normalize_additional_profile
from app.personnel_intake.domain.models import empty_intake_draft_payload


def test_empty_intake_draft_payload_includes_additional_defaults() -> None:
    payload = empty_intake_draft_payload()
    assert payload["additional"] == {
        "foreign_languages": [],
        "foreign_languages_none": False,
        "awards": [],
        "awards_none": False,
        "academic_degrees": [],
        "academic_degrees_none": False,
        "academic_titles": [],
        "academic_titles_none": False,
    }


def test_is_intake_section_empty_additional_respects_declared_none() -> None:
    payload = empty_intake_draft_payload()
    assert is_intake_section_empty("additional", payload) is True

    payload["additional"]["foreign_languages_none"] = True
    assert is_intake_section_empty("additional", payload) is True

    payload["additional"]["foreign_languages_none"] = False
    payload["additional"]["foreign_languages"] = [{"language": "English", "proficiency": "B2"}]
    assert is_intake_section_empty("additional", payload) is False


def test_intake_mapper_additional_records() -> None:
    languages = map_foreign_language_records([{"language": "English", "proficiency": "B2"}])
    awards = map_award_records(
        [
            {
                "category": "Медаль",
                "name": "Медаль «За доблестный труд»",
                "issued_by": "МЗ РК",
                "awarded_at": "2020-05-10",
                "document_number": "MD-1",
            }
        ]
    )
    degrees = map_academic_degree_records(
        [
            {
                "degree": "Доктор наук",
                "field_of_science": "Медицина",
                "completed_at": "2018-06-30",
                "document_number": "DN-1",
            }
        ]
    )
    titles = map_academic_title_records(
        [
            {
                "academic_title": "Профессор",
                "field_of_science": "Медицина",
                "completed_at": "2020-01-01",
                "document_number": "TITLE-1",
            }
        ]
    )

    assert languages[0]["language"] == "English"
    assert awards[0]["name"] == "Медаль «За доблестный труд»"
    assert awards[0]["document_number"] == "MD-1"
    assert degrees[0]["field_of_science"] == "Медицина"
    assert titles[0]["academic_title"] == "Профессор"
    assert titles[0]["document_number"] == "TITLE-1"


def test_normalize_academic_degree_legacy_label() -> None:
    normalized = normalize_academic_degree_entry(
        {
            "label": "Кандидат медицинских наук",
            "degree_type": "candidate_medical_sciences",
            "completed_at": "2018-06-30",
        }
    )
    assert normalized["degree_other"] == "Кандидат медицинских наук"
    assert normalized["field_of_science"] == "candidate_medical_sciences"


def test_normalize_additional_profile_roundtrip() -> None:
    profile = normalize_additional_profile(
        {
            "foreign_languages": [{"language": "Английский", "proficiency": "Средний (B1)"}],
            "awards": [
                {
                    "category": "Благодарность",
                    "name": "Благодарность Министерства здравоохранения",
                    "awarded_at": "2021-03-01",
                }
            ],
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
                    "completed_at": "2019-05-01",
                    "document_number": "TTL-1",
                }
            ],
        }
    )
    assert len(profile["foreign_languages"]) == 1
    assert profile["awards"][0]["name"] == "Благодарность Министерства здравоохранения"
    assert profile["academic_degrees"][0]["degree"] == "PhD"
    assert profile["academic_titles"][0]["academic_title"] == "Доцент"
