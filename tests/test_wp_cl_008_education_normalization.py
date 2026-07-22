# tests/test_wp_cl_008_education_normalization.py
"""Unit tests for WP-CL-008 education normalization layer."""
from __future__ import annotations

import inspect
from datetime import datetime

import pytest

from app.control_list_import.domain.education_candidate import EducationReadinessStatus
from app.control_list_import.domain.models import (
    MappingProfileColumnSnapshot,
    MappingProfileSheetSnapshot,
    MappingProfileSnapshot,
)
from app.control_list_import.domain.person_match_models import MatchReason, MatchStatus, PersonMatchResult
from app.control_list_import.domain.staging_models import StagingCellInput, StagingRowInput
from app.control_list_import.domain.vocabulary import PARSER_CODE_RECORDS_EDUCATION, SEMANTIC_FIELD_EDUCATION_RECORDS
from app.control_list_import.education_normalization.records import (
    EDUCATION_SHARED_CONTEXT_ISSUE,
    is_technical_empty_education_cell,
    parse_education_fragment,
    split_education_fragments,
)
from app.control_list_import.education_normalization.service import EducationNormalizationService
from app.db.models.control_list_mapping import (
    EMPLOYMENT_MODE_PRIMARY,
    PERSONNEL_CATEGORY_DOCTOR,
    PROFILE_STATUS_ACTIVE,
    SHEET_PURPOSE_PERSONNEL_CONTROL_LIST,
)


def _education_column() -> MappingProfileColumnSnapshot:
    return MappingProfileColumnSnapshot(
        profile_column_id=1,
        profile_sheet_id=1,
        column_index=9,
        column_letter="I",
        raw_header="Образование",
        semantic_field=SEMANTIC_FIELD_EDUCATION_RECORDS,
        parser_code=PARSER_CODE_RECORDS_EDUCATION,
        is_required=False,
    )


def _profile() -> MappingProfileSnapshot:
    sheet = MappingProfileSheetSnapshot(
        profile_sheet_id=1,
        profile_id=10,
        sheet_name="врачи",
        personnel_category=PERSONNEL_CATEGORY_DOCTOR,
        employment_mode=EMPLOYMENT_MODE_PRIMARY,
        sheet_purpose=SHEET_PURPOSE_PERSONNEL_CONTROL_LIST,
        header_row_override=3,
        columns=[_education_column()],
    )
    return MappingProfileSnapshot(
        profile_id=10,
        profile_code="control_list_default",
        profile_version=1,
        profile_name="Default",
        description=None,
        status=PROFILE_STATUS_ACTIVE,
        created_at=datetime(2026, 7, 17, 12, 0, 0),
        created_by=1,
        updated_at=None,
        sheets=[sheet],
    )


def _row(*, education: str | None, row_id: int = 100) -> StagingRowInput:
    cells: list[StagingCellInput] = []
    if education is not None:
        cells.append(StagingCellInput(column_index=9, raw_value=education))
    return StagingRowInput(
        row_id=row_id,
        sheet_name="врачи",
        excel_row_number=5,
        row_kind="data",
        cells=tuple(cells),
    )


def _match_result(
    *,
    status: MatchStatus = MatchStatus.EXACT,
    recommended_person_id: int | None = 42,
    source_row_id: int = 100,
) -> PersonMatchResult:
    return PersonMatchResult(
        import_run_id=7,
        source_row_id=source_row_id,
        status=status,
        match_candidates=(),
        primary_reason=MatchReason.EXACT_IIN,
        reasons=(MatchReason.EXACT_IIN,),
        confidence=1.0,
        recommended_person_id=recommended_person_id,
    )


def test_single_education_record():
    candidates = EducationNormalizationService().normalize_row(
        row=_row(education="КазНМУ им. Асфendiyarov 2015"),
        profile=_profile(),
        person_match=_match_result(),
        import_run_id=7,
    )
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.graduation_year.value == 2015
    assert "КазНМУ" in (candidate.institution_name.text or "")
    assert candidate.readiness_status == EducationReadinessStatus.NORMALIZATION_READY


