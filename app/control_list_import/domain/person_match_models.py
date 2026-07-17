"""Person matching domain models (WP-CL-005).

Read-only matching results — no Person/PPR mutations.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Optional


class MatchStatus(StrEnum):
    EXACT = "exact"
    PROBABLE = "probable"
    AMBIGUOUS = "ambiguous"
    NOT_FOUND = "not_found"
    INVALID = "invalid"


class MatchReason(StrEnum):
    EXACT_IIN = "exact_iin"
    PROBABLE_FIO_BIRTH_DATE = "probable_fio_birth_date"
    WEAK_FIO_ONLY = "weak_fio_only"
    MULTIPLE_MATCHES = "multiple_matches"
    IIN_ATTRIBUTE_CONFLICT = "iin_attribute_conflict"
    NO_MATCH = "no_match"
    CANDIDATE_INCOMPLETE = "candidate_incomplete"


@dataclass(frozen=True, slots=True)
class PersonMatchCandidate:
    """One canonical Person hit for an import Person Candidate."""

    source_person_id: int
    resolved_person_id: int
    person_status: str
    full_name: str
    iin: Optional[str]
    birth_date: Optional[date]
    match_key: str
    merge_redirected: bool
    reason: MatchReason
    score: float
    confidence: float


@dataclass(frozen=True, slots=True)
class PersonMatchResult:
    """Matching outcome for one normalized Person Candidate."""

    import_run_id: Optional[int]
    source_row_id: Optional[int]
    status: MatchStatus
    match_candidates: tuple[PersonMatchCandidate, ...]
    primary_reason: MatchReason
    reasons: tuple[MatchReason, ...]
    confidence: float
    recommended_person_id: Optional[int]
