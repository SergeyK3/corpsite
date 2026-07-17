"""ReviewAssembler — normalization results → ControlListReviewRun (WP-CL-011)."""
from __future__ import annotations

from dataclasses import replace
from typing import Optional

from app.control_list_import.domain.contact_candidate import ContactCandidate, ContactReadinessStatus
from app.control_list_import.domain.education_candidate import EducationCandidate, EducationReadinessStatus
from app.control_list_import.domain.employment_candidate import EmploymentCandidate, EmploymentReadinessStatus
from app.control_list_import.domain.other_ppr_candidate import OtherPprCandidate, OtherPprReadinessStatus
from app.control_list_import.domain.person_candidate import PersonCandidate
from app.control_list_import.domain.person_match_models import MatchStatus, PersonMatchResult
from app.control_list_import.domain.review_models import (
    BlockingIssueSummary,
    ControlListReviewItem,
    ControlListReviewRun,
    ReviewDecision,
    ReviewStatus,
)
from app.control_list_import.domain.training_candidate import TrainingCandidate, TrainingReadinessStatus
from app.control_list_import.review.apply_planner import ApplyPlanner
from app.control_list_import.review.issues import dedupe_issues
from app.control_list_import.review.normalization_bundle import NormalizationRunBundle
from app.control_list_import.review.provenance import (
    filter_candidate_list,
    filter_optional_candidate,
    person_candidate_matches_row,
    person_match_matches_row,
)

class ReviewAssembler:
    """Assemble normalization + matching outputs into a review aggregate."""

    def __init__(self, *, apply_planner: Optional[ApplyPlanner] = None) -> None:
        self._apply_planner = apply_planner or ApplyPlanner()

    def assemble(self, bundle: NormalizationRunBundle) -> ControlListReviewRun:
        items = tuple(
            self._assemble_item(bundle, source_row_id)
            for source_row_id in bundle.source_row_ids()
        )
        return ControlListReviewRun(
            import_run_id=bundle.import_run_id,
            profile_id=bundle.profile_id,
            profile_code=bundle.profile_code,
            profile_version=bundle.profile_version,
            items=items,
        )

    def _assemble_item(
        self,
        bundle: NormalizationRunBundle,
        source_row_id: int,
    ) -> ControlListReviewItem:
        person_candidate = person_candidate_matches_row(
            bundle.person_candidates.get(source_row_id),
            source_row_id=source_row_id,
        )
        person_match = person_match_matches_row(
            bundle.person_matches.get(source_row_id),
            source_row_id=source_row_id,
        )
        employment = filter_optional_candidate(
            bundle.employment_candidates.get(source_row_id),
            source_row_id=source_row_id,
        )
        contact = filter_optional_candidate(
            bundle.contact_candidates.get(source_row_id),
            source_row_id=source_row_id,
        )
        education = filter_candidate_list(
            bundle.education_candidates.get(source_row_id, ()),
            source_row_id=source_row_id,
        )
        training = filter_candidate_list(
            bundle.training_candidates.get(source_row_id, ()),
            source_row_id=source_row_id,
        )
        other_ppr = filter_candidate_list(
            bundle.other_ppr_candidates.get(source_row_id, ()),
            source_row_id=source_row_id,
        )

        provenance = _resolve_provenance(
            source_row_id=source_row_id,
            person_candidate=person_candidate,
            person_match=person_match,
            employment=employment,
            contact=contact,
            education=education,
            training=training,
            other_ppr=other_ppr,
            bundle=bundle,
        )

        blocking = dedupe_issues(_collect_blocking_issues(person_candidate, person_match))
        non_blocking = dedupe_issues(
            _collect_non_blocking_slice_issues(
                employment=employment,
                contact=contact,
                education=education,
                training=training,
                other_ppr=other_ppr,
                person_match=person_match,
            )
        )

        readiness = _compute_readiness(blocking, non_blocking)

        item = ControlListReviewItem(
            import_run_id=provenance["import_run_id"],
            profile_id=provenance["profile_id"],
            profile_code=provenance["profile_code"],
            profile_version=provenance["profile_version"],
            source_row_id=source_row_id,
            source_sheet_name=provenance["source_sheet_name"],
            source_excel_row_number=provenance["source_excel_row_number"],
            person_candidate=person_candidate,
            person_match=person_match,
            employment_candidate=employment,
            contact_candidate=contact,
            education_candidates=education,
            training_candidates=training,
            other_ppr_candidates=other_ppr,
            blocking_issues=blocking,
            non_blocking_issues=non_blocking,
            readiness_status=readiness,
            decision=ReviewDecision.PENDING,
            apply_plan=None,
        )
        return replace(item, apply_plan=self._apply_planner.plan_item(item))


