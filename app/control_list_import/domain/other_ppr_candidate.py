"""Other PPR field Candidate domain model (WP-CL-010).

Temporary normalized slices for PPR fields not covered by WP-CL-004…009.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Optional

from app.control_list_import.domain.person_candidate import NormalizedField


class OtherPprReadinessStatus(StrEnum):
    """Normalization-layer readiness — does not authorize PPR writes."""

    NORMALIZATION_READY = "normalization_ready"
    REVIEW_REQUIRED = "review_required"
    PERSON_UNMATCHED = "person_unmatched"
    PERSON_MATCH_INVALID = "person_match_invalid"


@dataclass(frozen=True)
class NormalizedScalarValue(NormalizedField):
    """Normalized scalar with optional controlled-vocabulary code."""

    text: Optional[str] = None
    code: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        return (self.text is not None or self.code is not None) and not self.has_issues


@dataclass(frozen=True)
class OtherPprCandidate:
    """Temporary normalized PPR field slice from one staging cell."""

    import_run_id: Optional[int]
    profile_id: Optional[int]
    profile_code: Optional[str]
    profile_version: Optional[int]
    source_row_id: Optional[int]
    source_sheet_name: str
    source_excel_row_number: int
    source_column_index: int
    source_column_letter: str
    semantic_field: str
    raw_value: str
    normalized_value: NormalizedScalarValue
    matched_person_id: Optional[int]
    field_issues: dict[str, tuple[str, ...]] = field(default_factory=dict)
    readiness_status: OtherPprReadinessStatus = OtherPprReadinessStatus.REVIEW_REQUIRED

    @property
    def is_normalization_ready(self) -> bool:
        """True when person is matched/recommended and field normalized cleanly.

        Does not authorize merge/update of canonical PPR — downstream WP only.
        """
        return self.readiness_status == OtherPprReadinessStatus.NORMALIZATION_READY

    @property
    def all_issues(self) -> tuple[str, ...]:
        seen: list[str] = []
        for issues in self.field_issues.values():
            for issue in issues:
                if issue not in seen:
                    seen.append(issue)
        return tuple(seen)
