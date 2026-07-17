# tests/test_wp_cl_010_other_ppr_normalization.py
"""Unit tests for WP-CL-010 other PPR fields normalization layer."""
from __future__ import annotations

import inspect
from datetime import datetime

import pytest

from app.control_list_import.domain.models import (
    MappingProfileColumnSnapshot,
    MappingProfileSheetSnapshot,
    MappingProfileSnapshot,
)
from app.control_list_import.domain.other_ppr_candidate import OtherPprReadinessStatus
from app.control_list_import.domain.person_match_models import MatchReason, MatchStatus, PersonMatchResult
from app.control_list_import.domain.staging_models import StagingCellInput, StagingRowInput
from app.control_list_import.domain.vocabulary import (
    PARSER_CODE_PERSON_CITIZENSHIP,
    PARSER_CODE_PPR_DISABILITY_SUMMARY,
    PARSER_CODE_PPR_MARITAL_STATUS,
    PARSER_CODE_PPR_MILITARY_SUMMARY,
    PARSER_CODE_QUALIFICATION_CATEGORY,
    PARSER_CODE_TEXT_AWARDS,
    PARSER_CODE_TEXT_NOTES,
    PARSER_CODE_TEXT_PLAIN,
    SEMANTIC_FIELD_PERSON_AWARDS,
    SEMANTIC_FIELD_PERSON_CITIZENSHIP,
    SEMANTIC_FIELD_PERSON_FULL_NAME,
    SEMANTIC_FIELD_PERSON_NATIONALITY_RAW,
    SEMANTIC_FIELD_PERSON_NOTES,
    SEMANTIC_FIELD_PPR_DISABILITY_SUMMARY,
    SEMANTIC_FIELD_PPR_MARITAL_STATUS,
    SEMANTIC_FIELD_PPR_MILITARY_SUMMARY,
    SEMANTIC_FIELD_QUALIFICATION_CATEGORY,
)
from app.control_list_import.other_ppr_normalization.fields import (
    normalize_citizenship,
    normalize_disability_summary,
    normalize_marital_status,
    normalize_military_summary,
)
from app.control_list_import.other_ppr_normalization.scope import OTHER_PPR_SKIP_REASON_BY_FIELD
from app.control_list_import.other_ppr_normalization.service import OtherPprNormalizationService
from app.db.models.control_list_mapping import (
    EMPLOYMENT_MODE_PRIMARY,
    PERSONNEL_CATEGORY_DOCTOR,
    PROFILE_STATUS_ACTIVE,
    SHEET_PURPOSE_PERSONNEL_CONTROL_LIST,
)


def _column(
    *,
    column_index: int,
    semantic_field: str,
    parser_code: str,
    letter: str,
) -> MappingProfileColumnSnapshot:
    return MappingProfileColumnSnapshot(
        profile_column_id=column_index,
        profile_sheet_id=1,
        column_index=column_index,
        column_letter=letter,
        raw_header=semantic_field,
        semantic_field=semantic_field,
        parser_code=parser_code,
        is_required=False,
    )


