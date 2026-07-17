"""Employment normalization service: staging + profile + match → EmploymentCandidate (WP-CL-006).

Pure in-memory transformation — no Employment/PPR database access or org/position lookup.
"""
from __future__ import annotations

from typing import Any, Optional

from app.control_list_import.domain.employment_candidate import (
    EmploymentCandidate,
    EmploymentReadinessStatus,
    NormalizedEmploymentStartDate,
    NormalizedRate,
)
from app.control_list_import.domain.models import MappingProfileSnapshot
from app.control_list_import.domain.person_candidate import NormalizedField, NormalizedPlainText
from app.control_list_import.domain.person_match_models import MatchReason, MatchStatus, PersonMatchResult
from app.control_list_import.domain.staging_models import StagingRowInput, StagingRunInput
from app.control_list_import.domain.vocabulary import (
    PARSER_CODE_DATE_EXCEL_SERIAL,
    PARSER_CODE_DATE_TEXT,
    PARSER_CODE_EMPLOYMENT_DEPARTMENT,
    PARSER_CODE_EMPLOYMENT_POSITION,
    PARSER_CODE_EMPLOYMENT_RATE,
    PARSER_CODE_EMPLOYMENT_STARTED_AT,
    PARSER_CODE_TEXT_PLAIN,
    SEMANTIC_FIELD_EMPLOYMENT_DEPARTMENT_NAME,
    SEMANTIC_FIELD_EMPLOYMENT_POSITION_TITLE,
    SEMANTIC_FIELD_EMPLOYMENT_RATE,
    SEMANTIC_FIELD_EMPLOYMENT_STARTED_AT,
)
from app.control_list_import.employment_normalization.department import normalize_department_name
from app.control_list_import.employment_normalization.mode import normalize_employment_mode
from app.control_list_import.employment_normalization.position import normalize_position_title
from app.control_list_import.employment_normalization.rate import normalize_employment_rate
from app.control_list_import.employment_normalization.start_date import normalize_employment_start_date

ROW_KIND_DATA = "data"

_EMPLOYMENT_SEMANTIC_FIELDS = (
    SEMANTIC_FIELD_EMPLOYMENT_DEPARTMENT_NAME,
    SEMANTIC_FIELD_EMPLOYMENT_POSITION_TITLE,
    SEMANTIC_FIELD_EMPLOYMENT_RATE,
    SEMANTIC_FIELD_EMPLOYMENT_STARTED_AT,
)


def _empty_department() -> NormalizedPlainText:
    return NormalizedPlainText(raw=None)


def _empty_position() -> NormalizedPlainText:
    return NormalizedPlainText(raw=None)


def _empty_rate() -> NormalizedRate:
    return NormalizedRate(raw=None)


def _empty_start_date() -> NormalizedEmploymentStartDate:
    return NormalizedEmploymentStartDate(raw=None)


def _normalize_by_parser(parser_code: str, semantic_field: str, value: Any) -> NormalizedField:
    if parser_code in {PARSER_CODE_EMPLOYMENT_DEPARTMENT, PARSER_CODE_TEXT_PLAIN} and semantic_field == SEMANTIC_FIELD_EMPLOYMENT_DEPARTMENT_NAME:
        return normalize_department_name(value)
    if parser_code in {PARSER_CODE_EMPLOYMENT_POSITION, PARSER_CODE_TEXT_PLAIN} and semantic_field == SEMANTIC_FIELD_EMPLOYMENT_POSITION_TITLE:
        return normalize_position_title(value)
    if parser_code == PARSER_CODE_EMPLOYMENT_RATE or semantic_field == SEMANTIC_FIELD_EMPLOYMENT_RATE:
        return normalize_employment_rate(value)
    if parser_code in {PARSER_CODE_EMPLOYMENT_STARTED_AT, PARSER_CODE_DATE_TEXT, PARSER_CODE_DATE_EXCEL_SERIAL} or semantic_field == SEMANTIC_FIELD_EMPLOYMENT_STARTED_AT:
        return normalize_employment_start_date(value)
    return normalize_department_name(value)


def _matched_person_id(person_match: PersonMatchResult) -> Optional[int]:
    if person_match.status in {MatchStatus.EXACT, MatchStatus.PROBABLE}:
        return person_match.recommended_person_id
    return None


def _append_issues(
    field_issues: dict[str, tuple[str, ...]],
    semantic_field: str,
    issues: tuple[str, ...],
) -> None:
    if not issues:
        return
    existing = field_issues.get(semantic_field, ())
    field_issues[semantic_field] = tuple(dict.fromkeys(existing + issues))


def _collect_structural_issues(
    *,
    department_name: NormalizedPlainText,
    position_title: NormalizedPlainText,
    rate: NormalizedRate,
    field_issues: dict[str, tuple[str, ...]],
) -> None:
    if department_name.is_empty:
        _append_issues(field_issues, SEMANTIC_FIELD_EMPLOYMENT_DEPARTMENT_NAME, ("employment_department_missing",))
    if position_title.is_empty:
        _append_issues(field_issues, SEMANTIC_FIELD_EMPLOYMENT_POSITION_TITLE, ("employment_position_missing",))
    if not rate.is_empty and not rate.is_valid:
        _append_issues(field_issues, SEMANTIC_FIELD_EMPLOYMENT_RATE, rate.issues)


