"""ADR-042 Phase B4 — Pydantic schemas for sysadmin REST API."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class MatchedGrantOut(BaseModel):
    grant_id: int
    access_role_code: str
    access_level: str
    level_rank: int
    target_type: str
    target_id: int
    resource_key: Optional[str] = None


class EffectiveAccessResponse(BaseModel):
    user_id: Optional[int] = None
    person_id: Optional[int] = None
    employee_id: Optional[int] = None
    effective_role_code: str
    access_level: str
    level_rank: int
    matched_grants: List[Dict[str, Any]] = Field(default_factory=list)
    deny_grants: List[Dict[str, Any]] = Field(default_factory=list)
    explanation: Dict[str, Any] = Field(default_factory=dict)


class AccessGrantCreate(BaseModel):
    access_role_id: int = Field(..., ge=1)
    target_type: str = Field(..., min_length=1, max_length=32)
    target_id: int = Field(..., ge=1)
    resource_key: str = Field(default="*", max_length=200)
    scope_type: str = Field(default="GLOBAL", max_length=32)
    scope_id: Optional[int] = Field(default=None, ge=1)
    include_subtree: bool = False
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    reason: Optional[str] = Field(default=None, max_length=500)


class AccessGrantResponse(BaseModel):
    grant_id: int
    access_role_id: Optional[int] = None
    access_role_code: Optional[str] = None
    access_level: Optional[str] = None
    level_rank: Optional[int] = None
    target_type: Optional[str] = None
    target_id: Optional[int] = None
    resource_key: Optional[str] = None
    scope_type: Optional[str] = None
    scope_id: Optional[int] = None
    include_subtree: Optional[bool] = None
    starts_at: Optional[str] = None
    ends_at: Optional[str] = None
    active_flag: Optional[bool] = None
    granted_by_user_id: Optional[int] = None
    reason: Optional[str] = None
    created_at: Optional[str] = None
    revoked_at: Optional[str] = None
    revoked_by_user_id: Optional[int] = None
    audit_id: Optional[int] = None
    revoked: Optional[bool] = None
    already_revoked: Optional[bool] = None


class EnrollmentQueueItemResponse(BaseModel):
    queue_id: int
    person_id: Optional[int] = None
    assignment_id: Optional[int] = None
    change_event_id: Optional[int] = None
    queue_status: str
    reason: str
    detected_at: Optional[str] = None
    resolved_at: Optional[str] = None
    resolved_by_user_id: Optional[int] = None
    decision_comment: Optional[str] = None
    idempotency_key: Optional[str] = None


class EnrollmentDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    comment: Optional[str] = Field(default=None, max_length=2000)


class EnrollmentDetectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch_id: Optional[int] = Field(default=None, ge=1)
    dry_run: bool = False
    limit: int = Field(default=500, ge=1, le=2000)


class AssignmentDriftItem(BaseModel):
    employee_id: int
    person_id: Optional[int] = None
    assignment_id: Optional[int] = None
    has_primary_assignment: bool = False
    has_drift: bool = False
    diff: Dict[str, Any] = Field(default_factory=dict)


class AssignmentDriftResponse(BaseModel):
    items: List[AssignmentDriftItem] = Field(default_factory=list)
    total: int = 0
    limit: int = 100
    offset: int = 0


class SecurityAuditEventResponse(BaseModel):
    audit_id: int
    event_type: str
    happened_at: Optional[str] = None
    actor_user_id: Optional[int] = None
    actor_login: Optional[str] = None
    actor_label: Optional[str] = None
    target_user_id: Optional[int] = None
    target_user_login: Optional[str] = None
    target_user_label: Optional[str] = None
    target_person_id: Optional[int] = None
    target_person_label: Optional[str] = None
    target_employee_id: Optional[int] = None
    target_employee_label: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    success: bool = True
    failure_reason: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    request_id: Optional[str] = None


class AdminUserResponse(BaseModel):
    user_id: int
    employee_id: Optional[int] = None
    full_name: Optional[str] = None
    login: Optional[str] = None
    role_id: Optional[int] = None
    role_name: Optional[str] = None
    unit_id: Optional[int] = None
    is_active: bool = True
    must_change_password: bool = False
    locked_at: Optional[str] = None
    locked_reason: Optional[str] = None
    token_version: int = 1
    created_at: Optional[str] = None


class AccessRoleRefResponse(BaseModel):
    access_role_id: int
    code: str
    label: str
    description: Optional[str] = None
    access_level: Optional[str] = None
    level_rank: Optional[int] = None
    active_flag: bool = True


class AccessTargetSearchItem(BaseModel):
    target_type: str
    target_id: int
    label: Optional[str] = None
    subtitle: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AccessTargetSearchResponse(BaseModel):
    items: List[AccessTargetSearchItem] = Field(default_factory=list)
    target_type: str
    q: str = ""
    limit: int = 20


class GuardModeResponse(BaseModel):
    guard_mode: str
    message: str
    enforcement_active: bool = False
    shadow_mode: bool = False


class BulkReconcileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_ids: List[int] = Field(default_factory=list)
    all_drift: bool = False
    dry_run: bool = True
    limit: int = Field(default=500, ge=1, le=2000)


class BulkEnrollmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queue_ids: List[int] = Field(..., min_length=1)
    comment: Optional[str] = Field(default=None, max_length=2000)