def _profile(columns: list[MappingProfileColumnSnapshot]) -> MappingProfileSnapshot:
    sheet = MappingProfileSheetSnapshot(
        profile_sheet_id=1,
        profile_id=10,
        sheet_name="врачи",
        personnel_category=PERSONNEL_CATEGORY_DOCTOR,
        employment_mode=EMPLOYMENT_MODE_PRIMARY,
        sheet_purpose=SHEET_PURPOSE_PERSONNEL_CONTROL_LIST,
        header_row_override=3,
        columns=columns,
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


def _row(cells: dict[int, str], row_id: int = 100) -> StagingRowInput:
    return StagingRowInput(
        row_id=row_id,
        sheet_name="врачи",
        excel_row_number=5,
        row_kind="data",
        cells=tuple(StagingCellInput(column_index=idx, raw_value=value) for idx, value in cells.items()),
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


def test_citizenship_alias():
    result = normalize_citizenship("  РК  ")
    assert result.raw == "  РК  "
    assert result.code == "KZ"
    assert result.text == "Казахстан"


def test_marital_status_alias():
    result = normalize_marital_status("замужем")
    assert result.code == "married"


def test_military_summary_not_applicable():
    result = normalize_military_summary("не подлежит воинскому учёту")
    assert result.code == "not_applicable"


def test_disability_summary_alias():
    result = normalize_disability_summary("нет")
    assert result.code == "no"


def test_nationality_plain_text():
    candidates = OtherPprNormalizationService().normalize_row(
        row=_row({11: "  казах  "}),
        profile=_profile(
            [
                _column(
                    column_index=11,
                    semantic_field=SEMANTIC_FIELD_PERSON_NATIONALITY_RAW,
                    parser_code=PARSER_CODE_TEXT_PLAIN,
                    letter="K",
                )
            ]
        ),
        person_match=_match_result(),
        import_run_id=7,
    )
    assert len(candidates) == 1
    assert candidates[0].raw_value == "  казах  "
    assert candidates[0].normalized_value.text == "казах"


def test_awards_and_notes_group():
    candidates = OtherPprNormalizationService().normalize_row(
        row=_row({12: "Почётная грамота", 13: "Служебная отметка"}),
        profile=_profile(
            [
                _column(
                    column_index=12,
                    semantic_field=SEMANTIC_FIELD_PERSON_AWARDS,
                    parser_code=PARSER_CODE_TEXT_AWARDS,
                    letter="L",
                ),
                _column(
                    column_index=13,
                    semantic_field=SEMANTIC_FIELD_PERSON_NOTES,
                    parser_code=PARSER_CODE_TEXT_NOTES,
                    letter="M",
                ),
            ]
        ),
        person_match=_match_result(),
        import_run_id=7,
    )
    assert len(candidates) == 2
    assert {candidate.semantic_field for candidate in candidates} == {
        SEMANTIC_FIELD_PERSON_AWARDS,
        SEMANTIC_FIELD_PERSON_NOTES,
    }


def test_qualification_category_group():
    candidates = OtherPprNormalizationService().normalize_row(
        row=_row({14: "высшая"}),
        profile=_profile(
            [
                _column(
                    column_index=14,
                    semantic_field=SEMANTIC_FIELD_QUALIFICATION_CATEGORY,
                    parser_code=PARSER_CODE_QUALIFICATION_CATEGORY,
                    letter="N",
                )
            ]
        ),
        person_match=_match_result(),
        import_run_id=7,
    )
    assert candidates[0].normalized_value.text == "высшая"


@pytest.mark.parametrize("value", ["-", "н/д", ""])
def test_technical_empty_skips_candidate(value: str):
    candidates = OtherPprNormalizationService().normalize_row(
        row=_row({15: value}) if value else _row({}),
        profile=_profile(
            [
                _column(
                    column_index=15,
                    semantic_field=SEMANTIC_FIELD_PERSON_CITIZENSHIP,
                    parser_code=PARSER_CODE_PERSON_CITIZENSHIP,
                    letter="O",
                )
            ]
        ),
        person_match=_match_result(),
        import_run_id=7,
    )
    assert candidates == []


def test_ambiguous_value_requires_review():
    candidates = OtherPprNormalizationService().normalize_row(
        row=_row({16: "гражданин мира"}),
        profile=_profile(
            [
                _column(
                    column_index=16,
                    semantic_field=SEMANTIC_FIELD_PERSON_CITIZENSHIP,
                    parser_code=PARSER_CODE_PERSON_CITIZENSHIP,
                    letter="P",
                )
            ]
        ),
        person_match=_match_result(),
        import_run_id=7,
    )
    assert candidates[0].readiness_status == OtherPprReadinessStatus.REVIEW_REQUIRED
    assert "other_ppr_citizenship_unmapped" in candidates[0].field_issues[SEMANTIC_FIELD_PERSON_CITIZENSHIP]


def test_military_unparsed_free_text():
    candidates = OtherPprNormalizationService().normalize_row(
        row=_row({17: "рядовой, 123456"}),
        profile=_profile(
            [
                _column(
                    column_index=17,
                    semantic_field=SEMANTIC_FIELD_PPR_MILITARY_SUMMARY,
                    parser_code=PARSER_CODE_PPR_MILITARY_SUMMARY,
                    letter="Q",
                )
            ]
        ),
        person_match=_match_result(),
        import_run_id=7,
    )
    assert candidates[0].raw_value == "рядовой, 123456"
    assert candidates[0].normalized_value.code is None
    assert "other_ppr_military_summary_unparsed" in candidates[0].field_issues[SEMANTIC_FIELD_PPR_MILITARY_SUMMARY]


def test_matched_person_reaches_normalization_ready():
    candidates = OtherPprNormalizationService().normalize_row(
        row=_row({18: "РК"}),
        profile=_profile(
            [
                _column(
                    column_index=18,
                    semantic_field=SEMANTIC_FIELD_PERSON_CITIZENSHIP,
                    parser_code=PARSER_CODE_PERSON_CITIZENSHIP,
                    letter="R",
                )
            ]
        ),
        person_match=_match_result(recommended_person_id=42),
        import_run_id=7,
    )
    assert candidates[0].matched_person_id == 42
    assert candidates[0].is_normalization_ready


def test_unmatched_person_still_creates_candidate():
    candidates = OtherPprNormalizationService().normalize_row(
        row=_row({18: "РК"}),
        profile=_profile(
            [
                _column(
                    column_index=18,
                    semantic_field=SEMANTIC_FIELD_PERSON_CITIZENSHIP,
                    parser_code=PARSER_CODE_PERSON_CITIZENSHIP,
                    letter="R",
                )
            ]
        ),
        person_match=_match_result(status=MatchStatus.NOT_FOUND, recommended_person_id=None),
        import_run_id=7,
    )
    assert candidates[0].matched_person_id is None
    assert candidates[0].readiness_status == OtherPprReadinessStatus.PERSON_UNMATCHED


def test_ambiguous_match_requires_review():
    candidates = OtherPprNormalizationService().normalize_row(
        row=_row({18: "РК"}),
        profile=_profile(
            [
                _column(
                    column_index=18,
                    semantic_field=SEMANTIC_FIELD_PERSON_CITIZENSHIP,
                    parser_code=PARSER_CODE_PERSON_CITIZENSHIP,
                    letter="R",
                )
            ]
        ),
        person_match=_match_result(status=MatchStatus.AMBIGUOUS, recommended_person_id=None),
        import_run_id=7,
    )
    assert candidates[0].readiness_status == OtherPprReadinessStatus.REVIEW_REQUIRED


def test_provenance_fields():
    candidates = OtherPprNormalizationService().normalize_row(
        row=_row({19: "женат"}, row_id=777),
        profile=_profile(
            [
                _column(
                    column_index=19,
                    semantic_field=SEMANTIC_FIELD_PPR_MARITAL_STATUS,
                    parser_code=PARSER_CODE_PPR_MARITAL_STATUS,
                    letter="S",
                )
            ]
        ),
        person_match=_match_result(source_row_id=777),
        import_run_id=99,
    )
    candidate = candidates[0]
    assert candidate.import_run_id == 99
    assert candidate.source_row_id == 777
    assert candidate.source_column_index == 19
    assert candidate.source_column_letter == "S"
    assert candidate.raw_value == "женат"


def test_unsupported_semantic_field_records_issue():
    candidates = OtherPprNormalizationService().normalize_row(
        row=_row({20: "some value"}),
        profile=_profile(
            [
                _column(
                    column_index=20,
                    semantic_field="declaration.summary",
                    parser_code=PARSER_CODE_TEXT_PLAIN,
                    letter="T",
                )
            ]
        ),
        person_match=_match_result(recommended_person_id=42),
        import_run_id=7,
    )
    assert len(candidates) == 1
    candidate = candidates[0]
    assert "other_ppr_unsupported_semantic_field" in candidate.field_issues["declaration.summary"]
    assert candidate.readiness_status == OtherPprReadinessStatus.REVIEW_REQUIRED
    assert not candidate.is_normalization_ready


def test_ambiguous_military_text_does_not_invent_controlled_code():
    result = normalize_military_summary("состоит на учете в другом городе")
    assert result.code is None
    assert "other_ppr_military_summary_ambiguous" in result.issues


def test_ambiguous_disability_text_does_not_invent_controlled_code():
    result = normalize_disability_summary("инвалидность не подтверждена")
    assert result.code is None
    assert "other_ppr_disability_summary_ambiguous" in result.issues


def test_citizenship_and_nationality_remain_distinct_semantic_fields():
    candidates = OtherPprNormalizationService().normalize_row(
        row=_row({26: "РК", 27: "казах"}),
        profile=_profile(
            [
                _column(
                    column_index=26,
                    semantic_field=SEMANTIC_FIELD_PERSON_CITIZENSHIP,
                    parser_code=PARSER_CODE_PERSON_CITIZENSHIP,
                    letter="Z",
                ),
                _column(
                    column_index=27,
                    semantic_field=SEMANTIC_FIELD_PERSON_NATIONALITY_RAW,
                    parser_code=PARSER_CODE_TEXT_PLAIN,
                    letter="AA",
                ),
            ]
        ),
        person_match=_match_result(),
        import_run_id=7,
    )
    by_field = {candidate.semantic_field: candidate for candidate in candidates}
    assert by_field[SEMANTIC_FIELD_PERSON_CITIZENSHIP].normalized_value.code == "KZ"
    assert by_field[SEMANTIC_FIELD_PERSON_NATIONALITY_RAW].normalized_value.code is None
    assert by_field[SEMANTIC_FIELD_PERSON_NATIONALITY_RAW].normalized_value.text == "казах"


def test_excluded_semantic_field_has_documented_skip_reason():
    assert OTHER_PPR_SKIP_REASON_BY_FIELD[SEMANTIC_FIELD_PERSON_FULL_NAME] == (
        "handled_by_prior_control_list_work_package"
    )


def test_excluded_semantic_field_is_skipped():
    candidates = OtherPprNormalizationService().normalize_row(
        row=_row({21: "Иванов Иван"}),
        profile=_profile(
            [
                _column(
                    column_index=21,
                    semantic_field=SEMANTIC_FIELD_PERSON_FULL_NAME,
                    parser_code=PARSER_CODE_TEXT_PLAIN,
                    letter="U",
                )
            ]
        ),
        person_match=_match_result(),
        import_run_id=7,
    )
    assert candidates == []


def test_multiple_supported_fields_in_one_row():
    candidates = OtherPprNormalizationService().normalize_row(
        row=_row({22: "РК", 23: "женат", 24: "не подлежит", 25: "нет"}),
        profile=_profile(
            [
                _column(
                    column_index=22,
                    semantic_field=SEMANTIC_FIELD_PERSON_CITIZENSHIP,
                    parser_code=PARSER_CODE_PERSON_CITIZENSHIP,
                    letter="V",
                ),
                _column(
                    column_index=23,
                    semantic_field=SEMANTIC_FIELD_PPR_MARITAL_STATUS,
                    parser_code=PARSER_CODE_PPR_MARITAL_STATUS,
                    letter="W",
                ),
                _column(
                    column_index=24,
                    semantic_field=SEMANTIC_FIELD_PPR_MILITARY_SUMMARY,
                    parser_code=PARSER_CODE_PPR_MILITARY_SUMMARY,
                    letter="X",
                ),
                _column(
                    column_index=25,
                    semantic_field=SEMANTIC_FIELD_PPR_DISABILITY_SUMMARY,
                    parser_code=PARSER_CODE_PPR_DISABILITY_SUMMARY,
                    letter="Y",
                ),
            ]
        ),
        person_match=_match_result(),
        import_run_id=7,
    )
    assert len(candidates) == 4


def test_normalization_ready_does_not_authorize_ppr_apply():
    candidate = OtherPprNormalizationService().normalize_row(
        row=_row({18: "РК"}),
        profile=_profile(
            [
                _column(
                    column_index=18,
                    semantic_field=SEMANTIC_FIELD_PERSON_CITIZENSHIP,
                    parser_code=PARSER_CODE_PERSON_CITIZENSHIP,
                    letter="R",
                )
            ]
        ),
        person_match=_match_result(recommended_person_id=42),
        import_run_id=7,
    )[0]
    assert candidate.is_normalization_ready
    assert not hasattr(candidate, "person_training_id")
    assert not hasattr(candidate, "authorizes_apply")
    source = inspect.getsource(OtherPprNormalizationService).lower()
    assert "insert into" not in source
    assert "person_marital_status" not in source


def test_service_has_no_db_or_ppr_writes():
    source = inspect.getsource(OtherPprNormalizationService).lower()
    assert "sqlalchemy" not in source
    assert "insert into" not in source
    assert "update " not in source
    assert "delete from" not in source
    assert "employee_id" not in source
    assert "dedup" not in source