@pytest.mark.parametrize(
    "raw",
    [
        "КазНМУ 2010\nАстана Мед 2015",
        "КазНМУ 2010; Астана Мед 2015",
        "КазНМУ 2010 | Астана Мед 2015",
    ],
)
def test_multiple_records_via_delimiters(raw: str):
    candidates = EducationNormalizationService().normalize_row(
        row=_row(education=raw),
        profile=_profile(),
        person_match=_match_result(),
        import_run_id=7,
    )
    assert len(candidates) == 2
    assert candidates[0].source_fragment_index == 0
    assert candidates[1].source_fragment_index == 1
    assert candidates[0].graduation_year.value == 2010
    assert candidates[1].graduation_year.value == 2015


def test_commas_inside_record_do_not_split():
    raw = "КазНМУ им. Асфendiyarov, специальность «Лечебное дело», 2015"
    fragments = split_education_fragments(raw)
    assert len(fragments) == 1
    candidates = EducationNormalizationService().normalize_row(
        row=_row(education=raw),
        profile=_profile(),
        person_match=_match_result(),
        import_run_id=7,
    )
    assert len(candidates) == 1
    assert candidates[0].graduation_year.value == 2015
    assert "Лечебное дело" in (candidates[0].specialty.text or "")


def test_year_extraction():
    parsed = parse_education_fragment("Астана медицинский университет, 2018", fragment_index=0)
    assert parsed.graduation_year.value == 2018


def test_incomplete_fragment_kept_with_issue():
    candidates = EducationNormalizationService().normalize_row(
        row=_row(education="непонятная запись"),
        profile=_profile(),
        person_match=_match_result(),
        import_run_id=7,
    )
    assert len(candidates) == 1
    assert candidates[0].raw_fragment == "непонятная запись"
    assert "education_fragment_incomplete" in candidates[0].field_issues[SEMANTIC_FIELD_EDUCATION_RECORDS]
    assert candidates[0].readiness_status == EducationReadinessStatus.REVIEW_REQUIRED


@pytest.mark.parametrize("value", ["", "   ", "-", "н/д", "N/A"])
def test_empty_and_technical_empty_values(value: str):
    assert is_technical_empty_education_cell(value) or not value.strip()
    candidates = EducationNormalizationService().normalize_row(
        row=_row(education=value if value.strip() else value or None),
        profile=_profile(),
        person_match=_match_result(),
        import_run_id=7,
    )
    assert candidates == []


def test_matched_person_reaches_normalization_ready():
    candidates = EducationNormalizationService().normalize_row(
        row=_row(education="КазНМУ 2015"),
        profile=_profile(),
        person_match=_match_result(recommended_person_id=42),
        import_run_id=7,
    )
    assert len(candidates) == 1
    assert candidates[0].matched_person_id == 42
    assert candidates[0].is_normalization_ready


def test_unmatched_person_still_creates_candidates():
    candidates = EducationNormalizationService().normalize_row(
        row=_row(education="КазНМУ 2015"),
        profile=_profile(),
        person_match=_match_result(status=MatchStatus.NOT_FOUND, recommended_person_id=None),
        import_run_id=7,
    )
    assert len(candidates) == 1
    assert candidates[0].matched_person_id is None
    assert candidates[0].readiness_status == EducationReadinessStatus.PERSON_UNMATCHED


def test_ambiguous_match_requires_review():
    candidates = EducationNormalizationService().normalize_row(
        row=_row(education="КазНМУ 2015"),
        profile=_profile(),
        person_match=_match_result(status=MatchStatus.AMBIGUOUS, recommended_person_id=None),
        import_run_id=7,
    )
    assert len(candidates) == 1
    assert candidates[0].readiness_status == EducationReadinessStatus.REVIEW_REQUIRED


