# tests/test_wp_cl_009_training_normalization.py
"""Unit tests for WP-CL-009 training normalization layer."""
from __future__ import annotations

import inspect
from datetime import datetime
from decimal import Decimal

import pytest

from app.control_list_import.domain.models import (
    MappingProfileColumnSnapshot,
    MappingProfileSheetSnapshot,
    MappingProfileSnapshot,
)
from app.control_list_import.domain.person_match_models import MatchReason, MatchStatus, PersonMatchResult
from app.control_list_import.domain.staging_models import StagingCellInput, StagingRowInput
from app.control_list_import.domain.training_candidate import TrainingReadinessStatus
from app.control_list_import.domain.vocabulary import PARSER_CODE_RECORDS_TRAINING, SEMANTIC_FIELD_TRAINING_RECORDS
from app.control_list_import.training_normalization.records import (
    is_technical_empty_training_cell,
    parse_training_fragment,
    split_training_fragments,
)
from app.control_list_import.training_normalization.service import TrainingNormalizationService
from app.db.models.control_list_mapping import (
    EMPLOYMENT_MODE_PRIMARY,
    PERSONNEL_CATEGORY_DOCTOR,
    PROFILE_STATUS_ACTIVE,
    SHEET_PURPOSE_PERSONNEL_CONTROL_LIST,
)


