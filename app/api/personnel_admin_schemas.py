"""ADR-043 Phase C4.1 — Pydantic schemas for personnel lifecycle REST API."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class LifecycleRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    previous_snapshot_id: int = Field(..., ge=1)
    snapshot_id: int = Field(..., ge=1)
    refresh_cache: bool = True
    enqueue: bool = False
    sync_persons: bool = False


class LifecycleRunSummary(BaseModel):
    run_id: int
    previous_snapshot_id: int
    snapshot_id: int
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    actor_user_id: Optional[int] = None
    dry_run: bool
    refresh_cache: bool
    enqueue: bool
    sync_persons: bool
    effective_entries_processed: int = 0
    events_created: int = 0
    events_existing: int = 0
    enrollment_created: int = 0
    enrollment_existing: int = 0
    persons_created: int = 0
    persons_updated: int = 0
    assignments_created: int = 0
    assignments_updated: int = 0
    assignments_closed: int = 0
    warnings_count: int = 0
    errors_count: int = 0


class LifecycleRunListResponse(BaseModel):
    items: List[LifecycleRunSummary]
    total: int
    limit: int
    offset: int


class LifecycleRunDetail(LifecycleRunSummary):
    summary: Dict[str, Any] = Field(default_factory=dict)


class LifecycleRunReportResponse(BaseModel):
    run_id: Optional[int] = None
    previous_snapshot_id: int
    snapshot_id: int
    dry_run: bool
    refresh_cache: bool
    enqueue: bool
    sync_persons: bool
    run_status: str
    duration_ms: float = 0.0
    effective_cache: Dict[str, Any] = Field(default_factory=dict)
    monthly_diff: Dict[str, Any] = Field(default_factory=dict)
    personnel_events: Dict[str, Any] = Field(default_factory=dict)
    enrollment: Dict[str, Any] = Field(default_factory=dict)
    person_sync: Dict[str, Any] = Field(default_factory=dict)
    validation: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    errors: List[Dict[str, Any]] = Field(default_factory=list)


class PersonnelEventSummary(BaseModel):
    personnel_event_id: int
    previous_snapshot_id: int
    snapshot_id: int
    person_key: str
    assignment_key: Optional[str] = None
    event_type: str
    status: str
    field_path: Optional[str] = None
    person_id: Optional[int] = None
    assignment_id: Optional[int] = None
    detected_at: Optional[str] = None
    resolved_at: Optional[str] = None


class PersonnelEventListResponse(BaseModel):
    items: List[PersonnelEventSummary]
    total: int
    limit: int
    offset: int


class PersonnelEventDetail(PersonnelEventSummary):
    source_event_id: Optional[int] = None
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None
    effective_old_value: Optional[Any] = None
    effective_new_value: Optional[Any] = None
    resolved_by_user_id: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OverrideSummary(BaseModel):
    override_id: int
    scope_type: str
    scope_key: str
    field_path: str
    status: str
    tier: int
    owner_domain: str
    person_key: Optional[str] = None
    assignment_key: Optional[str] = None
    stale_flag: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class OverrideListResponse(BaseModel):
    items: List[OverrideSummary]
    total: int
    limit: int
    offset: int


class OverrideDetail(OverrideSummary):
    person_id: Optional[int] = None
    assignment_id: Optional[int] = None
    canonical_value: Optional[Any] = None
    override_value: Optional[Any] = None
    justification: Optional[str] = None
    evidence_url: Optional[str] = None
    created_by_user_id: Optional[int] = None
    approved_by_user_id: Optional[int] = None
    approved_at: Optional[str] = None
    supersedes_override_id: Optional[int] = None
    superseded_by_override_id: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OverrideCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope_type: str = Field(..., min_length=1, max_length=32)
    scope_key: str = Field(..., min_length=1, max_length=500)
    field_path: str = Field(..., min_length=1, max_length=200)
    override_value: Any
    tier: int = Field(..., ge=0, le=2)
    owner_domain: str = Field(..., min_length=1, max_length=32)
    canonical_value: Optional[Any] = None
    justification: Optional[str] = Field(default=None, max_length=4000)
    evidence_url: Optional[str] = Field(default=None, max_length=2000)
    person_key: Optional[str] = Field(default=None, max_length=500)
    assignment_key: Optional[str] = Field(default=None, max_length=500)
    person_id: Optional[int] = Field(default=None, ge=1)
    assignment_id: Optional[int] = Field(default=None, ge=1)
    supersedes_override_id: Optional[int] = Field(default=None, ge=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OverrideActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    comment: Optional[str] = Field(default=None, max_length=2000)
    reason: Optional[str] = Field(default=None, max_length=2000)


class EffectivePersonResponse(BaseModel):
    snapshot_id: int
    entry_id: int
    person_key: str
    assignment_key: Optional[str] = None
    scope_type: str
    record_kind: str
    entity_scope: Optional[str] = None
    canonical_payload: Dict[str, Any] = Field(default_factory=dict)
    effective_payload: Dict[str, Any] = Field(default_factory=dict)
    applied_override_ids: List[int] = Field(default_factory=list)


class ValidationCheckResponse(BaseModel):
    code: str
    severity: str
    count: int
    samples: List[Dict[str, Any]] = Field(default_factory=list)
    snapshots: List[Dict[str, Any]] = Field(default_factory=list)


class ValidationResponse(BaseModel):
    previous_snapshot_id: int
    snapshot_id: int
    checks: List[ValidationCheckResponse]
    warnings_count: int = 0
    errors_count: int = 0


class IdentityReconciliationPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: Optional[int] = Field(default=None, ge=1)


class IdentityReconciliationCandidate(BaseModel):
    person_id: int
    full_name: Optional[str] = None
    match_key: str = ""
    canonical_person_key: str = ""
    employee_id: Optional[int] = None
    resolved_iin: Optional[str] = None
    source: Optional[str] = None
    outcome: str
    would_update_person_iin: bool = False
    would_insert_employee_identity: bool = False
    message: Optional[str] = None
    error_code: Optional[str] = None


class IdentityReconciliationGate(BaseModel):
    gate_id: str
    severity: str
    blocks_execute: bool
    count: int
    passed: bool
    message: str = ""
    violations: List[Dict[str, Any]] = Field(default_factory=list)


class IdentityReconciliationReportResponse(BaseModel):
    phase: str
    dry_run: bool
    snapshot_id: Optional[int] = None
    generated_at: str
    blocking: bool
    execute_allowed: bool
    summary: Dict[str, Any] = Field(default_factory=dict)
    gates: List[IdentityReconciliationGate] = Field(default_factory=list)
    apply_preview: List[Dict[str, Any]] = Field(default_factory=list)
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    incomplete: List[Dict[str, Any]] = Field(default_factory=list)
    already_filled: List[Dict[str, Any]] = Field(default_factory=list)
    employee_identity_gaps: List[Dict[str, Any]] = Field(default_factory=list)
    candidates: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    validated_at: Optional[str] = None


class IdentityReconciliationExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: Optional[int] = Field(default=None, ge=1)
    person_id: Optional[int] = Field(default=None, ge=1)
    limit: Optional[int] = Field(default=None, ge=1, le=500)


class IdentityReconciliationExecuteResponse(IdentityReconciliationReportResponse):
    run_id: Optional[int] = None
    execute_summary: Dict[str, Any] = Field(default_factory=dict)
    item_results: List[Dict[str, Any]] = Field(default_factory=list)


class UserLinkageCandidate(BaseModel):
    user_id: int
    login: Optional[str] = None
    proposed_employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    match_strategy: Optional[str] = None
    classification: str
    confidence: Optional[str] = None
    reason_codes: List[str] = Field(default_factory=list)
    blockers: List[str] = Field(default_factory=list)
    requires_manual_confirmation: bool = False


class UserLinkagePreviewSummary(BaseModel):
    total_users: int
    auto_link_safe: int
    review_required: int
    ambiguous: int
    impossible: int
    excluded: int


class UserLinkagePreviewResponse(BaseModel):
    phase: str
    dry_run: bool
    generated_at: str
    summary: UserLinkagePreviewSummary
    candidates: List[UserLinkageCandidate]


class UserLinkageReviewCandidate(UserLinkageCandidate):
    user_full_name: Optional[str] = None
    decision_state: str = "PENDING"
    latest_decision_id: Optional[int] = None
    latest_decision_at: Optional[str] = None
    reviewer_user_id: Optional[int] = None
    reviewer_login: Optional[str] = None
    decision_reason: Optional[str] = None


class UserLinkageReviewSummary(BaseModel):
    review_required: int
    ambiguous: int
    approved: int
    rejected: int
    deferred: int
    pending: int


class UserLinkageReviewQueueResponse(BaseModel):
    phase: str
    generated_at: str
    summary: UserLinkageReviewSummary
    candidates: List[UserLinkageReviewCandidate]
    total: int
    limit: int
    offset: int


class UserLinkageReviewActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Optional[str] = Field(default=None, max_length=2000)


class UserLinkageReviewDecisionResponse(BaseModel):
    decision_id: int
    reviewer_user_id: int
    user_id: int
    proposed_employee_id: Optional[int] = None
    classification: str
    match_strategy: Optional[str] = None
    decision: str
    reason: Optional[str] = None
    created_at: Optional[str] = None


class UserLinkageReviewAuditItem(BaseModel):
    decision_id: int
    reviewer_user_id: int
    reviewer_login: Optional[str] = None
    user_id: int
    user_login: Optional[str] = None
    user_full_name: Optional[str] = None
    proposed_employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    classification: str
    match_strategy: Optional[str] = None
    decision: str
    reason: Optional[str] = None
    created_at: Optional[str] = None


class UserLinkageReviewAuditResponse(BaseModel):
    items: List[UserLinkageReviewAuditItem]
    total: int
    limit: int
    offset: int
