"""Personnel Intake domain models."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


def empty_intake_draft_payload() -> dict[str, Any]:
    """Default empty draft structure for a new intake session."""
    return {
        "personal": {
            "last_name": "",
            "first_name": "",
            "middle_name": "",
            "birth_date": "",
            "birth_place": "",
            "gender": "",
            "citizenship": "",
            "nationality": "",
        },
        "contacts": {
            "mobile_phone": "",
            "email": "",
            "registration_address": "",
            "residence_address": "",
        },
        "education": [],
        "training": [],
        "relatives": [],
        "employment_biography": [],
        "military": {
            "status": "",
            "rank": "",
            "category": "",
            "composition": "",
            "specialty_code": "",
            "fitness_category": "",
            "commissariat": "",
            "registration_group": "",
            "registration_category": "",
        },
        "current_step": "personal",
    }


@dataclass(frozen=True, slots=True)
class IntakeLinkSnapshot:
    link_id: int
    application_id: int
    status: str
    issued_at: datetime
    issued_by_user_id: int
    expires_at: datetime
    opened_at: datetime | None
    submitted_at: datetime | None
    revoked_at: datetime | None
    revoked_by_user_id: int | None
    superseded_by_link_id: int | None
    created_at: datetime
    updated_at: datetime
    token_ciphertext: str | None = None


@dataclass(frozen=True, slots=True)
class IntakeDraftSnapshot:
    draft_id: int
    application_id: int
    link_id: int
    status: str
    payload: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    submitted_at: datetime | None


@dataclass(frozen=True, slots=True)
class IntakeSummary:
    """HR-facing intake state for an application."""

    application_id: int
    link_status: str | None
    draft_status: str | None
    link_id: int | None
    issued_at: datetime | None
    expires_at: datetime | None
    opened_at: datetime | None
    submitted_at: datetime | None
    revoked_at: datetime | None
    intake_url_path: str | None


@dataclass(frozen=True, slots=True)
class IntakeSectionReviewSnapshot:
    review_id: int
    application_id: int
    section_code: str
    status: str
    rework_comment: str | None
    reviewed_by_user_id: int | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class IntakeTransferSnapshot:
    transfer_id: int
    application_id: int
    status: str
    result: str | None
    transferred_by_user_id: int | None
    transferred_at: datetime | None
    sections_transferred: list[str]
    command_ids: list[str]
    error_message: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class IntakeReviewState:
    application_id: int
    draft: IntakeDraftSnapshot
    sections: list[IntakeSectionReviewSnapshot]
    transfer: IntakeTransferSnapshot | None
    can_transfer: bool
    transfer_blocked_reason: str | None


@dataclass(frozen=True, slots=True)
class PersonTelegramBindingSnapshot:
    binding_id: int
    person_id: int
    telegram_user_id: int
    telegram_username: str | None
    revoked_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class PersonTelegramBotActivationSnapshot:
    activation_id: int
    person_id: int
    bot_code: str
    first_activated_at: datetime
    last_activated_at: datetime
