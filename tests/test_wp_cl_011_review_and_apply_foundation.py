# tests/test_wp_cl_011_review_and_apply_foundation.py
"""Unit tests for WP-CL-011 review aggregate and apply planning foundation."""
from __future__ import annotations

import inspect
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal

import pytest

from app.control_list_import.domain.contact_candidate import ContactCandidate, ContactReadinessStatus, NormalizedEmail
from app.control_list_import.domain.education_candidate import EducationCandidate, EducationReadinessStatus, NormalizedGraduationYear
from app.control_list_import.domain.employment_candidate import (
    EmploymentCandidate,
    EmploymentReadinessStatus,
    NormalizedEmploymentStartDate,
    NormalizedRate,
)
from app.control_list_import.domain.other_ppr_candidate import (
    NormalizedScalarValue,
    OtherPprCandidate,
    OtherPprReadinessStatus,
)
from app.control_list_import.domain.person_candidate import (
    NormalizedBirthDate,
    NormalizedFullName,
    NormalizedIin,
    NormalizedPhone,
    NormalizedPlainText,
    NormalizedSex,
    PersonCandidate,
)
from app.control_list_import.domain.person_match_models import MatchReason, MatchStatus, PersonMatchResult
from app.control_list_import.domain.review_models import (
    ApplyActionType,
    ReviewDecision,
    ReviewStatus,
)
from app.control_list_import.domain.training_candidate import TrainingCandidate, TrainingReadinessStatus
from app.control_list_import.domain.vocabulary import SEMANTIC_FIELD_PERSON_CITIZENSHIP
from app.control_list_import.review.apply_planner import ApplyPlanner, _idempotency_key
from app.control_list_import.review.assembler import ReviewAssembler
from app.control_list_import.review.decisions import ReviewDecisionError, apply_review_decision
from app.control_list_import.review.normalization_bundle import NormalizationRunBundle
from app.db.models.control_list_mapping import EMPLOYMENT_MODE_CONCURRENT, EMPLOYMENT_MODE_PRIMARY


def _person_candidate(*, row_id: int = 100, iin_issues: tuple[str, ...] = ()) -> PersonCandidate:
    return PersonCandidate(
        import_run_id=7,
        profile_id=10,
        profile_code="control_list_default",
        profile_version=1,
        source_row_id=row_id,
        source_sheet_name="врачи",
        source_excel_row_number=5,
        personnel_category="doctor",
        employment_mode="primary",
        full_name=NormalizedFullName(raw="Иванов Иван", display="Иванов Иван", normalized_key="ivanov ivan"),
        iin=NormalizedIin(raw="850101300123", digits="850101300123", issues=iin_issues),
        birth_date=NormalizedBirthDate(raw="01.01.1985", value=date(1985, 1, 1)),
        phone=NormalizedPhone(raw="+77001234567", digits="77001234567"),
        sex=NormalizedSex(raw="М", code="M"),
        department_name=NormalizedPlainText(raw="Терапия", text="Терапия"),
        position_title=NormalizedPlainText(raw="Врач", text="Врач"),
    )


def _person_match(
    *,
    row_id: int = 100,
    status: MatchStatus = MatchStatus.EXACT,
    recommended_person_id: int | None = 42,
) -> PersonMatchResult:
    return PersonMatchResult(
        import_run_id=7,
        source_row_id=row_id,
        status=status,
        match_candidates=(),
        primary_reason=MatchReason.EXACT_IIN,
        reasons=(MatchReason.EXACT_IIN,),
        confidence=1.0,
        recommended_person_id=recommended_person_id,
    )


def _employment_candidate(
    *,
    row_id: int = 100,
    ready: bool = True,
    employment_mode: str = EMPLOYMENT_MODE_PRIMARY,
) -> EmploymentCandidate:
    status = EmploymentReadinessStatus.NORMALIZATION_READY if ready else EmploymentReadinessStatus.REVIEW_REQUIRED
    field_issues = {} if ready else {"employment.department": ("employment_department_missing",)}
    return EmploymentCandidate(
        import_run_id=7,
        profile_id=10,
        profile_code="control_list_default",
        profile_version=1,
        source_row_id=row_id,
        source_sheet_name="врачи",
        source_excel_row_number=5,
        matched_person_id=42 if ready else None,
        personnel_category="doctor",
        employment_mode=employment_mode,
        department_name=NormalizedPlainText(raw="Терапия", text="Терапия"),
        position_title=NormalizedPlainText(raw="Врач", text="Врач"),
        rate=NormalizedRate(raw="1", value=Decimal("1")),
        employment_start_date=NormalizedEmploymentStartDate(raw="01.03.2020", value=date(2020, 3, 1)),
        field_issues=field_issues,
        readiness_status=status,
    )