def test_invalid_person_match_status():
    candidates = EducationNormalizationService().normalize_row(
        row=_row(education="КазНМУ 2015"),
        profile=_profile(),
        person_match=_match_result(status=MatchStatus.INVALID, recommended_person_id=None),
        import_run_id=7,
    )
    assert len(candidates) == 1
    assert candidates[0].readiness_status == EducationReadinessStatus.PERSON_MATCH_INVALID


def test_provenance_per_fragment():
    raw = "КазНМУ 2010\nАстана Мед 2015"
    candidates = EducationNormalizationService().normalize_row(
        row=_row(education=raw, row_id=555),
        profile=_profile(),
        person_match=_match_result(source_row_id=555),
        import_run_id=99,
    )
    assert len(candidates) == 2
    for index, candidate in enumerate(candidates):
        assert candidate.import_run_id == 99
        assert candidate.source_row_id == 555
        assert candidate.source_sheet_name == "врачи"
        assert candidate.source_excel_row_number == 5
        assert candidate.source_column_index == 9
        assert candidate.source_column_letter == "I"
        assert candidate.source_fragment_index == index
        assert candidate.raw_fragment in raw
        assert candidate.profile_code == "control_list_default"


def test_normalization_ready_does_not_authorize_ppr_education_apply():
    candidates = EducationNormalizationService().normalize_row(
        row=_row(education="КазНМУ 2015"),
        profile=_profile(),
        person_match=_match_result(recommended_person_id=42),
        import_run_id=7,
    )
    candidate = candidates[0]
    assert candidate.is_normalization_ready
    assert type(candidate).__name__ == "EducationCandidate"
    assert not hasattr(candidate, "employee_id")
    assert not hasattr(candidate, "person_education_id")
    assert not hasattr(candidate, "authorizes_apply")
    service_source = inspect.getsource(EducationNormalizationService).lower()
    assert "insert into" not in service_source
    assert "update " not in service_source
    assert "person_education" not in service_source


def test_service_has_no_db_or_ppr_writes():
    source = inspect.getsource(EducationNormalizationService).lower()
    assert "sqlalchemy" not in source
    assert "insert into" not in source
    assert "update " not in source
    assert "delete from" not in source
    assert "employee_id" not in source
    assert "person_education" not in source
    assert "dedup" not in source


def test_raw_fragment_preserves_source_text_without_normalization():
    raw = "  1. КазНМУ, 2010  "
    fragments = split_education_fragments(raw)
    assert fragments == ["1. КазНМУ, 2010"]
    parsed = parse_education_fragment(fragments[0], fragment_index=0)
    assert parsed.raw_fragment == "1. КазНМУ, 2010"
    assert parsed.institution_name.text == "КазНМУ"
    assert parsed.institution_name.raw == "КазНМУ"


def test_normalized_values_are_separate_from_raw_fragment():
    raw = "КазНМУ им. Доктора, специальность «Лечебное дело», 2015"
    parsed = parse_education_fragment(raw, fragment_index=0)
    assert parsed.raw_fragment == raw
    assert parsed.graduation_year.value == 2015
    assert parsed.graduation_year.raw == "2015"
    assert parsed.institution_name.text == "КазНМУ им. Доктора"
    assert raw not in (parsed.institution_name.text or "")


def test_ambiguous_text_with_year_does_not_invent_institution():
    raw = "непонятная запись, 2015"
    parsed = parse_education_fragment(raw, fragment_index=0)
    assert parsed.raw_fragment == raw
    assert parsed.graduation_year.value == 2015
    assert parsed.institution_name.text is None
    assert parsed.specialty.text is None
    assert parsed.qualification.text is None
    assert parsed.education_level.text is None
    assert "education_fragment_unparsed" in parsed.field_issues[SEMANTIC_FIELD_EDUCATION_RECORDS]


