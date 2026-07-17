"""Other PPR normalization service: staging + profile + match → OtherPprCandidate (WP-CL-010).

Pure in-memory transformation — no canonical PPR database access or writes.
"""
from __future__ import annotations

from typing import Any, Optional

from app.control_list_import.domain.models import MappingProfileSnapshot
from app.control_list_import.domain.other_ppr_candidate import (
    NormalizedScalarValue,
    OtherPprCandidate,
    OtherPprReadinessStatus,
)
from app.control_list_import.domain.person_match_models import MatchReason, MatchStatus, PersonMatchResult
from app.control_list_import.domain.staging_models import StagingRowInput, StagingRunInput
from app.control_list_import.domain.vocabulary import (
    PARSER_CODE_PERSON_CITIZENSHIP,
    PARSER_CODE_PERSON_NATIONALITY,
    PARSER_CODE_PPR_DISABILITY_SUMMARY,
    PARSER_CODE_PPR_MARITAL_STATUS,
    PARSER_CODE_PPR_MILITARY_SUMMARY,
    PARSER_CODE_QUALIFICATION_CATEGORY,
    PARSER_CODE_QUALIFICATION_DEGREE,
    PARSER_CODE_TEXT_AWARDS,
    PARSER_CODE_TEXT_NOTES,
    PARSER_CODE_TEXT_PLAIN,
    SEMANTIC_FIELD_PERSON_AWARDS,
    SEMANTIC_FIELD_PERSON_CITIZENSHIP,
    SEMANTIC_FIELD_PERSON_NOTES,
    SEMANTIC_FIELD_PERSON_NATIONALITY_RAW,
    SEMANTIC_FIELD_PPR_DISABILITY_SUMMARY,
    SEMANTIC_FIELD_PPR_MARITAL_STATUS,
    SEMANTIC_FIELD_PPR_MILITARY_SUMMARY,
    SEMANTIC_FIELD_QUALIFICATION_CATEGORY,
    SEMANTIC_FIELD_QUALIFICATION_DEGREE,
)
from app.control_list_import.other_ppr_normalization.common import preserve_raw_value
from app.control_list_import.other_ppr_normalization.fields import (
    normalize_awards,
    normalize_citizenship,
    normalize_disability_summary,
    normalize_marital_status,
    normalize_military_summary,
    normalize_nationality_raw,
    normalize_notes,
    normalize_qualification_category,
    normalize_qualification_degree,
    normalize_unsupported_field,
)
from app.control_list_import.other_ppr_normalization.scope import (
    OTHER_PPR_EXCLUDED_FIELDS,
    OTHER_PPR_SUPPORTED_FIELDS,
)

ROW_KIND_DATA = "data"

_FIELD_NORMALIZERS = {
    SEMANTIC_FIELD_PERSON_CITIZENSHIP: normalize_citizenship,
    SEMANTIC_FIELD_PERSON_NATIONALITY_RAW: normalize_nationality_raw,
    SEMANTIC_FIELD_PPR_MARITAL_STATUS: normalize_marital_status,
    SEMANTIC_FIELD_PPR_MILITARY_SUMMARY: normalize_military_summary,
    SEMANTIC_FIELD_PPR_DISABILITY_SUMMARY: normalize_disability_summary,
    SEMANTIC_FIELD_PERSON_AWARDS: normalize_awards,
    SEMANTIC_FIELD_PERSON_NOTES: normalize_notes,
    SEMANTIC_FIELD_QUALIFICATION_CATEGORY: normalize_qualification_category,
    SEMANTIC_FIELD_QUALIFICATION_DEGREE: normalize_qualification_degree,
}

_SUPPORTED_PARSERS = {
    PARSER_CODE_TEXT_PLAIN,
    PARSER_CODE_PERSON_NATIONALITY,
    PARSER_CODE_PERSON_CITIZENSHIP,
    PARSER_CODE_TEXT_AWARDS,
    PARSER_CODE_TEXT_NOTES,
    PARSER_CODE_QUALIFICATION_CATEGORY,
    PARSER_CODE_QUALIFICATION_DEGREE,
    PARSER_CODE_PPR_MARITAL_STATUS,
    PARSER_CODE_PPR_MILITARY_SUMMARY,
    PARSER_CODE_PPR_DISABILITY_SUMMARY,
}


def _matched_person_id(person_match: PersonMatchResult) -> Optional[int]:
    if person_match.status in {MatchStatus.EXACT, MatchStatus.PROBABLE}:
        return person_match.recommended_person_id
    return None


def _normalize_field(semantic_field: str, value: Any) -> NormalizedScalarValue:
    normalizer = _FIELD_NORMALIZERS.get(semantic_field)
    if normalizer is None:
        return normalize_unsupported_field(value)
    return normalizer(value)


def _has_normalization_blocking_issues(
    *,
    semantic_field: str,
    field_issues: dict[str, tuple[str, ...]],
) -> bool:
    blocking = {
        "other_ppr_technical_empty",
        "other_ppr_empty_after_normalization",
        "other_ppr_citizenship_unmapped",
        "other_ppr_marital_status_unmapped",
        "other_ppr_military_summary_empty",
        "other_ppr_military_summary_unparsed",
        "other_ppr_disability_summary_unmapped",
        "other_ppr_unsupported_semantic_field",
        "required_field_missing",
    }
    ambiguous = {
        "other_ppr_citizenship_ambiguous",
        "other_ppr_marital_status_ambiguous",
        "other_ppr_military_summary_ambiguous",
        "other_ppr_disability_summary_ambiguous",
    }
    issues = field_issues.get(semantic_field, ())
    return any(issue in blocking or issue in ambiguous for issue in issues)