def _contact_candidate(*, row_id: int = 100) -> ContactCandidate:
    return ContactCandidate(
        import_run_id=7,
        profile_id=10,
        profile_code="control_list_default",
        profile_version=1,
        source_row_id=row_id,
        source_sheet_name="врачи",
        source_excel_row_number=5,
        matched_person_id=42,
        phone=NormalizedPhone(raw="+77001234567", digits="77001234567"),
        email=NormalizedEmail(raw="a@b.kz", address="a@b.kz"),
        residence_address=NormalizedPlainText(raw="Алматы", text="Алматы"),
        registration_address=NormalizedPlainText(raw="Алматы", text="Алматы"),
        readiness_status=ContactReadinessStatus.NORMALIZATION_READY,
    )


def _education_candidate(*, row_id: int = 100, fragment_index: int = 0) -> EducationCandidate:
    return EducationCandidate(
        import_run_id=7,
        profile_id=10,
        profile_code="control_list_default",
        profile_version=1,
        source_row_id=row_id,
        source_sheet_name="врачи",
        source_excel_row_number=5,
        source_column_index=12,
        source_column_letter="L",
        source_fragment_index=fragment_index,
        raw_fragment="КазНМУ; 2010",
        matched_person_id=42,
        institution_name=NormalizedPlainText(raw="КазНМУ", text="КазНМУ"),
        qualification=NormalizedPlainText(raw="врач", text="врач"),
        specialty=NormalizedPlainText(raw="терапия", text="терапия"),
        graduation_year=NormalizedGraduationYear(raw="2010", value=2010),
        education_level=NormalizedPlainText(raw="высшее", text="высшее"),
        document_number=NormalizedPlainText(raw="", text=None),
        readiness_status=EducationReadinessStatus.NORMALIZATION_READY,
    )


def _training_candidate(*, row_id: int = 100) -> TrainingCandidate:
    from app.control_list_import.domain.training_candidate import (
        NormalizedCompletionDate,
        NormalizedCompletionYear,
        NormalizedDurationHours,
    )

    return TrainingCandidate(
        import_run_id=7,
        profile_id=10,
        profile_code="control_list_default",
        profile_version=1,
        source_row_id=row_id,
        source_sheet_name="врачи",
        source_excel_row_number=5,
        source_column_index=13,
        source_column_letter="M",
        source_fragment_index=0,
        raw_fragment="Курс ACLS; 2022",
        matched_person_id=42,
        training_title=NormalizedPlainText(raw="ACLS", text="ACLS"),
        provider_name=NormalizedPlainText(raw="", text=None),
        completion_date=NormalizedCompletionDate(raw="", value=None),
        completion_year=NormalizedCompletionYear(raw="2022", value=2022),
        certificate_number=NormalizedPlainText(raw="", text=None),
        duration_hours=NormalizedDurationHours(raw="", value=None),
        training_type=NormalizedPlainText(raw="", text=None),
        readiness_status=TrainingReadinessStatus.NORMALIZATION_READY,
    )


def _other_ppr_candidate(*, row_id: int = 100) -> OtherPprCandidate:
    return OtherPprCandidate(
        import_run_id=7,
        profile_id=10,
        profile_code="control_list_default",
        profile_version=1,
        source_row_id=row_id,
        source_sheet_name="врачи",
        source_excel_row_number=5,
        source_column_index=14,
        source_column_letter="N",
        semantic_field=SEMANTIC_FIELD_PERSON_CITIZENSHIP,
        raw_value="РК",
        normalized_value=NormalizedScalarValue(raw="РК", text="РК", code="KZ"),
        matched_person_id=42,
        readiness_status=OtherPprReadinessStatus.NORMALIZATION_READY,
    )


