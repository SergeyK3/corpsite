"""Provenance validation helpers for review assembly (WP-CL-011)."""
from __future__ import annotations

from typing import Optional, TypeVar

from app.control_list_import.domain.contact_candidate import ContactCandidate
from app.control_list_import.domain.education_candidate import EducationCandidate
from app.control_list_import.domain.employment_candidate import EmploymentCandidate
from app.control_list_import.domain.other_ppr_candidate import OtherPprCandidate
from app.control_list_import.domain.person_candidate import PersonCandidate
from app.control_list_import.domain.person_match_models import PersonMatchResult
from app.control_list_import.domain.training_candidate import TrainingCandidate

T = TypeVar("T")


def candidate_matches_row(candidate: object | None, source_row_id: int) -> bool:
    if candidate is None:
        return True
    row_id = getattr(candidate, "source_row_id", None)
    return row_id is None or row_id == source_row_id


def filter_optional_candidate(
    candidate: Optional[T],
    *,
    source_row_id: int,
) -> Optional[T]:
    if candidate is None:
        return None
    if not candidate_matches_row(candidate, source_row_id):
        return None
    return candidate


def filter_candidate_list(
    candidates: list[T],
    *,
    source_row_id: int,
) -> tuple[T, ...]:
    return tuple(
        candidate
        for candidate in candidates
        if candidate_matches_row(candidate, source_row_id)
    )


def person_match_matches_row(
    person_match: Optional[PersonMatchResult],
    *,
    source_row_id: int,
) -> Optional[PersonMatchResult]:
    if person_match is None:
        return None
    if person_match.source_row_id is not None and person_match.source_row_id != source_row_id:
        return None
    return person_match


def person_candidate_matches_row(
    person_candidate: Optional[PersonCandidate],
    *,
    source_row_id: int,
) -> Optional[PersonCandidate]:
    return filter_optional_candidate(person_candidate, source_row_id=source_row_id)