def _training_column() -> MappingProfileColumnSnapshot:
    return MappingProfileColumnSnapshot(
        profile_column_id=1,
        profile_sheet_id=1,
        column_index=10,
        column_letter="J",
        raw_header="Повышение квалификации",
        semantic_field=SEMANTIC_FIELD_TRAINING_RECORDS,
        parser_code=PARSER_CODE_RECORDS_TRAINING,
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
        columns=[_training_column()],
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


def _row(*, training: str | None, row_id: int = 100) -> StagingRowInput:
    cells: list[StagingCellInput] = []
    if training is not None:
        cells.append(StagingCellInput(column_index=10, raw_value=training))
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


def test_single_training_record():
    candidates = TrainingNormalizationService().normalize_row(
        row=_row(training="ПК по кардиологии, 36 ч., 2023"),
        profile=_profile(),
        person_match=_match_result(),
        import_run_id=7,
    )
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.duration_hours.value == Decimal("36")
    assert candidate.completion_year.value == 2023
    assert candidate.training_type.text == "QUAL_UPGRADE"
    assert candidate.readiness_status == TrainingReadinessStatus.NORMALIZATION_READY


@pytest.mark.parametrize(
    "raw",
    [
        "ПК «Терапия» 24 ч 2022\nсеминар «Инфекционный контроль» 16 ч., 2023",
        "ПК «Терапия» 24 ч 2022; семинар «Инфекционный контроль» 16 ч., 2023",
        "ПК «Терапия» 24 ч 2022 | семинар «Инфекционный контроль» 16 ч., 2023",
    ],
)
def test_multiple_records_via_delimiters(raw: str):
    candidates = TrainingNormalizationService().normalize_row(
        row=_row(training=raw),
        profile=_profile(),
        person_match=_match_result(),
        import_run_id=7,
    )
    assert len(candidates) == 2
    assert candidates[0].source_fragment_index == 0
    assert candidates[1].source_fragment_index == 1
    assert candidates[0].completion_year.value == 2022
    assert candidates[1].completion_year.value == 2023


def test_numbered_list():
    raw = (
        "1. ПК «Неотложная помощь» 72 ч 2022\n"
        "2. семинар «Инфекционный контроль» 16 ч., 2023"
    )
    fragments = split_training_fragments(raw)
    assert len(fragments) == 2
    assert fragments[0].startswith("1.")
    candidates = TrainingNormalizationService().normalize_row(
        row=_row(training=raw),
        profile=_profile(),
        person_match=_match_result(),
        import_run_id=7,
    )
    assert len(candidates) == 2
    assert candidates[0].raw_fragment.startswith("1.")
    assert candidates[0].duration_hours.value == Decimal("72")


def test_title_is_not_used_as_provider():
    raw = "Курс по неотложной помощи, 72 ч., 2024"
    parsed = parse_training_fragment(raw, fragment_index=0)
    assert parsed.raw_fragment == raw
    assert parsed.provider_name.text is None
    assert "неотложной помощи" in (parsed.training_title.text or "").lower()


def test_explicit_provider_label():
    raw = "ПК по кардиологии, организация: РЦПЧ г. Алматы, 36 ч., 2023"
    candidate = TrainingNormalizationService().normalize_row(
        row=_row(training=raw),
        profile=_profile(),
        person_match=_match_result(),
        import_run_id=7,
    )[0]
    assert candidate.provider_name.text == "РЦПЧ г. Алматы"
    assert "кардиологии" in (candidate.training_title.text or "").lower()
    assert candidate.provider_name.text != candidate.training_title.text


def test_completion_date_and_year():
    parsed = parse_training_fragment("семинар «Качество», 24 ч., 15.03.2024", fragment_index=0)
    assert parsed.completion_date.value == datetime(2024, 3, 15).date()
    assert parsed.completion_year.value == 2024


def test_duration_hours():
    parsed = parse_training_fragment("курс, 144 акад. часов, 2023", fragment_index=0)
    assert parsed.duration_hours.value == Decimal("144")


def test_certificate_number():
    raw = "ПК «Управление МО», 144 ч., сертификат №123/45, 2023"
    parsed = parse_training_fragment(raw, fragment_index=0)
    assert parsed.certificate_number.text == "123/45"


def test_commas_inside_record_do_not_split():
    raw = "ПК «Управление медицинской организацией», 144 ч., 2023"
    assert len(split_training_fragments(raw)) == 1


def test_incomplete_fragment_kept_with_issue():
    candidates = TrainingNormalizationService().normalize_row(
        row=_row(training="данные уточняются"),
        profile=_profile(),
        person_match=_match_result(),
        import_run_id=7,
    )
    assert len(candidates) == 1
    assert candidates[0].raw_fragment == "данные уточняются"
    assert "training_fragment_incomplete" in candidates[0].field_issues.get(
        SEMANTIC_FIELD_TRAINING_RECORDS, ()
    )
    assert candidates[0].readiness_status == TrainingReadinessStatus.REVIEW_REQUIRED


def test_unparsed_year_only_fragment():
    parsed = parse_training_fragment("2024", fragment_index=0)
    assert parsed.raw_fragment == "2024"
    assert parsed.completion_year.value == 2024
    assert parsed.training_title.text is None
    assert "training_fragment_unparsed" in parsed.field_issues[SEMANTIC_FIELD_TRAINING_RECORDS]


@pytest.mark.parametrize("value", ["", "   ", "-", "н/д", "N/A"])
def test_empty_and_technical_empty_values(value: str):
    assert is_technical_empty_training_cell(value) or not value.strip()
    candidates = TrainingNormalizationService().normalize_row(
        row=_row(training=value if value.strip() else value or None),
        profile=_profile(),
        person_match=_match_result(),
        import_run_id=7,
    )
    assert candidates == []


def test_matched_person_reaches_normalization_ready():
    candidates = TrainingNormalizationService().normalize_row(
        row=_row(training="ПК по терапии, 24 ч., 2023"),
        profile=_profile(),
        person_match=_match_result(recommended_person_id=42),
        import_run_id=7,
    )
    assert candidates[0].matched_person_id == 42
    assert candidates[0].is_normalization_ready


def test_unmatched_person_still_creates_candidates():
    candidates = TrainingNormalizationService().normalize_row(
        row=_row(training="ПК по терапии, 24 ч., 2023"),
        profile=_profile(),
        person_match=_match_result(status=MatchStatus.NOT_FOUND, recommended_person_id=None),
        import_run_id=7,
    )
    assert candidates[0].matched_person_id is None
    assert candidates[0].readiness_status == TrainingReadinessStatus.PERSON_UNMATCHED


def test_ambiguous_match_requires_review():
    candidates = TrainingNormalizationService().normalize_row(
        row=_row(training="ПК по терапии, 24 ч., 2023"),
        profile=_profile(),
        person_match=_match_result(status=MatchStatus.AMBIGUOUS, recommended_person_id=None),
        import_run_id=7,
    )
    assert candidates[0].readiness_status == TrainingReadinessStatus.REVIEW_REQUIRED


def test_invalid_person_match_status():
    candidates = TrainingNormalizationService().normalize_row(
        row=_row(training="ПК по терапии, 24 ч., 2023"),
        profile=_profile(),
        person_match=_match_result(status=MatchStatus.INVALID, recommended_person_id=None),
        import_run_id=7,
    )
    assert candidates[0].readiness_status == TrainingReadinessStatus.PERSON_MATCH_INVALID


def test_provenance_per_fragment():
    raw = "ПК «Терапия» 24 ч 2022\nсеминар «Инфекционный контроль» 16 ч., 2023"
    candidates = TrainingNormalizationService().normalize_row(
        row=_row(training=raw, row_id=555),
        profile=_profile(),
        person_match=_match_result(source_row_id=555),
        import_run_id=99,
    )
    assert len(candidates) == 2
    for index, candidate in enumerate(candidates):
        assert candidate.import_run_id == 99
        assert candidate.source_row_id == 555
        assert candidate.source_column_index == 10
        assert candidate.source_column_letter == "J"
        assert candidate.source_fragment_index == index
        assert candidate.raw_fragment in raw


def test_normalization_ready_does_not_authorize_ppr_training_apply():
    candidate = TrainingNormalizationService().normalize_row(
        row=_row(training="ПК по терапии, 24 ч., 2023"),
        profile=_profile(),
        person_match=_match_result(recommended_person_id=42),
        import_run_id=7,
    )[0]
    assert candidate.is_normalization_ready
    assert not hasattr(candidate, "person_training_id")
    assert not hasattr(candidate, "authorizes_apply")
    source = inspect.getsource(TrainingNormalizationService).lower()
    assert "insert into" not in source
    assert "person_training" not in source


def test_service_has_no_db_or_ppr_writes():
    source = inspect.getsource(TrainingNormalizationService).lower()
    assert "sqlalchemy" not in source
    assert "insert into" not in source
    assert "update " not in source
    assert "delete from" not in source
    assert "employee_id" not in source
    assert "dedup" not in source


def test_raw_fragment_preserves_source_text():
    raw = "  1. ПК «Терапия» 72 ч 2022  "
    fragments = split_training_fragments(raw)
    parsed = parse_training_fragment(fragments[0], fragment_index=0)
    assert parsed.raw_fragment == "1. ПК «Терапия» 72 ч 2022"


def test_golden_numbered_list_from_control_excel():
    raw = (
        "1. ПК «Неотложная помощь» 72 ч 2022\n"
        "2. семинар «Инфекционный контроль» 16 ч., 2023"
    )
    candidates = TrainingNormalizationService().normalize_row(
        row=_row(training=raw),
        profile=_profile(),
        person_match=_match_result(),
        import_run_id=7,
    )
    assert len(candidates) == 2
    assert candidates[0].training_type.text == "QUAL_UPGRADE"
    assert candidates[1].training_type.text == "SEMINAR"


def test_golden_course_hours_certificate_year_from_control_excel():
    raw = "ПК «Управление медицинской организацией», 144 ч., сертификат №123/45, 2023"
    candidate = TrainingNormalizationService().normalize_row(
        row=_row(training=raw),
        profile=_profile(),
        person_match=_match_result(),
        import_run_id=7,
    )[0]
    assert candidate.duration_hours.value == Decimal("144")
    assert candidate.certificate_number.text == "123/45"
    assert candidate.completion_year.value == 2023
    assert candidate.readiness_status == TrainingReadinessStatus.NORMALIZATION_READY


def test_golden_multiple_trainings_via_newline_from_control_excel():
    raw = "ПК «Терапия» 24 ч 2022\nконференция «Онкология» 8 ч., 2024"
    candidates = TrainingNormalizationService().normalize_row(
        row=_row(training=raw),
        profile=_profile(),
        person_match=_match_result(),
        import_run_id=7,
    )
    assert len(candidates) == 2
    assert candidates[0].completion_year.value == 2022
    assert candidates[1].completion_year.value == 2024


def test_golden_explicit_provider_from_control_excel():
    raw = "ПК по анестезиологии, организация: Учебный центр «Медицина», 36 ч., 15.05.2023"
    candidate = TrainingNormalizationService().normalize_row(
        row=_row(training=raw),
        profile=_profile(),
        person_match=_match_result(),
        import_run_id=7,
    )[0]
    assert "Учебный центр" in (candidate.provider_name.text or "")
    assert candidate.completion_date.value == datetime(2023, 5, 15).date()


def test_golden_ambiguous_incomplete_text_fail_safe():
    raw = "уточняется / без сертификата"
    candidate = TrainingNormalizationService().normalize_row(
        row=_row(training=raw),
        profile=_profile(),
        person_match=_match_result(),
        import_run_id=7,
    )[0]
    assert candidate.raw_fragment == raw
    assert candidate.training_title.text is None
    assert candidate.provider_name.text is None
    assert candidate.readiness_status == TrainingReadinessStatus.REVIEW_REQUIRED