def _compute_readiness(
    *,
    person_match: PersonMatchResult,
    semantic_field: str,
    normalized_value: NormalizedScalarValue,
    field_issues: dict[str, tuple[str, ...]],
) -> OtherPprReadinessStatus:
    if person_match.status == MatchStatus.INVALID:
        return OtherPprReadinessStatus.PERSON_MATCH_INVALID
    if person_match.status == MatchStatus.NOT_FOUND:
        return OtherPprReadinessStatus.PERSON_UNMATCHED
    if person_match.status == MatchStatus.AMBIGUOUS or person_match.recommended_person_id is None:
        return OtherPprReadinessStatus.REVIEW_REQUIRED
    if not normalized_value.is_valid:
        return OtherPprReadinessStatus.REVIEW_REQUIRED
    if _has_normalization_blocking_issues(semantic_field=semantic_field, field_issues=field_issues):
        return OtherPprReadinessStatus.REVIEW_REQUIRED
    return OtherPprReadinessStatus.NORMALIZATION_READY


class OtherPprNormalizationService:
    """Map staging rows and person match results into Other PPR Candidate objects."""

    def normalize_row(
        self,
        *,
        row: StagingRowInput,
        profile: MappingProfileSnapshot,
        person_match: PersonMatchResult,
        import_run_id: Optional[int] = None,
    ) -> list[OtherPprCandidate]:
        if row.row_kind != ROW_KIND_DATA:
            return []

        profile_sheet = next((sheet for sheet in profile.sheets if sheet.sheet_name == row.sheet_name), None)
        if profile_sheet is None:
            return []

        cell_values: dict[int, Any] = {cell.column_index: cell.raw_value for cell in row.cells}
        candidates: list[OtherPprCandidate] = []

        for column in profile_sheet.columns:
            if column.semantic_field in OTHER_PPR_EXCLUDED_FIELDS:
                continue

            raw_value = cell_values.get(column.column_index)
            if raw_value is None or (isinstance(raw_value, str) and not raw_value.strip()):
                continue

            if column.semantic_field not in OTHER_PPR_SUPPORTED_FIELDS:
                if column.parser_code not in _SUPPORTED_PARSERS and column.parser_code != PARSER_CODE_TEXT_PLAIN:
                    continue
                normalized_value = normalize_unsupported_field(raw_value)
                field_issues = {column.semantic_field: normalized_value.issues}
                candidates.append(
                    self._build_candidate(
                        row=row,
                        profile=profile,
                        person_match=person_match,
                        import_run_id=import_run_id,
                        column_index=column.column_index,
                        column_letter=column.column_letter,
                        semantic_field=column.semantic_field,
                        raw_value=preserve_raw_value(raw_value),
                        normalized_value=normalized_value,
                        field_issues=field_issues,
                    )
                )
                continue

            if column.parser_code not in _SUPPORTED_PARSERS and column.parser_code != PARSER_CODE_TEXT_PLAIN:
                continue

            normalized_value = _normalize_field(column.semantic_field, raw_value)
            if "other_ppr_technical_empty" in normalized_value.issues:
                continue

            field_issues: dict[str, tuple[str, ...]] = {}
            if normalized_value.issues:
                field_issues[column.semantic_field] = normalized_value.issues

            candidates.append(
                self._build_candidate(
                    row=row,
                    profile=profile,
                    person_match=person_match,
                    import_run_id=import_run_id,
                    column_index=column.column_index,
                    column_letter=column.column_letter,
                    semantic_field=column.semantic_field,
                    raw_value=preserve_raw_value(raw_value),
                    normalized_value=normalized_value,
                    field_issues=field_issues,
                )
            )

        return candidates

    def _build_candidate(
        self,
        *,
        row: StagingRowInput,
        profile: MappingProfileSnapshot,
        person_match: PersonMatchResult,
        import_run_id: Optional[int],
        column_index: int,
        column_letter: str,
        semantic_field: str,
        raw_value: str,
        normalized_value: NormalizedScalarValue,
        field_issues: dict[str, tuple[str, ...]],
    ) -> OtherPprCandidate:
        readiness_status = _compute_readiness(
            person_match=person_match,
            semantic_field=semantic_field,
            normalized_value=normalized_value,
            field_issues=field_issues,
        )
        return OtherPprCandidate(
            import_run_id=import_run_id,
            profile_id=profile.profile_id,
            profile_code=profile.profile_code,
            profile_version=profile.profile_version,
            source_row_id=row.row_id,
            source_sheet_name=row.sheet_name,
            source_excel_row_number=row.excel_row_number,
            source_column_index=column_index,
            source_column_letter=column_letter,
            semantic_field=semantic_field,
            raw_value=raw_value,
            normalized_value=normalized_value,
            matched_person_id=_matched_person_id(person_match),
            field_issues=field_issues,
            readiness_status=readiness_status,
        )

    def normalize_run(
        self,
        *,
        staging: StagingRunInput,
        profile: MappingProfileSnapshot,
        person_matches: dict[int, PersonMatchResult],
    ) -> list[OtherPprCandidate]:
        candidates: list[OtherPprCandidate] = []
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