def _full_bundle(*, row_id: int = 100) -> NormalizationRunBundle:
    return NormalizationRunBundle(
        import_run_id=7,
        profile_id=10,
        profile_code="control_list_default",
        profile_version=1,
        person_candidates={row_id: _person_candidate(row_id=row_id)},
        person_matches={row_id: _person_match(row_id=row_id)},
        employment_candidates={row_id: _employment_candidate(row_id=row_id)},
        contact_candidates={row_id: _contact_candidate(row_id=row_id)},
        education_candidates={row_id: [_education_candidate(row_id=row_id)]},
        training_candidates={row_id: [_training_candidate(row_id=row_id)]},
        other_ppr_candidates={row_id: [_other_ppr_candidate(row_id=row_id)]},
    )


def test_one_source_row_produces_one_review_item():
    bundle = _full_bundle()
    bundle = replace(
        bundle,
        person_candidates={
            100: _person_candidate(row_id=100),
            101: _person_candidate(row_id=101),
        },
        person_matches={
            100: _person_match(row_id=100),
            101: _person_match(row_id=101, recommended_person_id=43),
        },
        employment_candidates={100: _employment_candidate(row_id=100), 101: None},
        contact_candidates={100: _contact_candidate(row_id=100), 101: None},
        education_candidates={100: [_education_candidate(row_id=100)], 101: []},
        training_candidates={100: [_training_candidate(row_id=100)], 101: []},
        other_ppr_candidates={100: [_other_ppr_candidate(row_id=100)], 101: []},
    )
    review_run = ReviewAssembler().assemble(bundle)
    assert review_run.item_count == 2
    row_ids = {item.source_row_id for item in review_run.items}
    assert row_ids == {100, 101}


def test_full_review_item_contains_all_slices():
    review_run = ReviewAssembler().assemble(_full_bundle())
    item = review_run.items[0]
    assert item.person_candidate is not None
    assert item.person_match is not None
    assert item.employment_candidate is not None
    assert item.contact_candidate is not None
    assert len(item.education_candidates) == 1
    assert len(item.training_candidates) == 1
    assert len(item.other_ppr_candidates) == 1
    assert item.source_sheet_name == "врачи"
    assert item.source_excel_row_number == 5
    assert item.readiness_status == ReviewStatus.READY
    assert item.decision == ReviewDecision.PENDING
    assert not item.has_blocking_issues


def test_blocking_issue_aggregation_for_invalid_person_match():
    bundle = replace(
        _full_bundle(),
        person_matches={100: _person_match(status=MatchStatus.INVALID, recommended_person_id=None)},
        employment_candidates={100: _employment_candidate(ready=False)},
    )
    item = ReviewAssembler().assemble(bundle).items[0]
    assert item.readiness_status == ReviewStatus.BLOCKED
    assert any(issue.code == "review.person_match_invalid" for issue in item.blocking_issues)
    assert not item.is_approval_allowed


@pytest.mark.parametrize(
    "status,expected_code",
    [
        (MatchStatus.AMBIGUOUS, "review.person_match_ambiguous"),
        (MatchStatus.INVALID, "review.person_match_invalid"),
        (MatchStatus.NOT_FOUND, "review.person_not_found"),
    ],
)
def test_person_match_statuses_block_review(status, expected_code):
    bundle = replace(
        _full_bundle(),
        person_matches={100: _person_match(status=status, recommended_person_id=None)},
    )
    item = ReviewAssembler().assemble(bundle).items[0]
    assert item.readiness_status == ReviewStatus.BLOCKED
    assert any(issue.code == expected_code for issue in item.blocking_issues)


def test_approved_item_with_valid_match_gets_executable_plan():
    item = ReviewAssembler().assemble(_full_bundle()).items[0]
    approved = apply_review_decision(item, ReviewDecision.APPROVED)
    plan = approved.apply_plan
    assert plan is not None
    assert plan.is_executable
    assert plan.decision == ReviewDecision.APPROVED
    action_types = {action.action_type for action in plan.actions}
    assert ApplyActionType.UPDATE_PERSON_CONTACT in action_types
    assert ApplyActionType.RESOLVE_ASSIGNMENT in action_types
    assert ApplyActionType.ADD_EDUCATION in action_types
    assert ApplyActionType.ADD_TRAINING in action_types
    assert ApplyActionType.UPDATE_OTHER_PPR_FIELD in action_types
    assert ApplyActionType.CREATE_PERSON not in action_types


