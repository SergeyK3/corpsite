# tests/test_wp_cl_004_person_normalization.py
"""Unit tests for WP-CL-004 person normalization layer."""
from __future__ import annotations

from datetime import date, datetime

import pytest

from app.control_list_import.domain.models import (
    MappingProfileColumnSnapshot,
    MappingProfileSheetSnapshot,
    MappingProfileSnapshot,
)
from app.control_list_import.domain.staging_models import (
    StagingCellInput,
    StagingRowInput,
    StagingRunInput,
    StagingSheetInput,
)
from app.control_list_import.domain.vocabulary import (
    PARSER_CODE_DATE_EXCEL_SERIAL,
    PARSER_CODE_DATE_TEXT,
    PARSER_CODE_EMPLOYMENT_DEPARTMENT,
    PARSER_CODE_EMPLOYMENT_POSITION,
    PARSER_CODE_IDENTITY_IIN,
    PARSER_CODE_IDENTITY_PHONE,
    PARSER_CODE_PERSON_FULL_NAME,
    PARSER_CODE_PERSON_SEX,
    PARSER_CODE_TEXT_PLAIN,
    SEMANTIC_FIELD_EMPLOYMENT_DEPARTMENT_NAME,
    SEMANTIC_FIELD_EMPLOYMENT_POSITION_TITLE,
    SEMANTIC_FIELD_PERSON_BIRTH_DATE,
    SEMANTIC_FIELD_PERSON_FULL_NAME,
    SEMANTIC_FIELD_PERSON_IIN,
    SEMANTIC_FIELD_PERSON_PHONE,
    SEMANTIC_FIELD_PERSON_SEX,
)
from app.control_list_import.normalization.dates import normalize_birth_date
from app.control_list_import.normalization.full_name import normalize_full_name
from app.control_list_import.normalization.iin import normalize_iin
from app.control_list_import.normalization.phone import normalize_phone
from app.control_list_import.normalization.service import PersonNormalizationService
from app.control_list_import.normalization.sex import normalize_sex
from app.control_list_import.normalization.strings import normalize_plain_string
from app.db.models.control_list_mapping import (
    EMPLOYMENT_MODE_PRIMARY,
    PERSONNEL_CATEGORY_DOCTOR,
    PROFILE_STATUS_ACTIVE,
    SHEET_PURPOSE_PERSONNEL_CONTROL_LIST,
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
        columns=[
            MappingProfileColumnSnapshot(
                profile_column_id=1,
                profile_sheet_id=1,
                column_index=2,
                column_letter="B",
                raw_header="ФИО",
                semantic_field=SEMANTIC_FIELD_PERSON_FULL_NAME,
                parser_code=PARSER_CODE_PERSON_FULL_NAME,
                is_required=True,
            ),
            MappingProfileColumnSnapshot(
                profile_column_id=2,
                profile_sheet_id=1,
                column_index=3,
                column_letter="C",
                raw_header="ИИН",
                semantic_field=SEMANTIC_FIELD_PERSON_IIN,
                parser_code=PARSER_CODE_IDENTITY_IIN,
                is_required=True,
            ),
            MappingProfileColumnSnapshot(
                profile_column_id=3,
                profile_sheet_id=1,
                column_index=4,
                column_letter="D",
                raw_header="Дата рождения",
                semantic_field=SEMANTIC_FIELD_PERSON_BIRTH_DATE,
                parser_code=PARSER_CODE_DATE_TEXT,
                is_required=False,
            ),
            MappingProfileColumnSnapshot(
                profile_column_id=4,
                profile_sheet_id=1,
                column_index=5,
                column_letter="E",
                raw_header="Телефон",
                semantic_field=SEMANTIC_FIELD_PERSON_PHONE,
                parser_code=PARSER_CODE_IDENTITY_PHONE,
                is_required=False,
            ),
            MappingProfileColumnSnapshot(
                profile_column_id=5,
                profile_sheet_id=1,
                column_index=6,
                column_letter="F",
                raw_header="Пол",
                semantic_field=SEMANTIC_FIELD_PERSON_SEX,
                parser_code=PARSER_CODE_PERSON_SEX,
                is_required=False,
            ),
            MappingProfileColumnSnapshot(
                profile_column_id=6,
                profile_sheet_id=1,
                column_index=7,
                column_letter="G",
                raw_header="Подразделение",
                semantic_field=SEMANTIC_FIELD_EMPLOYMENT_DEPARTMENT_NAME,
                parser_code=PARSER_CODE_EMPLOYMENT_DEPARTMENT,
                is_required=False,
            ),
            MappingProfileColumnSnapshot(
                profile_column_id=7,
                profile_sheet_id=1,
                column_index=8,
                column_letter="H",
                raw_header="Должность",
                semantic_field=SEMANTIC_FIELD_EMPLOYMENT_POSITION_TITLE,
                parser_code=PARSER_CODE_EMPLOYMENT_POSITION,
                is_required=False,
            ),
        ],
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


def test_normalize_plain_string_trims_unicode_and_whitespace():
    text, issues = normalize_plain_string("  Әбіл   Қасымов  ")
    assert issues == ()
    assert text == "Әбіл Қасымов"


def test_normalize_full_name_collapses_whitespace_and_title_cases():
    result = normalize_full_name("  иванов   иван   иванович  ")
    assert result.display == "Иванов Иван Иванович"
    assert result.normalized_key == "иванов иван иванович"
    assert result.is_valid


def test_normalize_full_name_rejects_digits():
    result = normalize_full_name("Иванов123 Иван")
    assert "full_name_contains_digits" in result.issues


def test_normalize_iin_pads_11_digits_and_handles_float():
    result = normalize_iin("900101300123")
    assert result.digits == "900101300123"
    assert result.is_valid

    padded = normalize_iin("90010130012")
    assert padded.digits == "090010130012"

    numeric = normalize_iin(900101300123.0)
    assert numeric.digits == "900101300123"
    assert "iin_stored_as_number" in numeric.issues


def test_normalize_iin_empty_and_invalid():
    empty = normalize_iin(None)
    assert empty.is_empty
    assert not empty.is_valid

    invalid = normalize_iin("abc")
    assert invalid.digits is None
    assert invalid.issues


@pytest.mark.parametrize(
    "raw,expected_digits",
    [
        ("+7 (701) 123-45-67", "77011234567"),
        ("87011234567", "77011234567"),
        ("7011234567", "7011234567"),
    ],
)
def test_normalize_phone_formats(raw, expected_digits):
    result = normalize_phone(raw)
    assert result.digits == expected_digits
    assert result.is_valid


def test_normalize_phone_invalid_and_empty():
    assert normalize_phone(None).is_empty
    invalid = normalize_phone("123")
    assert "phone_invalid_length" in invalid.issues


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("15.03.1990", date(1990, 3, 15)),
        ("1990-03-15", date(1990, 3, 15)),
        (32874, date(1990, 1, 1)),
        (datetime(1985, 7, 20, 0, 0), date(1985, 7, 20)),
    ],
)
def test_normalize_birth_date_formats(raw, expected):
    result = normalize_birth_date(raw)
    assert result.value == expected