def test_golden_numbered_list_from_control_excel():
    raw = (
        "1. КазНМУ, 2010\n"
        "2. Карагандинский государственный медицинский университет, 2015"
    )
    candidates = EducationNormalizationService().normalize_row(
        row=_row(education=raw),
        profile=_profile(),
        person_match=_match_result(),
        import_run_id=7,
    )
    assert len(candidates) == 2
    assert candidates[0].raw_fragment == "1. КазНМУ, 2010"
    assert candidates[0].source_fragment_index == 0
    assert candidates[0].graduation_year.value == 2010
    assert candidates[0].institution_name.text == "КазНМУ"
    assert candidates[1].raw_fragment.startswith("2. Карагандинский")
    assert candidates[1].source_fragment_index == 1
    assert candidates[1].graduation_year.value == 2015
    assert "университет" in (candidates[1].institution_name.text or "").lower()


def test_inline_numbered_education_items_in_one_line():
    raw = (
        "1. Семипалатинский бизнес-колледж, 2006г. "
        "2. Семипалатинская государственная медицинская академия, 2012г. "
        "Специальность «Лечебное дело», квалификация «врач»"
    )
    fragments = split_education_fragments(raw)
    assert len(fragments) >= 2
    candidates = EducationNormalizationService().normalize_row(
        row=_row(education=raw),
        profile=_profile(),
        person_match=_match_result(),
        import_run_id=7,
    )
    assert len(candidates) == 2
    assert candidates[0].source_fragment_index == 0
    assert candidates[1].source_fragment_index == 1
    assert "Лечебное дело" in (candidates[0].specialty.text or "")
    assert "Лечебное дело" in (candidates[1].specialty.text or "")
    assert "врач" in (candidates[0].qualification.text or "")
    assert "врач" in (candidates[1].qualification.text or "")
    assert EDUCATION_SHARED_CONTEXT_ISSUE in candidates[0].field_issues.get(
        SEMANTIC_FIELD_EDUCATION_RECORDS, ()
    )


def test_golden_institution_specialty_year_from_control_excel():
    raw = "КазНМУ, специальность «Лечебное дело», 2015"
    candidates = EducationNormalizationService().normalize_row(
        row=_row(education=raw),
        profile=_profile(),
        person_match=_match_result(),
        import_run_id=7,
    )
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.raw_fragment == raw
    assert candidate.institution_name.text == "КазНМУ"
    assert "Лечебное дело" in (candidate.specialty.text or "")
    assert candidate.graduation_year.value == 2015
    assert candidate.readiness_status == EducationReadinessStatus.NORMALIZATION_READY


def test_golden_multiple_educations_via_newline_from_control_excel():
    raw = "КазНМУ, 1982\nСемипалатинский государственный медицинский университет, 1990"
    candidates = EducationNormalizationService().normalize_row(
        row=_row(education=raw),
        profile=_profile(),
        person_match=_match_result(),
        import_run_id=7,
    )
    assert len(candidates) == 2
    assert [candidate.source_fragment_index for candidate in candidates] == [0, 1]
    assert candidates[0].graduation_year.value == 1982
    assert candidates[1].graduation_year.value == 1990
    assert candidates[0].raw_fragment == "КазНМУ, 1982"
    assert candidates[1].raw_fragment.startswith("Семипалатинский")


def test_golden_ambiguous_incomplete_text_fail_safe():
    raw = "данные уточняются / без диплома"
    candidates = EducationNormalizationService().normalize_row(
        row=_row(education=raw),
        profile=_profile(),
        person_match=_match_result(),
        import_run_id=7,
    )
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.raw_fragment == raw
    assert candidate.institution_name.text is None
    assert candidate.graduation_year.value is None
    assert "education_fragment_incomplete" in candidate.field_issues.get(
        SEMANTIC_FIELD_EDUCATION_RECORDS, ()
    ) or "education_fragment_unparsed" in candidate.field_issues.get(
        SEMANTIC_FIELD_EDUCATION_RECORDS, ()
    )
    assert candidate.readiness_status == EducationReadinessStatus.REVIEW_REQUIRED
