"""Employment Candidate domain model (WP-CL-006).

Temporary normalized employment slice — not canonical Employment or assignment.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Optional

from app.control_list_import.domain.person_candidate import NormalizedField, NormalizedPlainText


class EmploymentReadinessStatus(StrEnum):
    """Normalization-layer readiness — does not authorize Employment BC apply."""

    NORMALIZATION_READY = "normalization_ready"
    REVIEW_REQUIRED = "review_required"
    PERSON_UNMATCHED = "person_unmatched"
    PERSON_MATCH_INVALID = "person_match_invalid"


@dataclass(frozen=True)
class NormalizedRate(NormalizedField):
    value: Optional[Decimal] = None

    @property
    def is_valid(self) -> bool:
        return self.value is not None and not self.has_issues


@dataclass(frozen=True)
class NormalizedEmploymentStartDate(NormalizedField):
    value: Optional[date] = None

    @property
    def is_valid(self) -> bool:
        return self.value is not None and not self.has_issues


@dataclass(frozen=True)
class EmploymentCandidate:
    """Temporary normalized employment slice from one staging data row."""

    import_run_id: Optional[int]
    profile_id: Optional[int]
    profile_code: Optional[str]
    profile_version: Optional[int]
    source_row_id: Optional[int]
    source_sheet_name: str
    source_excel_row_number: int
    matched_person_id: Optional[int]
    personnel_category: str
    employment_mode: str
    department_name: NormalizedPlainText
    position_title: NormalizedPlainText
    rate: NormalizedRate
    employment_start_date: NormalizedEmploymentStartDate
    field_issues: dict[str, tuple[str, ...]] = field(default_factory=dict)
    readiness_status: EmploymentReadinessStatus = EmploymentReadinessStatus.REVIEW_REQUIRED

    @property
    def is_normalization_ready(self) -> bool:
        """True when person is matched/recommended and source employment fields normalized cleanly.

        Does not authorize apply in Employment BC — OrgUnit/Position resolution and conflict
        checks happen in downstream WP.
        """
        return self.readiness_status == EmploymentReadinessStatus.NORMALIZATION_READY

    @property
    def all_issues(self) -> tuple[str, ...]:
        seen: list[str] = []
        for issues in self.field_issues.values():
            for issue in issues:
                if issue not in seen:
                    seen.append(issue)
        return tuple(seen)