def _compute_readiness(
    *,
    person_match: PersonMatchResult,
    field_issues: dict[str, tuple[str, ...]],
) -> EmploymentReadinessStatus:
    if person_match.status == MatchStatus.INVALID:
        return EmploymentReadinessStatus.PERSON_MATCH_INVALID
    if person_match.status == MatchStatus.NOT_FOUND:
        return EmploymentReadinessStatus.PERSON_UNMATCHED
    if person_match.status == MatchStatus.AMBIGUOUS or person_match.recommended_person_id is None:
        return EmploymentReadinessStatus.REVIEW_REQUIRED
    if _has_normalization_blocking_issues(field_issues):
        return EmploymentReadinessStatus.REVIEW_REQUIRED
    return EmploymentReadinessStatus.NORMALIZATION_READY


def _has_normalization_blocking_issues(field_issues: dict[str, tuple[str, ...]]) -> bool:
    blocking = {
        "employment_department_missing",
        "employment_position_missing",
        "employment_rate_unrecognized_format",
        "employment_rate_out_of_range",
        "required_field_missing",
    }
    return any(issue in blocking for issues in field_issues.values() for issue in issues)


class EmploymentNormalizationService:
    """Map staging rows and person match results into Employment Candidate objects."""

    def normalize_row(
        self,
        *,
        row: StagingRowInput,
        profile: MappingProfileSnapshot,
        person_match: PersonMatchResult,
        import_run_id: Optional[int] = None,
    ) -> Optional[EmploymentCandidate]:
        if row.row_kind != ROW_KIND_DATA:
            return None

        profile_sheet = next((sheet for sheet in profile.sheets if sheet.sheet_name == row.sheet_name), None)
        if profile_sheet is None:
            return None

        employment_mode, mode_issues = normalize_employment_mode(profile_sheet.employment_mode)
        cell_values: dict[int, Any] = {cell.column_index: cell.raw_value for cell in row.cells}

        fields: dict[str, NormalizedField] = {
            SEMANTIC_FIELD_EMPLOYMENT_DEPARTMENT_NAME: _empty_department(),
            SEMANTIC_FIELD_EMPLOYMENT_POSITION_TITLE: _empty_position(),
            SEMANTIC_FIELD_EMPLOYMENT_RATE: _empty_rate(),
            SEMANTIC_FIELD_EMPLOYMENT_STARTED_AT: _empty_start_date(),
        }
        field_issues: dict[str, tuple[str, ...]] = {}
        if mode_issues:
            field_issues["employment.mode"] = mode_issues

        for column in profile_sheet.columns:
            if column.semantic_field not in _EMPLOYMENT_SEMANTIC_FIELDS:
                continue

            raw_value = cell_values.get(column.column_index)
            if raw_value is None or (isinstance(raw_value, str) and not raw_value.strip()):
                if column.is_required:
                    _append_issues(field_issues, column.semantic_field, ("required_field_missing",))
                continue

            normalized = _normalize_by_parser(column.parser_code, column.semantic_field, raw_value)
            fields[column.semantic_field] = normalized
            if normalized.issues:
                _append_issues(field_issues, column.semantic_field, normalized.issues)

        for column in profile_sheet.columns:
            if column.semantic_field not in _EMPLOYMENT_SEMANTIC_FIELDS or not column.is_required:
                continue
            if column.semantic_field not in field_issues and fields[column.semantic_field].is_empty:
                _append_issues(field_issues, column.semantic_field, ("required_field_missing",))

        department_name = fields[SEMANTIC_FIELD_EMPLOYMENT_DEPARTMENT_NAME]  # type: ignore[assignment]
        position_title = fields[SEMANTIC_FIELD_EMPLOYMENT_POSITION_TITLE]  # type: ignore[assignment]
        rate = fields[SEMANTIC_FIELD_EMPLOYMENT_RATE]  # type: ignore[assignment]

        _collect_structural_issues(
            department_name=department_name,
            position_title=position_title,
            rate=rate,
            field_issues=field_issues,
        )

        readiness_status = _compute_readiness(
            person_match=person_match,
            field_issues=field_issues,
        )

        return EmploymentCandidate(
            import_run_id=import_run_id,
            profile_id=profile.profile_id,
            profile_code=profile.profile_code,
            profile_version=profile.profile_version,
            source_row_id=row.row_id,
            source_sheet_name=row.sheet_name,
            source_excel_row_number=row.excel_row_number,
            matched_person_id=_matched_person_id(person_match),
            personnel_category=profile_sheet.personnel_category,
            employment_mode=employment_mode,
            department_name=department_name,
            position_title=position_title,
            rate=rate,
            employment_start_date=fields[SEMANTIC_FIELD_EMPLOYMENT_STARTED_AT],  # type: ignore[assignment]
            field_issues=field_issues,
            readiness_status=readiness_status,
        )

    def normalize_run(
        self,
        *,
        staging: StagingRunInput,
        profile: MappingProfileSnapshot,
        person_matches: dict[int, PersonMatchResult],
    ) -> list[EmploymentCandidate]:
        candidates: list[EmploymentCandidate] = []
        for sheet in staging.sheets:
            for row in sheet.rows:
                person_match = person_matches.get(
                    row.row_id,
                    PersonMatchResult(
                        import_run_id=staging.import_run_id,
                        source_row_id=row.row_id,
                        status=MatchStatus.NOT_FOUND,
                        match_candidates=(),
                        primary_reason=MatchReason.NO_MATCH,
                        reasons=(MatchReason.NO_MATCH,),
                        confidence=0.0,
                        recommended_person_id=None,
                    ),
                )
                candidate = self.normalize_row(
                    row=row,
                    profile=profile,
                    person_match=person_match,
                    import_run_id=staging.import_run_id,
                )
                if candidate is not None:
                    candidates.append(candidate)
        return candidates
