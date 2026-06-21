"""ADR-042 Phase E1 — personnel visibility API schemas."""
from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

TargetType = Literal["USER", "POSITION", "DEPARTMENT"]
ScopeType = Literal["ORGANIZATION", "DEPARTMENT", "DEPARTMENT_GROUP"]


class PersonnelVisibilityAssignmentCreate(BaseModel):
    target_type: TargetType
    target_user_id: Optional[int] = Field(default=None, ge=1)
    target_position_id: Optional[int] = Field(default=None, ge=1)
    target_department_id: Optional[int] = Field(default=None, ge=1)
    scope_type: ScopeType
    scope_department_id: Optional[int] = Field(default=None, ge=1)
    scope_department_group_id: Optional[int] = Field(default=None, ge=1)
    can_view_personnel: bool = True
    can_view_tasks: bool = False

    @model_validator(mode="after")
    def validate_refs(self) -> "PersonnelVisibilityAssignmentCreate":
        tt = self.target_type
        if tt == "USER" and self.target_user_id is None:
            raise ValueError("target_user_id is required for USER target")
        if tt == "POSITION" and self.target_position_id is None:
            raise ValueError("target_position_id is required for POSITION target")
        if tt == "DEPARTMENT" and self.target_department_id is None:
            raise ValueError("target_department_id is required for DEPARTMENT target")

        st = self.scope_type
        if st == "DEPARTMENT" and self.scope_department_id is None:
            raise ValueError("scope_department_id is required for DEPARTMENT scope")
        if st == "DEPARTMENT_GROUP" and self.scope_department_group_id is None:
            raise ValueError("scope_department_group_id is required for DEPARTMENT_GROUP scope")
        return self


class PersonnelVisibilityAssignmentResponse(BaseModel):
    assignment_id: int
    target_type: str
    target_user_id: Optional[int] = None
    target_position_id: Optional[int] = None
    target_department_id: Optional[int] = None
    scope_type: str
    scope_department_id: Optional[int] = None
    scope_department_group_id: Optional[int] = None
    can_view_personnel: bool
    can_view_tasks: bool
    is_active: bool
    created_at: Optional[datetime] = None
    created_by_user_id: Optional[int] = None
    revoked_at: Optional[datetime] = None
    revoked_by_user_id: Optional[int] = None
    revoke_reason: Optional[str] = None


class PersonnelVisibilityAssignmentListResponse(BaseModel):
    items: List[PersonnelVisibilityAssignmentResponse]
    total: int
    limit: int
    offset: int


class PersonnelVisibilityRevokeRequest(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=500)


class EffectivePersonnelVisibilityResponse(BaseModel):
    has_visibility: bool
    show_org_sidebar: bool
    organization_wide: bool
    scope_unit_ids: Optional[List[int]] = None
    can_view_personnel: bool
    can_view_tasks: bool
    source: str
    matched_assignment_ids: List[int] = Field(default_factory=list)
    implicit_from_access_level: bool = False