def test_rejected_item_has_skip_only_plan():
    item = ReviewAssembler().assemble(_full_bundle()).items[0]
    rejected = apply_review_decision(item, ReviewDecision.REJECTED)
    plan = rejected.apply_plan
    assert plan is not None
    assert not plan.is_executable
    assert len(plan.actions) == 1
    assert plan.actions[0].action_type == ApplyActionType.SKIP


def test_mixed_candidates_partial_ready_blocks_executable_plan():
    bundle = replace(
        _full_bundle(),
        employment_candidates={100: _employment_candidate(ready=False)},
    )
    item = ReviewAssembler().assemble(bundle).items[0]
    approved = apply_review_decision(item, ReviewDecision.APPROVED)
    plan = approved.apply_plan
    assert plan is not None
    assert not plan.is_executable
    employment_actions = [
        action for action in plan.actions if action.action_type == ApplyActionType.RESOLVE_ASSIGNMENT
    ]
    assert employment_actions
    assert not employment_actions[0].is_ready
    assert employment_actions[0].blocking_reason == "employment.not_normalization_ready"


def test_empty_optional_sections_do_not_create_false_blocking():
    bundle = NormalizationRunBundle(
        import_run_id=7,
        profile_id=10,
        profile_code="control_list_default",
        profile_version=1,
        person_candidates={100: _person_candidate()},
        person_matches={100: _person_match()},
        employment_candidates={100: None},
        contact_candidates={100: None},
        education_candidates={100: []},
        training_candidates={100: []},
        other_ppr_candidates={100: []},
    )
    item = ReviewAssembler().assemble(bundle).items[0]
    assert item.readiness_status == ReviewStatus.READY
    assert not item.non_blocking_issues


def test_idempotency_key_is_stable():
    key_a = _idempotency_key(
        import_run_id=7,
        source_row_id=100,
        action_type=ApplyActionType.ADD_EDUCATION,
        ref_suffix="education:12:0",
    )
    key_b = _idempotency_key(
        import_run_id=7,
        source_row_id=100,
        action_type=ApplyActionType.ADD_EDUCATION,
        ref_suffix="education:12:0",
    )
    key_c = _idempotency_key(
        import_run_id=7,
        source_row_id=100,
        action_type=ApplyActionType.ADD_EDUCATION,
        ref_suffix="education:12:1",
    )
    assert key_a == key_b
    assert key_a != key_c
    assert key_a.startswith("cl-apply:")


def test_not_found_pending_plan_includes_create_person_not_auto_ready():
    bundle = replace(
        _full_bundle(),
        person_matches={100: _person_match(status=MatchStatus.NOT_FOUND, recommended_person_id=None)},
    )
    item = ReviewAssembler().assemble(bundle).items[0]
    assert item.has_blocking_issues
    assert item.readiness_status == ReviewStatus.BLOCKED
    plan = item.apply_plan
    assert plan is not None
    assert not plan.is_executable
    create_actions = [action for action in plan.actions if action.action_type == ApplyActionType.CREATE_PERSON]
    assert len(create_actions) == 1
    assert not create_actions[0].is_ready
    with pytest.raises(ReviewDecisionError):
        apply_review_decision(item, ReviewDecision.APPROVED)


def test_person_candidate_blocking_fields():
    bundle = replace(
        _full_bundle(),
        person_candidates={
            100: PersonCandidate(
                import_run_id=7,
                profile_id=10,
                profile_code="control_list_default",
                profile_version=1,
                source_row_id=100,
                source_sheet_name="врачи",
                source_excel_row_number=5,
                personnel_category="doctor",
                employment_mode="primary",
                full_name=NormalizedFullName(raw="Иванов Иван", display="Иванов Иван", normalized_key="ivanov ivan"),
                iin=NormalizedIin(raw="bad", digits=None, issues=("iin_invalid_checksum",)),
                birth_date=NormalizedBirthDate(raw="01.01.1985", value=date(1985, 1, 1)),
                phone=NormalizedPhone(raw="+77001234567", digits="77001234567"),
                sex=NormalizedSex(raw="М", code="M"),
                department_name=NormalizedPlainText(raw="Терапия", text="Терапия"),
                position_title=NormalizedPlainText(raw="Врач", text="Врач"),
                field_issues={"person.iin": ("iin_invalid_checksum",)},
            )
        },
    )
    item = ReviewAssembler().assemble(bundle).items[0]
    assert item.readiness_status == ReviewStatus.BLOCKED
    assert any("iin_invalid_checksum" in issue.code for issue in item.blocking_issues)