def _resolve_provenance(
    *,
    source_row_id: int,
    person_candidate: Optional[PersonCandidate],
    person_match: Optional[PersonMatchResult],
    employment: Optional[EmploymentCandidate],
    contact: Optional[ContactCandidate],
    education: tuple[EducationCandidate, ...],
    training: tuple[TrainingCandidate, ...],
    other_ppr: tuple[OtherPprCandidate, ...],
    bundle: NormalizationRunBundle,
) -> dict:
    for candidate in (
        person_candidate,
        employment,
        contact,
        education[0] if education else None,
        training[0] if training else None,
        other_ppr[0] if other_ppr else None,
    ):
        if candidate is None:
            continue
        return {
            "import_run_id": getattr(candidate, "import_run_id", bundle.import_run_id),
            "profile_id": getattr(candidate, "profile_id", bundle.profile_id),
            "profile_code": getattr(candidate, "profile_code", bundle.profile_code),
            "profile_version": getattr(candidate, "profile_version", bundle.profile_version),
            "source_sheet_name": candidate.source_sheet_name,
            "source_excel_row_number": candidate.source_excel_row_number,
        }

    if person_match is not None:
        return {
            "import_run_id": person_match.import_run_id or bundle.import_run_id,
            "profile_id": bundle.profile_id,
            "profile_code": bundle.profile_code,
            "profile_version": bundle.profile_version,
            "source_sheet_name": "",
            "source_excel_row_number": 0,
        }

    return {
        "import_run_id": bundle.import_run_id,
        "profile_id": bundle.profile_id,
        "profile_code": bundle.profile_code,
        "profile_version": bundle.profile_version,
        "source_sheet_name": "",
        "source_excel_row_number": 0,
    }


def _collect_blocking_issues(
    person_candidate: Optional[PersonCandidate],
    person_match: Optional[PersonMatchResult],
) -> tuple[BlockingIssueSummary, ...]:
    issues: list[BlockingIssueSummary] = []

    if person_candidate is None:
        issues.append(
            BlockingIssueSummary(
                code="review.person_candidate_missing",
                source="person",
                message="Person candidate is missing for source row",
                blocking=True,
            )
        )
    elif person_candidate.has_blocking_issues:
        seen_codes: set[str] = set()
        for issue_code in person_candidate.all_issues:
            if issue_code in seen_codes:
                continue
            seen_codes.add(issue_code)
            issues.append(
                BlockingIssueSummary(
                    code=issue_code,
                    source="person",
                    message=f"Person candidate blocking field issue: {issue_code}",
                    blocking=True,
                )
            )

    if person_match is None:
        issues.append(
            BlockingIssueSummary(
                code="review.person_match_missing",
                source="person_match",
                message="Person match result is missing for source row",
                blocking=True,
            )
        )
        return tuple(issues)

    if person_match.status == MatchStatus.AMBIGUOUS:
        issues.append(
            BlockingIssueSummary(
                code="review.person_match_ambiguous",
                source="person_match",
                message="Person match is ambiguous — manual resolution required",
                blocking=True,
            )
        )
    elif person_match.status == MatchStatus.INVALID:
        issues.append(
            BlockingIssueSummary(
                code="review.person_match_invalid",
                source="person_match",
                message="Person match is invalid — attribute conflict or incomplete candidate",
                blocking=True,
            )
        )
    elif person_match.status == MatchStatus.NOT_FOUND:
        issues.append(
            BlockingIssueSummary(
                code="review.person_not_found",
                source="person_match",
                message="No matching Person — automatic apply blocked; explicit create-person only",
                blocking=True,
            )
        )

    return tuple(issues)


