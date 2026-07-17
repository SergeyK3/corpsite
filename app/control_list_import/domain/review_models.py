"""Review aggregate domain models (WP-CL-011).

Review items assemble normalization + matching outcomes for operator preview.
They are **not** canonical PPR/Employment data and do not authorize mutation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Optional

from app.control_list_import.domain.contact_candidate import ContactCandidate
from app.control_list_import.domain.education_candidate import EducationCandidate
from app.control_list_import.domain.employment_candidate import EmploymentCandidate
from app.control_list_import.domain.other_ppr_candidate import OtherPprCandidate
from app.control_list_import.domain.person_candidate import PersonCandidate
from app.control_list_import.domain.person_match_models import PersonMatchResult
from app.control_list_import.domain.training_candidate import TrainingCandidate


class ReviewStatus(StrEnum):
    """Aggregate readiness for a review item — distinct from user ReviewDecision."""

    BLOCKED = "blocked"
    NEEDS_REVIEW = "needs_review"
    READY = "ready"


class ReviewDecision(StrEnum):
    """Operator decision on a review item — does not execute apply."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_CORRECTION = "needs_correction"


class ApplyActionType(StrEnum):
    """Declarative apply action kinds — execution deferred to a later WP."""

    CREATE_PERSON = "create_person"
    UPDATE_PERSON_CONTACT = "update_person_contact"
    # Reserved for explicit external-employment biography sources — not generated from WP-CL-006.
    CREATE_EXTERNAL_EMPLOYMENT = "create_external_employment"
    RESOLVE_ASSIGNMENT = "resolve_assignment"
    ADD_EDUCATION = "add_education"
    ADD_TRAINING = "add_training"
    UPDATE_OTHER_PPR_FIELD = "update_other_ppr_field"
    SKIP = "skip"


@dataclass(frozen=True, slots=True)
class BlockingIssueSummary:
    """One aggregated issue on a review item."""

    code: str
    source: str
    message: str
    blocking: bool = True


@dataclass(frozen=True, slots=True)
class ApplyAction:
    """Single declarative apply step — immutable plan entry, not an executed mutation."""

    action_type: ApplyActionType
    target_aggregate: str
    source_candidate_ref: str
    preconditions: tuple[str, ...]
    idempotency_key: str
    is_ready: bool
    blocking_reason: Optional[str] = None


@dataclass(frozen=True, slots=True)
class ApplyPlan:
    """Declarative apply plan for one review item — immutable, no side effects."""

    import_run_id: Optional[int]
    source_row_id: Optional[int]
    decision: ReviewDecision
    actions: tuple[ApplyAction, ...]
    is_executable: bool
    blocking_reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ControlListReviewItem:
    """One source staging row assembled into a review aggregate."""

    import_run_id: Optional[int]
    profile_id: Optional[int]
    profile_code: Optional[str]
    profile_version: Optional[int]
    source_row_id: Optional[int]
    source_sheet_name: str
    source_excel_row_number: int
    person_candidate: Optional[PersonCandidate]
    person_match: Optional[PersonMatchResult]
    employment_candidate: Optional[EmploymentCandidate]
    contact_candidate: Optional[ContactCandidate]
    education_candidates: tuple[EducationCandidate, ...] = ()
    training_candidates: tuple[TrainingCandidate, ...] = ()
    other_ppr_candidates: tuple[OtherPprCandidate, ...] = ()
    blocking_issues: tuple[BlockingIssueSummary, ...] = ()
    non_blocking_issues: tuple[BlockingIssueSummary, ...] = ()
    readiness_status: ReviewStatus = ReviewStatus.BLOCKED
    decision: ReviewDecision = ReviewDecision.PENDING
    apply_plan: Optional[ApplyPlan] = None

    @property
    def has_blocking_issues(self) -> bool:
        return bool(self.blocking_issues)

    @property
    def is_approval_allowed(self) -> bool:
        return not self.has_blocking_issues and self.readiness_status != ReviewStatus.BLOCKED


@dataclass(frozen=True, slots=True)
class ControlListReviewRun:
    """Review aggregate for one import run — in-memory, not canonical."""

    import_run_id: Optional[int]
    profile_id: Optional[int]
    profile_code: Optional[str]
    profile_version: Optional[int]
    items: tuple[ControlListReviewItem, ...]
    assembled_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def item_count(self) -> int:
        return len(self.items)