def test_normalization_ready_slices_do_not_imply_item_ready_when_person_blocked():
    bundle = replace(
        _full_bundle(),
        person_matches={100: _person_match(status=MatchStatus.AMBIGUOUS, recommended_person_id=None)},
    )
    item = ReviewAssembler().assemble(bundle).items[0]
    assert item.employment_candidate is not None
    assert item.employment_candidate.is_normalization_ready is True
    assert item.readiness_status == ReviewStatus.BLOCKED


def test_review_layer_has_no_db_or_ppr_writes():
    modules = [
        ReviewAssembler,
        ApplyPlanner,
    ]
    forbidden = (
        "sqlalchemy",
        "insert into",
        "update ",
        "delete from",
        "session.commit",
        "persons",
        "employees",
        "person_assignments",
    )
    for module_cls in modules:
        source = inspect.getsource(module_cls).lower()
        for token in forbidden:
            assert token not in source, f"{module_cls.__name__} must not reference {token}"


def test_approve_does_not_execute_apply():
    item = ReviewAssembler().assemble(_full_bundle()).items[0]
    approved = apply_review_decision(item, ReviewDecision.APPROVED)
    for module in (ApplyPlanner, apply_review_decision):
        source = inspect.getsource(module).lower()
        assert "sqlalchemy" not in source
        assert "session.commit" not in source
        assert "repository" not in source
    assert approved.apply_plan is not None
    assert approved.decision == ReviewDecision.APPROVED
    assert item.decision == ReviewDecision.PENDING
    assert item.apply_plan is not None
    assert item.apply_plan.is_executable is False


def test_concurrent_employment_uses_resolve_assignment_not_external():
    bundle = replace(
        _full_bundle(),
        employment_candidates={
            100: _employment_candidate(
                row_id=100,
                employment_mode=EMPLOYMENT_MODE_CONCURRENT,
            )
        },
    )
    item = ReviewAssembler().assemble(bundle).items[0]
    approved = apply_review_decision(item, ReviewDecision.APPROVED)
    plan = approved.apply_plan
    assert plan is not None
    employment_action = next(
        action for action in plan.actions if action.action_type == ApplyActionType.RESOLVE_ASSIGNMENT
    )
    assert employment_action.target_aggregate == "employment.assignment"
    assert f"employment_mode={EMPLOYMENT_MODE_CONCURRENT}" in employment_action.preconditions
    assert ApplyActionType.CREATE_EXTERNAL_EMPLOYMENT not in {a.action_type for a in plan.actions}


def test_blocked_item_cannot_be_approved():
    bundle = replace(
        _full_bundle(),
        person_matches={100: _person_match(status=MatchStatus.AMBIGUOUS, recommended_person_id=None)},
    )
    item = ReviewAssembler().assemble(bundle).items[0]
    with pytest.raises(ReviewDecisionError):
        apply_review_decision(item, ReviewDecision.APPROVED)


def test_wrong_row_provenance_is_not_attached_to_review_item():
    wrong_row_employment = _employment_candidate(row_id=999)
    bundle = replace(
        _full_bundle(),
        employment_candidates={100: wrong_row_employment},
    )
    item = ReviewAssembler().assemble(bundle).items[0]
    assert item.source_row_id == 100
    assert item.employment_candidate is None


def test_duplicate_candidate_reference_does_not_duplicate_apply_action():
    duplicate_education = _education_candidate(row_id=100, fragment_index=0)
    bundle = replace(
        _full_bundle(),
        education_candidates={100: [duplicate_education, duplicate_education]},
    )
    item = ReviewAssembler().assemble(bundle).items[0]
    approved = apply_review_decision(item, ReviewDecision.APPROVED)
    education_actions = [
        action for action in approved.apply_plan.actions if action.action_type == ApplyActionType.ADD_EDUCATION
    ]
    assert len(education_actions) == 1


