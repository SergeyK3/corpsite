# tests/test_wp_cl_006_employment_normalization.py
"""Unit tests for WP-CL-006 employment normalization layer."""
from __future__ import annotations

import inspect
from datetime import date, datetime
from decimal import Decimal

import pytest

from app.control_list_import.domain.employment_candidate import EmploymentReadinessStatus
from app.control_list_import.domain.models import (
    MappingProfileColumnSnapshot,
    MappingProfileSheetSnapshot,
    MappingProfileSnapshot,
)
from app.control_list_import.domain.person_match_models import MatchReason, MatchStatus, PersonMatchResult
from app.control_list_import.domain.staging_models import StagingCellInput, StagingRowInput
from app.control_list_import.domain.vocabulary import (
    PARSER_CODE_DATE_TEXT,
    PARSER_CODE_EMPLOYMENT_DEPARTMENT,
    PARSER_CODE_EMPLOYMENT_POSITION,
    PARSER_CODE_EMPLOYMENT_RATE,
    PARSER_CODE_EMPLOYMENT_STARTED_AT,
    SEMANTIC_FIELD_EMPLOYMENT_DEPARTMENT_NAME,
    SEMANTIC_FIELD_EMPLOYMENT_POSITION_TITLE,
    SEMANTIC_FIELD_EMPLOYMENT_RATE,
    SEMANTIC_FIELD_EMPLOYMENT_STARTED_AT,
)
from app.control_list_import.employment_normalization.mode import normalize_employment_mode
from app.control_list_import.employment_normalization.rate import normalize_employment_rate
from app.control_list_import.employment_normalization.service import EmploymentNormalizationService
from app.db.models.control_list_mapping import (
    EMPLOYMENT_MODE_CONCURRENT,
    EMPLOYMENT_MODE_PRIMARY,
    PERSONNEL_CATEGORY_DOCTOR,
    PROFILE_STATUS_ACTIVE,
    SHEET_PURPOSE_PERSONNEL_CONTROL_LIST,
)


def _employment_columns() -> list[MappingProfileColumnSnapshot]:
    return [
        MappingProfileColumnSnapshot(
            profile_column_id=1,
            profile_sheet_id=1,
            column_index=7,
            column_letter="G",
            raw_header="Подразделение",
            semantic_field=SEMANTIC_FIELD_EMPLOYMENT_DEPARTMENT_NAME,
            parser_code=PARSER_CODE_EMPLOYMENT_DEPARTMENT,
            is_required=False,
        ),
        MappingProfileColumnSnapshot(
            profile_column_id=2,
            profile_sheet_id=1,
            column_index=8,
            column_letter="H",
            raw_header="Должность",
            semantic_field=SEMANTIC_FIELD_EMPLOYMENT_POSITION_TITLE,
            parser_code=PARSER_CODE_EMPLOYMENT_POSITION,
            is_required=False,
        ),
        MappingProfileColumnSnapshot(
            profile_column_id=3,
            profile_sheet_id=1,
            column_index=9,
            column_letter="I",
            raw_header="Ставка",
            semantic_field=SEMANTIC_FIELD_EMPLOYMENT_RATE,
            parser_code=PARSER_CODE_EMPLOYMENT_RATE,
            is_required=False,
        ),
        MappingProfileColumnSnapshot(
            profile_column_id=4,
            profile_sheet_id=1,
            column_index=10,
            column_letter="J",
            raw_header="Дата начала",
            semantic_field=SEMANTIC_FIELD_EMPLOYMENT_STARTED_AT,
            parser_code=PARSER_CODE_EMPLOYMENT_STARTED_AT,
            is_required=False,
        ),
    ]


def _profile(*, sheet_name: str = "врачи", employment_mode: str = EMPLOYMENT_MODE_PRIMARY) -> MappingProfileSnapshot:
    sheet = MappingProfileSheetSnapshot(
        profile_sheet_id=1,
        profile_id=10,
        sheet_name=sheet_name,
        personnel_category=PERSONNEL_CATEGORY_DOCTOR,
        employment_mode=employment_mode,
        sheet_purpose=SHEET_PURPOSE_PERSONNEL_CONTROL_LIST,
        header_row_override=3,
        columns=_employment_columns(),
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


def _row(
    *,
    sheet_name: str = "врачи",
    department: str | None = "Терапевтическое отделение",
    position: str | None = "Врач-терапевт",
    rate: str | float | None = "1",
    started_at: str | None = "01.03.2020",
    row_id: int = 100,
) -> StagingRowInput:
    cells: list[StagingCellInput] = []
    if department is not None:
        cells.append(StagingCellInput(column_index=7, raw_value=department))
    if position is not None:
        cells.append(StagingCellInput(column_index=8, raw_value=position))
    if rate is not None:
        cells.append(StagingCellInput(column_index=9, raw_value=rate))
    if started_at is not None:
        cells.append(StagingCellInput(column_index=10, raw_value=started_at))
    return StagingRowInput(
        row_id=row_id,
        sheet_name=sheet_name,
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


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1", Decimal("1")),
        (1, Decimal("1")),
        ("0.5", Decimal("0.5")),
        ("0,5", Decimal("0.5")),
    ],
)
def test_normalize_employment_rate_valid_values(raw, expected):
    result = normalize_employment_rate(raw)
    assert result.value == expected
    assert result.is_valid


def test_normalize_employment_rate_invalid():
    result = normalize_employment_rate("abc")
    assert not result.is_valid
    assert "employment_rate_unrecognized_format" in result.issues


def test_normalize_employment_mode_primary():
    mode, issues = normalize_employment_mode(EMPLOYMENT_MODE_PRIMARY)
    assert mode == EMPLOYMENT_MODE_PRIMARY
    assert issues == ()


