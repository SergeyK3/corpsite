from app.ppr.application import config
from app.services import ppr_stage3_training_service as service
from app.control_list_import.domain.person_candidate import NormalizedPlainText
from app.control_list_import.domain.training_candidate import (
    NormalizedCompletionDate,
    NormalizedCompletionYear,
    NormalizedDurationHours,
    TrainingCandidate,
    TrainingReadinessStatus,
)
from datetime import date
from decimal import Decimal


def test_stage3_training_flags_default_off(monkeypatch):
    for key in (
        "PPR_STAGE3_TRAINING_PREVIEW_ENABLED",
        "PPR_STAGE3_TRAINING_EXECUTION_ENABLED",
        "PPR_STAGE3_TRAINING_ACCEPT_ENABLED",
    ):
        monkeypatch.delenv(key, raising=False)
    assert not config.ppr_stage3_training_preview_enabled()
    assert not config.ppr_stage3_training_execution_enabled()
    assert not config.ppr_stage3_training_accept_enabled()


def test_stage3_certificate_hmac_is_versioned_and_secret_is_not_result(monkeypatch):
    monkeypatch.setenv("PPR_STAGE3_CERTIFICATE_HMAC_SECRET", "test-secret")
    value = service._certificate_hmac("  AB  123 ")
    assert value and value.startswith("v1:")
    assert "AB" not in value
    assert "test-secret" not in value


def _training_candidate(*, training_type: str = "COURSE") -> TrainingCandidate:
    """A real WP-CL-009 TrainingCandidate fixture, never an education payload."""
    return TrainingCandidate(
        import_run_id=7, profile_id=10, profile_code="control_list_default", profile_version=1,
        source_row_id=100, source_sheet_name="training", source_excel_row_number=5,
        source_column_index=13, source_column_letter="M", source_fragment_index=0,
        raw_fragment="source fragment", matched_person_id=42,
        training_title=NormalizedPlainText(raw="ACLS", text="ACLS"),
        provider_name=NormalizedPlainText(raw="Provider", text="Provider"),
        completion_date=NormalizedCompletionDate(raw="2024-03-01", value=date(2024, 3, 1)),
        completion_year=NormalizedCompletionYear(raw="2024", value=2024),
        certificate_number=NormalizedPlainText(raw="AB-1", text="AB-1"),
        duration_hours=NormalizedDurationHours(raw="36", value=Decimal("36")),
        training_type=NormalizedPlainText(raw=training_type, text=training_type),
        readiness_status=TrainingReadinessStatus.NORMALIZATION_READY,
    )


def test_training_type_mapping_is_explicit_and_unknown_never_maps_to_other():
    assert service.classify_training_kind("QUAL_UPGRADE").kind == "continuing_education"
    assert service.classify_training_kind("COURSE").kind == "course"
    assert service.classify_training_kind("SEMINAR").kind == "seminar"
    assert service.classify_training_kind("WORKSHOP").kind == "master_class"
    unknown = service.classify_training_kind("CONFERENCE")
    assert unknown.outcome == service.REVIEW_REQUIRED
    assert unknown.kind is None


def test_deterministic_candidate_requires_actual_training_fields():
    assert service._candidate_is_deterministic(_training_candidate())
    incomplete = _training_candidate()
    object.__setattr__(incomplete, "training_title", NormalizedPlainText(raw="", text=None))
    assert not service._candidate_is_deterministic(incomplete)


def test_deterministic_candidate_allows_missing_optional_provider_and_hours():
    candidate = _training_candidate()
    object.__setattr__(candidate, "provider_name", NormalizedPlainText(raw="", text=None))
    object.__setattr__(candidate, "duration_hours", NormalizedDurationHours(raw="", value=None))
    assert service._candidate_is_deterministic(candidate)