def _collect_non_blocking_slice_issues(
    *,
    employment: Optional[EmploymentCandidate],
    contact: Optional[ContactCandidate],
    education: tuple[EducationCandidate, ...],
    training: tuple[TrainingCandidate, ...],
    other_ppr: tuple[OtherPprCandidate, ...],
    person_match: Optional[PersonMatchResult],
) -> tuple[BlockingIssueSummary, ...]:
    """Collect slice issues only when a candidate exists — empty sections are skipped."""
    if person_match is None:
        return ()

    issues: list[BlockingIssueSummary] = []

    if employment is not None:
        issues.extend(_slice_issues(employment, source="employment", prefix="employment"))

    if contact is not None:
        issues.extend(_slice_issues(contact, source="contact", prefix="contact"))

    for index, candidate in enumerate(education):
        issues.extend(
            _slice_issues(
                candidate,
                source=f"education[{index}]",
                prefix="education",
                fragment_index=candidate.source_fragment_index,
            )
        )

    for index, candidate in enumerate(training):
        issues.extend(
            _slice_issues(
                candidate,
                source=f"training[{index}]",
                prefix="training",
                fragment_index=candidate.source_fragment_index,
            )
        )

    for index, candidate in enumerate(other_ppr):
        issues.extend(
            _slice_issues(
                candidate,
                source=f"other_ppr[{index}]",
                prefix="other_ppr",
                semantic_field=candidate.semantic_field,
            )
        )

    return tuple(issues)


def _slice_issues(
    candidate: object,
    *,
    source: str,
    prefix: str,
    fragment_index: Optional[int] = None,
    semantic_field: Optional[str] = None,
) -> list[BlockingIssueSummary]:
    readiness = getattr(candidate, "readiness_status", None)
    if readiness is None:
        return []

    person_match_derived = readiness in {
        EmploymentReadinessStatus.PERSON_MATCH_INVALID,
        EmploymentReadinessStatus.PERSON_UNMATCHED,
        ContactReadinessStatus.PERSON_MATCH_INVALID,
        ContactReadinessStatus.PERSON_UNMATCHED,
        EducationReadinessStatus.PERSON_MATCH_INVALID,
        EducationReadinessStatus.PERSON_UNMATCHED,
        TrainingReadinessStatus.PERSON_MATCH_INVALID,
        TrainingReadinessStatus.PERSON_UNMATCHED,
        OtherPprReadinessStatus.PERSON_MATCH_INVALID,
        OtherPprReadinessStatus.PERSON_UNMATCHED,
    }
    if person_match_derived:
        return []

    if getattr(candidate, "is_normalization_ready", False):
        return []

    field_issues = getattr(candidate, "field_issues", {})
    all_issues = getattr(candidate, "all_issues", ())
    if not all_issues and not field_issues:
        return [
            BlockingIssueSummary(
                code=f"review.{prefix}.review_required",
                source=source,
                message=f"{prefix} slice requires review",
                blocking=False,
            )
        ]

    collected: list[BlockingIssueSummary] = []
    for issue_code in all_issues:
        suffix = ""
        if fragment_index is not None:
            suffix = f" fragment={fragment_index}"
        if semantic_field is not None:
            suffix = f" field={semantic_field}"
        collected.append(
            BlockingIssueSummary(
                code=issue_code,
                source=source,
                message=f"{prefix} non-blocking issue{suffix}: {issue_code}",
                blocking=False,
            )
        )
    return collected


def _compute_readiness(
    blocking: tuple[BlockingIssueSummary, ...],
    non_blocking: tuple[BlockingIssueSummary, ...],
) -> ReviewStatus:
    if blocking:
        return ReviewStatus.BLOCKED
    if non_blocking:
        return ReviewStatus.NEEDS_REVIEW
    return ReviewStatus.READY
