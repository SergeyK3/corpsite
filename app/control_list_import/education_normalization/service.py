"""Education normalization service: staging + profile + match → EducationCandidate (WP-CL-008).

Pure in-memory transformation — no person_education database access or PPR writes.
"""
from __future__ import annotations

from typing import Any, Optional

from app.control_list_import.domain.education_candidate import (
    EducationCandidate,
    EducationReadinessStatus,
)
from app.control_list_import.domain.models import MappingProfileSnapshot
from app.control_list_import.domain.person_match_models import MatchReason, MatchStatus, PersonMatchResult
from app.control_list_import.domain.staging_models import StagingRowInput, StagingRunInput
from app.control_list_import.domain.vocabulary import (
    PARSER_CODE_RECORDS_EDUCATION,
    PARSER_CODE_TEXT_COMPOSITE_NUMBERED,
    PARSER_CODE_TEXT_PLAIN,
    SEMANTIC_FIELD_EDUCATION_RECORDS,
)
from app.control_list_import.education_normalization.records import (
    ParsedEducationRecord,
    is_technical_empty_education_cell,
    parse_education_fragment,
    split_education_fragments,
)

ROW_KIND_DATA = "data"

_EDUCATION_PARSERS = {
    PARSER_CODE_RECORDS_EDUCATION,
    PARSER_CODE_TEXT_COMPOSITE_NUMBERED,
    PARSER_CODE_TEXT_PLAIN,
}


def _matched_person_id(person_match: PersonMatchResult) -> Optional[int]:
    if person_match.status in {MatchStatus.EXACT, MatchStatus.PROBABLE}:
        return person_match.recommended_person_id
    return None


def _has_normalization_blocking_issues(field_issues: dict[str, tuple[str, ...]]) -> bool:
    blocking = {
        "education_fragment_incomplete",
        "education_fragment_unparsed",
        "education_graduation_year_out_of_range",
        "required_field_missing",
    }
    return any(issue in blocking for issues in field_issues.values() for issue in issues)


def _compute_readiness(
    *,
    person_match: PersonMatchResult,
    field_issues: dict[str, tuple[str, ...]],
) -> EducationReadinessStatus:
    if person_match.status == MatchStatus.INVALID:
        return EducationReadinessStatus.PERSON_MATCH_INVALID
    if person_match.status == MatchStatus.NOT_FOUND:
        return EducationReadinessStatus.PERSON_UNMATCHED
    if person_match.status == MatchStatus.AMBIGUOUS or person_match.recommended_person_id is None:
        return EducationReadinessStatus.REVIEW_REQUIRED
    if _has_normalization_blocking_issues(field_issues):
        return EducationReadinessStatus.REVIEW_REQUIRED
    return EducationReadinessStatus.NORMALIZATION_READY


class EducationNormalizationService:
    """Map staging rows and person match results into Education Candidate objects."""

    def normalize_row(
        self,
        *,
        row: StagingRowInput,
        profile: MappingProfileSnapshot,
        person_match: PersonMatchResult,
        import_run_id: Optional[int] = None,
    ) -> list[EducationCandidate]:
        if row.row_kind != ROW_KIND_DATA:
            return []

        profile_sheet = next((sheet for sheet in profile.sheets if sheet.sheet_name == row.sheet_name), None)
        if profile_sheet is None:
            return []

        education_columns = [
            column
            for column in profile_sheet.columns
            if column.semantic_field == SEMANTIC_FIELD_EDUCATION_RECORDS
            and column.parser_code in _EDUCATION_PARSERS
        ]
        if not education_columns:
            return []

        cell_values: dict[int, Any] = {cell.column_index: cell.raw_value for cell in row.cells}
        candidates: list[EducationCandidate] = []

        for column in education_columns:
            raw_value = cell_values.get(column.column_index)
            if raw_value is None or is_technical_empty_education_cell(raw_value):
                continue

            fragments = split_education_fragments(raw_value)
            if not fragments:
                continue

            for fragment_index, fragment in enumerate(fragments):
                parsed = parse_education_fragment(fragment, fragment_index=fragment_index)
                candidates.append(
                    self._build_candidate(
                        parsed=parsed,
                        row=row,
                        profile=profile,
                        person_match=person_match,
                        import_run_id=import_run_id,
                        column_index=column.column_index,
                        column_letter=column.column_letter,
                        field_issues=dict(parsed.field_issues),
                    )
                )

        return candidates

    def _build_candidate(
        self,
        *,
        parsed: ParsedEducationRecord,
        row: StagingRowInput,
        profile: MappingProfileSnapshot,
        person_match: PersonMatchResult,
        import_run_id: Optional[int],
        column_index: int,
        column_letter: str,
        field_issues: dict[str, tuple[str, ...]],
    ) -> EducationCandidate:
        readiness_status = _compute_readiness(
            person_match=person_match,
            field_issues=field_issues,
        )
        return EducationCandidate(
            import_run_id=import_run_id,
            profile_id=profile.profile_id,
            profile_code=profile.profile_code,
            profile_version=profile.profile_version,
            source_row_id=row.row_id,
            source_sheet_name=row.sheet_name,
            source_excel_row_number=row.excel_row_number,
            source_column_index=column_index,
            source_column_letter=column_letter,
            source_fragment_index=parsed.fragment_index,
            raw_fragment=parsed.raw_fragment,
            matched_person_id=_matched_person_id(person_match),
            institution_name=parsed.institution_name,
            qualification=parsed.qualification,
            specialty=parsed.specialty,
            graduation_year=parsed.graduation_year,
            education_level=parsed.education_level,
            document_number=parsed.document_number,
            field_issues=field_issues,
            readiness_status=readiness_status,
        )

    def normalize_run(
        self,
        *,
        staging: StagingRunInput,
        profile: MappingProfileSnapshot,
        person_matches: dict[int, PersonMatchResult],
    ) -> list[EducationCandidate]:
        candidates: list[EducationCandidate] = []
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
                candidates.extend(
                    self.normalize_row(
                        row=row,
                        profile=profile,
                        person_match=person_match,
                        import_run_id=staging.import_run_id,
                    )
                )
        return candidates
