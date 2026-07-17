"""Training Candidate domain model (WP-CL-009).

Temporary normalized training slice — not canonical person_training record.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Optional

from app.control_list_import.domain.person_candidate import NormalizedField, NormalizedPlainText


class TrainingReadinessStatus(StrEnum):
    """Normalization-layer readiness — does not authorize PPR training writes."""

    NORMALIZATION_READY = "normalization_ready"
    REVIEW_REQUIRED = "review_required"
    PERSON_UNMATCHED = "person_unmatched"
    PERSON_MATCH_INVALID = "person_match_invalid"


@dataclass(frozen=True)
class NormalizedCompletionDate(NormalizedField):
    value: Optional[date] = None

    @property
    def is_valid(self) -> bool:
        return self.value is not None and not self.has_issues


@dataclass(frozen=True)
class NormalizedCompletionYear(NormalizedField):
    value: Optional[int] = None

    @property
    def is_valid(self) -> bool:
        return self.value is not None and not self.has_issues


@dataclass(frozen=True)
class NormalizedDurationHours(NormalizedField):
    value: Optional[Decimal] = None

    @property
    def is_valid(self) -> bool:
        return self.value is not None and not self.has_issues


@dataclass(frozen=True)
class TrainingCandidate:
    """Temporary normalized training record from one staging cell fragment."""

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
    training_title: NormalizedPlainText
    provider_name: NormalizedPlainText
    completion_date: NormalizedCompletionDate
    completion_year: NormalizedCompletionYear
    certificate_number: NormalizedPlainText
    duration_hours: NormalizedDurationHours
    training_type: NormalizedPlainText
    field_issues: dict[str, tuple[str, ...]] = field(default_factory=dict)
    readiness_status: TrainingReadinessStatus = TrainingReadinessStatus.REVIEW_REQUIRED

    @property
    def is_normalization_ready(self) -> bool:
        """True when person is matched/recommended and training fragment normalized cleanly.

        Does not authorize merge/update of canonical person_training — downstream WP only.
        """
        return self.readiness_status == TrainingReadinessStatus.NORMALIZATION_READY

    @property
    def all_issues(self) -> tuple[str, ...]:
        seen: list[str] = []
        for issues in self.field_issues.values():
            for issue in issues:
                if issue not in seen:
                    seen.append(issue)
        return tuple(seen)
