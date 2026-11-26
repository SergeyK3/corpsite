"""Reviewable self-service changes to existing relatives."""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, ConfigDict, Field

from app.auth import get_current_user
from app.api.ppr_card_command_router import Relative
from app.services import relative_change_request_service as service
from app.services import self_change_review_service

router = APIRouter(prefix="/api/ppr", tags=["relative-change-requests"])


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_updated_at: datetime
    proposed: Relative


class Addition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposed: Relative


class Resubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    expected_updated_at: datetime | None = None
    proposed: Relative


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    action: Literal["approve", "return"]
    reason: str = Field(default="", max_length=2000)


class ReviewItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["photo", "relative"]
    id: UUID
    expected_revision: int = Field(ge=1)
    action: Literal["approve", "return"]
    reason: str = Field(default="", max_length=2000)


class CompleteReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decisions: list[ReviewItem] = Field(min_length=1)


@router.get("/me/relative-change-requests")
def my_requests(user: dict = Depends(get_current_user)):
    return {"items": service.list_mine(user)}


@router.post("/me/relatives/{relative_id}/change-requests", status_code=201)
def submit(body: Proposal, relative_id: int = Path(ge=1), user: dict = Depends(get_current_user)):
    return service.submit(user, relative_id, body.expected_updated_at, body.proposed.model_dump(mode="json"))


@router.post("/me/relatives/change-requests", status_code=201)
def submit_addition(body: Addition, user: dict = Depends(get_current_user)):
    return service.submit_addition(user, body.proposed.model_dump(mode="json"))


@router.post("/me/relative-change-requests/{request_id}/resubmit")
def resubmit(request_id: UUID, body: Resubmission, user: dict = Depends(get_current_user)):
    return service.resubmit(user, request_id, body.expected_revision, body.expected_updated_at,
                            body.proposed.model_dump(mode="json"))


@router.get("/relative-change-requests/review-queue")
def review_queue(user: dict = Depends(get_current_user)):
    return {"items": service.review_queue(user)}


@router.post("/relative-change-requests/{request_id}/decision")
def decide(request_id: UUID, body: Decision, user: dict = Depends(get_current_user)):
    return service.decide(user, request_id, body.expected_revision, body.action, body.reason)


@router.post("/self-change-review/persons/{person_id}/complete")
def complete_review(person_id: int, body: CompleteReview, user: dict = Depends(get_current_user)):
    return self_change_review_service.complete(user, person_id,
        [item.model_dump(mode="json") for item in body.decisions])