def test_blocking_issues_are_deduplicated():
    bundle = replace(
        _full_bundle(),
        person_candidates={
            100: PersonCandidate(
                import_run_id=7,
                profile_id=10,
                profile_code="control_list_default",
                profile_version=1,
                source_row_id=100,
                source_sheet_name="врачи",
                source_excel_row_number=5,
                personnel_category="doctor",
                employment_mode="primary",
                full_name=NormalizedFullName(raw="Иванов Иван", display="Иванов Иван", normalized_key="ivanov ivan"),
                iin=NormalizedIin(raw="bad", digits=None, issues=("iin_invalid_checksum",)),
                birth_date=NormalizedBirthDate(raw="01.01.1985", value=date(1985, 1, 1)),
                phone=NormalizedPhone(raw="+77001234567", digits="77001234567"),
                sex=NormalizedSex(raw="М", code="M"),
                department_name=NormalizedPlainText(raw="Терапия", text="Терапия"),
                position_title=NormalizedPlainText(raw="Врач", text="Врач"),
                field_issues={
                    "person.iin": ("iin_invalid_checksum", "iin_invalid_checksum"),
                },
            )
        },
    )
    item = ReviewAssembler().assemble(bundle).items[0]
    blocking_codes = [issue.code for issue in item.blocking_issues if issue.source == "person"]
    assert blocking_codes.count("iin_invalid_checksum") == 1


def test_unsupported_other_ppr_is_not_executable():
    unsupported = OtherPprCandidate(
        import_run_id=7,
        profile_id=10,
        profile_code="control_list_default",
        profile_version=1,
        source_row_id=100,
        source_sheet_name="врачи",
        source_excel_row_number=5,
        source_column_index=15,
        source_column_letter="O",
        semantic_field="unknown.field",
        raw_value="???",
        normalized_value=NormalizedScalarValue(
            raw="???",
            text=None,
            issues=("other_ppr_unsupported_semantic_field",),
        ),
        matched_person_id=42,
        field_issues={"unknown.field": ("other_ppr_unsupported_semantic_field",)},
        readiness_status=OtherPprReadinessStatus.REVIEW_REQUIRED,
    )
    bundle = replace(
        _full_bundle(),
        other_ppr_candidates={100: [unsupported]},
    )
    item = ReviewAssembler().assemble(bundle).items[0]
    approved = apply_review_decision(item, ReviewDecision.APPROVED)
    other_ppr_actions = [
        action
        for action in approved.apply_plan.actions
        if action.action_type == ApplyActionType.UPDATE_OTHER_PPR_FIELD
    ]
    assert len(other_ppr_actions) == 1
    assert not other_ppr_actions[0].is_ready
    assert not approved.apply_plan.is_executable


@pytest.mark.parametrize(
    "decision",
    [ReviewDecision.PENDING, ReviewDecision.NEEDS_CORRECTION],
)
def test_non_approved_decisions_are_not_executable(decision):
    item = replace(
        ReviewAssembler().assemble(_full_bundle()).items[0],
        decision=decision,
    )
    plan = ApplyPlanner().plan_item(item)
    assert not plan.is_executable
    assert plan.actions == ()


def test_rebuilt_plan_preserves_idempotency_keys():
    item = ReviewAssembler().assemble(_full_bundle()).items[0]
    approved = apply_review_decision(item, ReviewDecision.APPROVED)
    replanned = ApplyPlanner().plan_item(approved)
    assert approved.apply_plan is not None
    assert [action.idempotency_key for action in approved.apply_plan.actions] == [
        action.idempotency_key for action in replanned.actions
    ]


def test_planner_never_generates_create_external_employment():
    source = inspect.getsource(ApplyPlanner).lower()
    assert "create_external_employment" not in source
    bundle = replace(
        _full_bundle(),
        employment_candidates={
            100: _employment_candidate(employment_mode=EMPLOYMENT_MODE_CONCURRENT),
        },
    )
    approved = apply_review_decision(ReviewAssembler().assemble(bundle).items[0], ReviewDecision.APPROVED)
    assert ApplyActionType.CREATE_EXTERNAL_EMPLOYMENT not in {
        action.action_type for action in approved.apply_plan.actions
    }