def test_primary_employment_mode_on_candidate():
    candidate = EmploymentNormalizationService().normalize_row(
        row=_row(),
        profile=_profile(employment_mode=EMPLOYMENT_MODE_PRIMARY),
        person_match=_match_result(),
        import_run_id=7,
    )
    assert candidate is not None
    assert candidate.employment_mode == EMPLOYMENT_MODE_PRIMARY


def test_concurrent_employment_mode():
    profile = _profile(sheet_name="врачи совместители", employment_mode=EMPLOYMENT_MODE_CONCURRENT)
    candidate = EmploymentNormalizationService().normalize_row(
        row=_row(sheet_name="врачи совместители"),
        profile=profile,
        person_match=_match_result(),
        import_run_id=7,
    )
    assert candidate is not None
    assert candidate.employment_mode == EMPLOYMENT_MODE_CONCURRENT


def test_matched_person_reaches_normalization_ready():
    candidate = EmploymentNormalizationService().normalize_row(
        row=_row(),
        profile=_profile(),
        person_match=_match_result(recommended_person_id=42),
        import_run_id=7,
    )
    assert candidate is not None
    assert candidate.matched_person_id == 42
    assert candidate.readiness_status == EmploymentReadinessStatus.NORMALIZATION_READY
    assert candidate.is_normalization_ready


def test_normalization_ready_does_not_authorize_canonical_employment_or_apply():
    candidate = EmploymentNormalizationService().normalize_row(
        row=_row(),
        profile=_profile(),
        person_match=_match_result(recommended_person_id=42),
        import_run_id=7,
    )
    assert candidate is not None
    assert candidate.is_normalization_ready
    assert type(candidate).__name__ == "EmploymentCandidate"
    assert not hasattr(candidate, "employee_id")
    assert not hasattr(candidate, "assignment_id")
    assert not hasattr(candidate, "position_id")
    assert not hasattr(candidate, "org_unit_id")
    assert not hasattr(candidate, "authorizes_apply")
    service_source = inspect.getsource(EmploymentNormalizationService).lower()
    assert "auto_apply" not in service_source
    assert "insert into" not in service_source


def test_unmatched_person_still_creates_candidate():
    candidate = EmploymentNormalizationService().normalize_row(
        row=_row(),
        profile=_profile(),
        person_match=_match_result(status=MatchStatus.NOT_FOUND, recommended_person_id=None),
        import_run_id=7,
    )
    assert candidate is not None
    assert candidate.matched_person_id is None
    assert candidate.readiness_status == EmploymentReadinessStatus.PERSON_UNMATCHED
    assert not candidate.is_normalization_ready


def test_ambiguous_person_requires_review():
    candidate = EmploymentNormalizationService().normalize_row(
        row=_row(),
        profile=_profile(),
        person_match=_match_result(status=MatchStatus.AMBIGUOUS, recommended_person_id=None),
        import_run_id=7,
    )
    assert candidate is not None
    assert candidate.matched_person_id is None
    assert candidate.readiness_status == EmploymentReadinessStatus.REVIEW_REQUIRED


def test_invalid_person_match_requires_review():
    candidate = EmploymentNormalizationService().normalize_row(
        row=_row(),
        profile=_profile(),
        person_match=_match_result(status=MatchStatus.INVALID, recommended_person_id=None),
        import_run_id=7,
    )
    assert candidate.readiness_status == EmploymentReadinessStatus.PERSON_MATCH_INVALID


def test_missing_department_and_position_add_issues():
    candidate = EmploymentNormalizationService().normalize_row(
        row=_row(department=None, position=None),
        profile=_profile(),
        person_match=_match_result(),
        import_run_id=7,
    )
    assert candidate is not None
    assert "employment_department_missing" in candidate.field_issues[SEMANTIC_FIELD_EMPLOYMENT_DEPARTMENT_NAME]
    assert "employment_position_missing" in candidate.field_issues[SEMANTIC_FIELD_EMPLOYMENT_POSITION_TITLE]
    assert candidate.readiness_status == EmploymentReadinessStatus.REVIEW_REQUIRED


def test_invalid_rate_blocks_normalization_ready():
    candidate = EmploymentNormalizationService().normalize_row(
        row=_row(rate="invalid"),
        profile=_profile(),
        person_match=_match_result(),
        import_run_id=7,
    )
    assert candidate is not None
    assert "employment_rate_unrecognized_format" in candidate.field_issues[SEMANTIC_FIELD_EMPLOYMENT_RATE]
    assert candidate.readiness_status == EmploymentReadinessStatus.REVIEW_REQUIRED


def test_provenance_fields():
    candidate = EmploymentNormalizationService().normalize_row(
        row=_row(row_id=555),
        profile=_profile(),
        person_match=_match_result(source_row_id=555),
        import_run_id=99,
    )
    assert candidate is not None
    assert candidate.import_run_id == 99
    assert candidate.source_row_id == 555
    assert candidate.source_sheet_name == "врачи"
    assert candidate.source_excel_row_number == 5
    assert candidate.profile_id == 10
    assert candidate.profile_code == "control_list_default"
    assert candidate.profile_version == 1


def test_service_has_no_db_or_employment_writes():
    source = inspect.getsource(EmploymentNormalizationService)
    lowered = source.lower()
    assert "sqlalchemy" not in lowered
    assert "insert into" not in lowered
    assert "update " not in lowered
    assert "delete from" not in lowered
    assert "employee_id" not in source
    assert "persons" not in lowered
    assert "employees" not in lowered
    assert "person_assignments" not in lowered
