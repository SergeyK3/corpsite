"""Person normalization service: staging + mapping profile → Person Candidate (WP-CL-004).

Pure in-memory transformation — no PPR database access and no person matching.
"""
from __future__ import annotations

from typing import Any, Optional

from app.control_list_import.domain.models import MappingProfileSnapshot
from app.control_list_import.domain.person_candidate import (
    NormalizedBirthDate,
    NormalizedField,
    NormalizedFullName,
    NormalizedIin,
    NormalizedPhone,
    NormalizedPlainText,
    NormalizedSex,
    PersonCandidate,
)
from app.control_list_import.domain.staging_models import StagingRowInput, StagingRunInput
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
from app.control_list_import.normalization.sex import normalize_sex
from app.control_list_import.normalization.strings import normalize_plain_string

ROW_KIND_DATA = "data"


def _empty_full_name() -> NormalizedFullName:
    return NormalizedFullName(raw=None)


def _empty_iin() -> NormalizedIin:
    return NormalizedIin(raw=None)


def _empty_birth_date() -> NormalizedBirthDate:
    return NormalizedBirthDate(raw=None)


def _empty_phone() -> NormalizedPhone:
    return NormalizedPhone(raw=None)


def _empty_sex() -> NormalizedSex:
    return NormalizedSex(raw=None)


def _empty_plain_text() -> NormalizedPlainText:
    return NormalizedPlainText(raw=None)


def _normalize_plain_text(value: Any) -> NormalizedPlainText:
    raw = value if value is None or isinstance(value, str) else str(value)
    text, issues = normalize_plain_string(value)
    raw_text = raw.strip() if isinstance(raw, str) and raw.strip() else None
    return NormalizedPlainText(raw=raw_text, text=text, issues=issues)


def _normalize_by_parser(parser_code: str, semantic_field: str, value: Any) -> NormalizedField:
    if parser_code == PARSER_CODE_PERSON_FULL_NAME or semantic_field == SEMANTIC_FIELD_PERSON_FULL_NAME:
        return normalize_full_name(value)
    if parser_code == PARSER_CODE_IDENTITY_IIN or semantic_field == SEMANTIC_FIELD_PERSON_IIN:
        return normalize_iin(value)
    if parser_code in {PARSER_CODE_DATE_TEXT, PARSER_CODE_DATE_EXCEL_SERIAL} or semantic_field == SEMANTIC_FIELD_PERSON_BIRTH_DATE:
        return normalize_birth_date(value)
    if parser_code == PARSER_CODE_IDENTITY_PHONE or semantic_field == SEMANTIC_FIELD_PERSON_PHONE:
        return normalize_phone(value)
    if parser_code == PARSER_CODE_PERSON_SEX or semantic_field == SEMANTIC_FIELD_PERSON_SEX:
        return normalize_sex(value)
    if parser_code in {PARSER_CODE_EMPLOYMENT_DEPARTMENT, PARSER_CODE_TEXT_PLAIN} and semantic_field == SEMANTIC_FIELD_EMPLOYMENT_DEPARTMENT_NAME:
        return _normalize_plain_text(value)
    if parser_code in {PARSER_CODE_EMPLOYMENT_POSITION, PARSER_CODE_TEXT_PLAIN} and semantic_field == SEMANTIC_FIELD_EMPLOYMENT_POSITION_TITLE:
        return _normalize_plain_text(value)
    return _normalize_plain_text(value)


class PersonNormalizationService:
    """Map staging rows through a mapping profile into Person Candidate objects."""

    def normalize_row(
        self,
        *,
        row: StagingRowInput,
        profile: MappingProfileSnapshot,
        import_run_id: Optional[int] = None,
    ) -> Optional[PersonCandidate]:
        if row.row_kind != ROW_KIND_DATA:
            return None

        profile_sheet = next((sheet for sheet in profile.sheets if sheet.sheet_name == row.sheet_name), None)
        if profile_sheet is None:
            return None

        cell_values: dict[int, Any] = {cell.column_index: cell.raw_value for cell in row.cells}

        fields: dict[str, NormalizedField] = {
            SEMANTIC_FIELD_PERSON_FULL_NAME: _empty_full_name(),
            SEMANTIC_FIELD_PERSON_IIN: _empty_iin(),
            SEMANTIC_FIELD_PERSON_BIRTH_DATE: _empty_birth_date(),
            SEMANTIC_FIELD_PERSON_PHONE: _empty_phone(),
            SEMANTIC_FIELD_PERSON_SEX: _empty_sex(),
            SEMANTIC_FIELD_EMPLOYMENT_DEPARTMENT_NAME: _empty_plain_text(),
            SEMANTIC_FIELD_EMPLOYMENT_POSITION_TITLE: _empty_plain_text(),
        }

        field_issues: dict[str, tuple[str, ...]] = {}

        for column in profile_sheet.columns:
            raw_value = cell_values.get(column.column_index)
            if raw_value is None or (isinstance(raw_value, str) and not raw_value.strip()):
                if column.is_required:
                    field_issues[column.semantic_field] = field_issues.get(column.semantic_field, ()) + (
                        "required_field_missing",
                    )
                continue

            normalized = _normalize_by_parser(column.parser_code, column.semantic_field, raw_value)
            fields[column.semantic_field] = normalized
            if normalized.issues:
                existing = field_issues.get(column.semantic_field, ())
                field_issues[column.semantic_field] = tuple(dict.fromkeys(existing + normalized.issues))

        for column in profile_sheet.columns:
            if column.is_required and column.semantic_field not in field_issues:
                current = fields[column.semantic_field]
                if current.is_empty:
                    field_issues[column.semantic_field] = field_issues.get(column.semantic_field, ()) + (
                        "required_field_missing",
                    )

        return PersonCandidate(
            import_run_id=import_run_id,
            profile_id=profile.profile_id,
            profile_code=profile.profile_code,
            profile_version=profile.profile_version,
            source_row_id=row.row_id,
            source_sheet_name=row.sheet_name,
            source_excel_row_number=row.excel_row_number,
            personnel_category=profile_sheet.personnel_category,
            employment_mode=profile_sheet.employment_mode,
            full_name=fields[SEMANTIC_FIELD_PERSON_FULL_NAME],  # type: ignore[assignment]
            iin=fields[SEMANTIC_FIELD_PERSON_IIN],  # type: ignore[assignment]
            birth_date=fields[SEMANTIC_FIELD_PERSON_BIRTH_DATE],  # type: ignore[assignment]
            phone=fields[SEMANTIC_FIELD_PERSON_PHONE],  # type: ignore[assignment]
            sex=fields[SEMANTIC_FIELD_PERSON_SEX],  # type: ignore[assignment]
            department_name=fields[SEMANTIC_FIELD_EMPLOYMENT_DEPARTMENT_NAME],  # type: ignore[assignment]
            position_title=fields[SEMANTIC_FIELD_EMPLOYMENT_POSITION_TITLE],  # type: ignore[assignment]
            field_issues=field_issues,
        )

    def normalize_run(
        self,
        *,
        staging: StagingRunInput,
        profile: MappingProfileSnapshot,
    ) -> list[PersonCandidate]:
        candidates: list[PersonCandidate] = []
        for sheet in staging.sheets:
            for row in sheet.rows:
                candidate = self.normalize_row(
                    row=row,
                    profile=profile,
                    import_run_id=staging.import_run_id,
                )
                if candidate is not None:
                    candidates.append(candidate)
        return candidates
