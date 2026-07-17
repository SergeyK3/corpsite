"""Input bundle for review assembly (WP-CL-011)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.control_list_import.domain.contact_candidate import ContactCandidate
from app.control_list_import.domain.education_candidate import EducationCandidate
from app.control_list_import.domain.employment_candidate import EmploymentCandidate
from app.control_list_import.domain.other_ppr_candidate import OtherPprCandidate
from app.control_list_import.domain.person_candidate import PersonCandidate
from app.control_list_import.domain.person_match_models import PersonMatchResult
from app.control_list_import.domain.training_candidate import TrainingCandidate


@dataclass(frozen=True, slots=True)
class NormalizationRunBundle:
    """Normalization + matching outputs keyed by ``source_row_id``."""

    import_run_id: Optional[int]
    profile_id: Optional[int]
    profile_code: Optional[str]
    profile_version: Optional[int]
    person_candidates: dict[int, PersonCandidate]
    person_matches: dict[int, PersonMatchResult]
    employment_candidates: dict[int, EmploymentCandidate | None]
    contact_candidates: dict[int, ContactCandidate | None]
    education_candidates: dict[int, list[EducationCandidate]]
    training_candidates: dict[int, list[TrainingCandidate]]
    other_ppr_candidates: dict[int, list[OtherPprCandidate]]

    def source_row_ids(self) -> tuple[int, ...]:
        keys: set[int] = set()
        keys.update(self.person_candidates)
        keys.update(self.person_matches)
        keys.update(self.employment_candidates)
        keys.update(self.contact_candidates)
        keys.update(self.education_candidates)
        keys.update(self.training_candidates)
        keys.update(self.other_ppr_candidates)
        return tuple(sorted(keys))