def test_normalize_birth_date_empty_and_invalid():
    assert normalize_birth_date("").is_empty
    invalid = normalize_birth_date("not-a-date")
    assert invalid.value is None
    assert "birth_date_unrecognized_format" in invalid.issues


def test_normalize_sex_values():
    assert normalize_sex("муж").code == "M"
    assert normalize_sex("Жен.").code == "F"
    unknown = normalize_sex("не указан")
    assert unknown.code is None
    assert "sex_unrecognized_value" in unknown.issues


def test_person_normalization_service_builds_candidate():
    profile = _profile()
    row = StagingRowInput(
        row_id=100,
        sheet_name="врачи",
        excel_row_number=5,
        row_kind="data",
        cells=(
            StagingCellInput(column_index=2, raw_value="  Сейтова   Айжан   Нурлыбековна  "),
            StagingCellInput(column_index=3, raw_value="900101300123"),
            StagingCellInput(column_index=4, raw_value="15.03.1990"),
            StagingCellInput(column_index=5, raw_value="+7 (701) 123-45-67"),
            StagingCellInput(column_index=6, raw_value="жен"),
            StagingCellInput(column_index=7, raw_value="  Терапевтическое отделение  "),
            StagingCellInput(column_index=8, raw_value="Врач-терапевт"),
        ),
    )

    service = PersonNormalizationService()
    candidate = service.normalize_row(row=row, profile=profile, import_run_id=42)

    assert candidate is not None
    assert candidate.import_run_id == 42
    assert candidate.profile_id == 10
    assert candidate.source_row_id == 100
    assert candidate.full_name.is_valid
    assert candidate.iin.digits == "900101300123"
    assert candidate.birth_date.value == date(1990, 3, 15)
    assert candidate.phone.digits == "77011234567"
    assert candidate.sex.code == "F"
    assert candidate.department_name.text == "Терапевтическое отделение"
    assert candidate.position_title.text == "Врач-терапевт"
    assert candidate.employment_mode == EMPLOYMENT_MODE_PRIMARY


def test_person_normalization_service_skips_non_data_rows_and_unknown_sheets():
    profile = _profile()
    service = PersonNormalizationService()

    header_row = StagingRowInput(
        row_id=1,
        sheet_name="врачи",
        excel_row_number=3,
        row_kind="header",
        cells=(),
    )
    assert service.normalize_row(row=header_row, profile=profile) is None

    unknown_sheet = StagingRowInput(
        row_id=2,
        sheet_name="декларация",
        excel_row_number=4,
        row_kind="data",
        cells=(),
    )
    assert service.normalize_row(row=unknown_sheet, profile=profile) is None


def test_person_normalization_service_flags_required_missing_fields():
    profile = _profile()
    row = StagingRowInput(
        row_id=200,
        sheet_name="врачи",
        excel_row_number=6,
        row_kind="data",
        cells=(
            StagingCellInput(column_index=2, raw_value="Петров Петр Петрович"),
        ),
    )

    candidate = PersonNormalizationService().normalize_row(row=row, profile=profile)
    assert candidate is not None
    assert "required_field_missing" in candidate.field_issues[SEMANTIC_FIELD_PERSON_IIN]


def test_person_normalization_service_normalize_run():
    profile = _profile()
    staging = StagingRunInput(
        import_run_id=7,
        sheets=(
            StagingSheetInput(
                sheet_name="врачи",
                rows=(
                    StagingRowInput(
                        row_id=1,
                        sheet_name="врачи",
                        excel_row_number=5,
                        row_kind="data",
                        cells=(
                            StagingCellInput(column_index=2, raw_value="Ахметов Болат Касымович"),
                            StagingCellInput(column_index=3, raw_value="900101300123"),
                        ),
                    ),
                    StagingRowInput(
                        row_id=2,
                        sheet_name="врачи",
                        excel_row_number=3,
                        row_kind="header",
                        cells=(),
                    ),
                ),
            ),
        ),
    )

    candidates = PersonNormalizationService().normalize_run(staging=staging, profile=profile)
    assert len(candidates) == 1
    assert candidates[0].full_name.display == "Ахметов Болат Касымович"