def test_exact_dedup_uses_provider_title_date_hours_and_certificate_hmac(monkeypatch):
    monkeypatch.setenv("PPR_STAGE3_CERTIFICATE_HMAC_SECRET", "test-secret")
    candidate = _training_candidate()
    monkeypatch.setattr(service, "_candidate_from_persisted_fragment", lambda _: candidate)
    fragment = {"normalized_record_id": 1, "batch_id": 2, "row_id": 3, "employee_id": 4,
                "fragment_index": 0, "source_record_key": "source-1", "source_row_number": 5,
                "source_text": "source", "title": "ACLS", "provider": "Provider", "hours": 36,
                "document_number": "AB-1", "end_date": date(2024, 3, 1), "issue_date": None,
                "source_field": "training", "parse_method": "regex_v1", "review_status": "approved",
                "reviewed_at": None, "reviewed_by": 1, "review_notes": None,
                "promoted_document_id": None, "updated_at": "v1"}
    canonical = {"training_id": 9, "training_kind": "course", "title": "ACLS",
                 "organization_name": "Provider", "hours": 36, "completed_at": date(2024, 3, 1),
                 "certificate_number": "AB-1", "metadata": {}, "updated_at": "v1"}
    view = service._fragment_view(fragment, [canonical], stage_run_id=1, participant_id=2, version=1)
    assert view["outcome"] == "ALREADY_APPLIED"
    changed_certificate = {**canonical, "certificate_number": "DIFFERENT"}
    assert service._fragment_view(fragment, [changed_certificate], stage_run_id=1, participant_id=2, version=1)["reason_code"] == "STAGE3_CANONICAL_POSSIBLE_DUPLICATE"
    changed_hours = {**canonical, "hours": 72, "certificate_number": "DIFFERENT"}
    assert service._fragment_view(fragment, [changed_hours], stage_run_id=1, participant_id=2, version=1)["reason_code"] == "STAGE3_CANONICAL_CONTRADICTORY_RECORD"
    distinct = {**canonical, "title": "BLS"}
    assert service._fragment_view(fragment, [distinct], stage_run_id=1, participant_id=2, version=1)["outcome"] == "READY_TO_ADD"


def test_certificate_redaction_removes_field_from_all_nested_stage3_dtos(monkeypatch):
    monkeypatch.setattr(service, "can_view_training_certificate_details", lambda _: False)
    value = {"proposal": {"certificate_number": "secret"}, "items": [{"current": {"certificate_number": "secret"}}]}
    assert service.redact_stage3_dto(value, user={}) == {"proposal": {}, "items": [{"current": {}}]}


def test_stale_fingerprint_covers_immutable_preconditions_not_reviewer_decisions(monkeypatch):
    monkeypatch.setenv("PPR_STAGE3_CERTIFICATE_HMAC_SECRET", "test-secret")
    participant = {"employee_id": 1, "person_id": 2, "status": "PENDING", "skip_reason": None}
    state = {"employee_id": 1, "employee_person_id": 2, "is_active": True, "operational_status": "active", "person_updated_at": "v1"}
    views = [{"normalized_record_id": 10, "source_fingerprint": "source-v1"}]
    canon = [{"training_id": 5, "training_kind": "course", "title": "ACLS", "organization_name": "Provider", "hours": 36, "completed_at": date(2024, 3, 1), "certificate_number": "AB-1", "updated_at": "v1"}]
    baseline = service._stale_fingerprint(participant=participant, state=state, views=views, canon=canon)
    assert baseline != service._stale_fingerprint(participant=participant, state=state, views=[{**views[0], "source_fingerprint": "source-v2"}], canon=canon)
    assert baseline != service._stale_fingerprint(participant={**participant, "person_id": 3}, state={**state, "employee_person_id": 3}, views=views, canon=canon)
    assert baseline != service._stale_fingerprint(participant=participant, state=state, views=views, canon=[{**canon[0], "hours": 72}])
    assert baseline == service._stale_fingerprint(participant={**participant, "status": "SKIPPED_BY_DECISION", "skip_reason": "review"}, state=state, views=views, canon=canon)


def test_approval_decision_fingerprint_changes_only_for_hr_skip_decisions():
    pending = {"stage_run_participant_id": 10, "status": "PENDING"}
    completed = {"stage_run_participant_id": 10, "status": "COMPLETED"}
    skipped = {
        "stage_run_participant_id": 10,
        "status": "SKIPPED_BY_DECISION",
        "skipped_by_user_id": 7,
        "skipped_at": "2026-09-10T12:00:00+00:00",
        "skip_reason": "incomplete source",
    }
    assert service._approval_decision_fingerprint([pending]) == service._approval_decision_fingerprint([completed])
    assert service._approval_decision_fingerprint([pending]) != service._approval_decision_fingerprint([skipped])
