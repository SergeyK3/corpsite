"""Pydantic schemas for Personnel Intake API."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.personnel_intake.domain.models import (
    IntakeDraftSnapshot,
    IntakeLinkSnapshot,
    IntakeReviewState,
    IntakeSectionReviewSnapshot,
    IntakeSummary,
    IntakeTransferSnapshot,
)
from app.personnel_intake.domain.review_status import INTAKE_SECTION_LABELS
from app.personnel_intake.application.intake_section_utils import (
    extract_section_payload,
    is_intake_section_empty,
)


class IntakeLinkIssueOut(BaseModel):
    application_id: int
    link_id: int
    intake_url_path: str
    expires_at: datetime
    status: str
    reissued: bool = False


class IntakeSummaryOut(BaseModel):
    application_id: int
    link_status: str | None = None
    draft_status: str | None = None
    link_id: int | None = None
    issued_at: datetime | None = None
    expires_at: datetime | None = None
    opened_at: datetime | None = None
    submitted_at: datetime | None = None
    revoked_at: datetime | None = None
    intake_url_path: str | None = None


class IntakeDraftOut(BaseModel):
    application_id: int
    draft_id: int
    link_id: int
    status: str
    payload: dict[str, Any]
    read_only: bool
    link_status: str
    opened_at: datetime | None = None
    submitted_at: datetime | None = None
    expires_at: datetime | None = None


class IntakeAutosaveIn(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


class IntakeAutosaveOut(BaseModel):
    draft_id: int
    status: str
    payload: dict[str, Any]
    saved_at: datetime


class IntakeSubmitIn(BaseModel):
    payload: dict[str, Any] | None = None


class IntakeSubmitOut(BaseModel):
    application_id: int
    draft_id: int
    status: str
    submitted_at: datetime


class IntakeRevokeOut(BaseModel):
    application_id: int
    link_id: int
    status: str
    revoked_at: datetime


class IntakeLinkAccessOut(BaseModel):
    application_id: int
    display_state: str
    link_id: int | None = None
    link_status: str | None = None
    intake_url_path: str | None = None
    expires_at: datetime | None = None


class IntakeLinkRevokeIn(BaseModel):
    pass


class IntakeSectionReviewOut(BaseModel):
    section_code: str
    section_label: str
    status: str
    rework_comment: str | None = None
    reviewed_by_user_id: int | None = None
    reviewed_at: datetime | None = None
    is_empty: bool
    payload: dict[str, Any] | list[Any]


class IntakeTransferAuditOut(BaseModel):
    transfer_id: int
    application_id: int
    status: str
    result: str | None = None
    transferred_by_user_id: int | None = None
    transferred_at: datetime | None = None
    sections_transferred: list[str]
    command_ids: list[str]
    error_message: str | None = None


class IntakeReviewStateOut(BaseModel):
    application_id: int
    draft: IntakeDraftOut
    sections: list[IntakeSectionReviewOut]
    transfer: IntakeTransferAuditOut | None = None
    can_transfer: bool
    transfer_blocked_reason: str | None = None


class IntakeSectionReworkIn(BaseModel):
    comment: str = Field(..., min_length=1)


class IntakeTransferOut(BaseModel):
    application_id: int
    transfer: IntakeTransferAuditOut
    idempotent_replay: bool = False


class IntakeTransferAuditListOut(BaseModel):
    items: list[IntakeTransferAuditOut]
    total: int


class IntakeOnBehalfEditSessionOut(BaseModel):
    application_id: int
    draft: IntakeDraftOut
    editable: bool
    blocked_reason: str | None = None
    reason_code: str | None = None


class IntakeOnBehalfSaveOut(BaseModel):
    application_id: int
    draft_id: int
    status: str
    saved_at: datetime
    changed_fields: list[str]


def summary_to_out(summary: IntakeSummary, *, intake_url_path: str | None = None) -> IntakeSummaryOut:
    return IntakeSummaryOut(
        application_id=summary.application_id,
        link_status=summary.link_status,
        draft_status=summary.draft_status,
        link_id=summary.link_id,
        issued_at=summary.issued_at,
        expires_at=summary.expires_at,
        opened_at=summary.opened_at,
        submitted_at=summary.submitted_at,
        revoked_at=summary.revoked_at,
        intake_url_path=intake_url_path or summary.intake_url_path,
    )


def draft_session_to_out(
    *,
    draft: IntakeDraftSnapshot,
    link: IntakeLinkSnapshot,
    read_only: bool,
) -> IntakeDraftOut:
    return IntakeDraftOut(
        application_id=draft.application_id,
        draft_id=draft.draft_id,
        link_id=draft.link_id,
        status=draft.status,
        payload=draft.payload,
        read_only=read_only,
        link_status=link.status,
        opened_at=link.opened_at,
        submitted_at=draft.submitted_at or link.submitted_at,
        expires_at=link.expires_at,
    )


def transfer_to_out(snapshot: IntakeTransferSnapshot) -> IntakeTransferAuditOut:
    return IntakeTransferAuditOut(
        transfer_id=snapshot.transfer_id,
        application_id=snapshot.application_id,
        status=snapshot.status,
        result=snapshot.result,
        transferred_by_user_id=snapshot.transferred_by_user_id,
        transferred_at=snapshot.transferred_at,
        sections_transferred=snapshot.sections_transferred,
        command_ids=snapshot.command_ids,
        error_message=snapshot.error_message,
    )


def section_review_to_out(
    section: IntakeSectionReviewSnapshot,
    *,
    draft_payload: dict[str, Any],
) -> IntakeSectionReviewOut:
    return IntakeSectionReviewOut(
        section_code=section.section_code,
        section_label=INTAKE_SECTION_LABELS.get(section.section_code, section.section_code),
        status=section.status,
        rework_comment=section.rework_comment,
        reviewed_by_user_id=section.reviewed_by_user_id,
        reviewed_at=section.reviewed_at,
        is_empty=is_intake_section_empty(section.section_code, draft_payload),
        payload=extract_section_payload(section.section_code, draft_payload),
    )


def review_state_to_out(state: IntakeReviewState, *, link: IntakeLinkSnapshot | None) -> IntakeReviewStateOut:
    draft_out = draft_session_to_out(
        draft=state.draft,
        link=link
        or IntakeLinkSnapshot(
            link_id=state.draft.link_id,
            application_id=state.application_id,
            status="submitted",
            issued_at=state.draft.created_at,
            issued_by_user_id=0,
            expires_at=state.draft.created_at,
            opened_at=None,
            submitted_at=state.draft.submitted_at,
            revoked_at=None,
            revoked_by_user_id=None,
            superseded_by_link_id=None,
            token_ciphertext=None,
            created_at=state.draft.created_at,
            updated_at=state.draft.updated_at,
        ),
        read_only=True,
    )
    return IntakeReviewStateOut(
        application_id=state.application_id,
        draft=draft_out,
        sections=[
            section_review_to_out(section, draft_payload=state.draft.payload)
            for section in state.sections
        ],
        transfer=transfer_to_out(state.transfer) if state.transfer else None,
        can_transfer=state.can_transfer,
        transfer_blocked_reason=state.transfer_blocked_reason,
    )
