"""Education Candidate domain model (WP-CL-008).

Temporary normalized education slice — not canonical person_education record.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Optional

from app.control_list_import.domain.person_candidate import NormalizedField, NormalizedPlainText


class EducationReadinessStatus(StrEnum):
    """Normalization-layer readiness — does not authorize PPR education writes."""

    NORMALIZATION_READY = "normalization_ready"
    REVIEW_REQUIRED = "review_required"
    PERSON_UNMATCHED = "person_unmatched"
    PERSON_MATCH_INVALID = "person_match_invalid"


@dataclass(frozen=True)
class NormalizedGraduationYear(NormalizedField):
    value: Optional[int] = None

    @property
    def is_valid(self) -> bool:
        return self.value is not None and not self.has_issues


@dataclass(frozen=True)
class EducationCandidate:
    """Temporary normalized education record from one staging cell fragment."""

    import_run_id: Optional[int]
    profile_id: Optional[int]
    profile_code: Optional[str]
    profile_version: Optional[int]
    source_row_id: Optional[int]
    source_sheet_name: str
    source_excel_row_number: int
    source_column_index: int
    source_column_letter: str
    source_fragment_index: int
    raw_fragment: str
    matched_person_id: Optional[int]
    institution_name: NormalizedPlainText
    qualification: NormalizedPlainText
    specialty: NormalizedPlainText
    graduation_year: NormalizedGraduationYear
    education_level: NormalizedPlainText
    document_number: NormalizedPlainText
    field_issues: dict[str, tuple[str, ...]] = field(default_factory=dict)
    readiness_status: EducationReadinessStatus = EducationReadinessStatus.REVIEW_REQUIRED

    @property
    def is_normalization_ready(self) -> bool:
        """True when person is matched/recommended and education fragment normalized cleanly.

        Does not authorize merge/update of canonical person_education — downstream WP only.
        """
        return self.readiness_status == EducationReadinessStatus.NORMALIZATION_READY

    @property
    def all_issues(self) -> tuple[str, ...]:
        seen: list[str] = []
        for issues in self.field_issues.values():
            for issue in issues:
                if issue not in seen:
                    seen.append(issue)
        return tuple(seen)
