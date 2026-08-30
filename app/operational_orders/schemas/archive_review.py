"""Read-only transport schemas for archive-import staging review."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ArchiveInitialReviewState = Literal[
    "REQUISITES_PRECONFIRMED",
    "NEEDS_REQUISITES",
    "NEEDS_DOCUMENT_TYPE",
    "POSSIBLE_NON_ORDER",
]
ArchiveReviewOutcome = Literal[
    "CONFIRMED",
    "NEEDS_CLARIFICATION",
    "DRAFT_ORDER",
    "ORDER_ANNEX",
    "SUPPORTING_DOCUMENT",
    "DUPLICATE",
    "NOT_AN_ORDER",
]
ArchiveReviewOutcomeFilter = Literal[
    "UNREVIEWED",
    "CONFIRMED",
    "NEEDS_CLARIFICATION",
    "DRAFT_ORDER",
    "ORDER_ANNEX",
    "SUPPORTING_DOCUMENT",
    "DUPLICATE",
    "NOT_AN_ORDER",
]


class ArchiveReviewBatchOut(BaseModel):
    batch_id: int
    batch_fingerprint: str
    source_manifest_name: str
    imported_at: datetime
    actor_user_id: int


class ArchiveReviewInitialQualityOut(BaseModel):
    total: int
    preconfirmed: int
    incomplete: int
    state_counts: dict[str, int] = Field(default_factory=dict)


class ArchiveReviewWorkQueueOut(BaseModel):
    pending_review: int
    needs_clarification: int
    completed_review: int
    outcome_counts: dict[str, int] = Field(default_factory=dict)


class ArchiveReviewStatsOut(BaseModel):
    initial_quality: ArchiveReviewInitialQualityOut
    work_queue: ArchiveReviewWorkQueueOut
    archive_section_count: int
    extension_counts: dict[str, int] = Field(default_factory=dict)
    duplicate_sha_excel_rows: list[int] = Field(default_factory=list)
    repeated_298_excel_rows: list[int] = Field(default_factory=list)


class ArchiveReviewRowOut(BaseModel):
    row_id: int
    excel_row: int
    archive_section: str
    file_name: str
    source_status: str
    initial_review_state: ArchiveInitialReviewState
    order_number: str | None
    order_date: date | None
    subject: str
    relative_path: str
    duplicate_sha: bool
    repeated_298: bool
    official_document_id: int | None
    review_outcome: ArchiveReviewOutcome | None = None
    reviewer_display_name: str | None = None
    reviewed_at: datetime | None = None
    version: int


class ArchiveReviewDetailOut(ArchiveReviewRowOut):
    source_document_type: str
    confirmed_document_type: str | None
    confirmed_order_number: str | None
    confirmed_order_date: date | None
    confirmed_subject: str | None
    review_comment: str | None


class ArchiveReviewUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    review_outcome: ArchiveReviewOutcome
    confirmed_document_type: str | None = Field(default=None, max_length=200)
    confirmed_order_number: str | None = Field(default=None, max_length=100)
    confirmed_order_date: date | None = None
    confirmed_subject: str | None = Field(default=None, max_length=1000)
    review_comment: str | None = Field(default=None, max_length=2000)

    @field_validator(
        "confirmed_document_type",
        "confirmed_order_number",
        "confirmed_subject",
        "review_comment",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None


class ArchiveReviewListOut(BaseModel):
    batch: ArchiveReviewBatchOut | None
    stats: ArchiveReviewStatsOut | None
    sections: list[str] = Field(default_factory=list)
    items: list[ArchiveReviewRowOut] = Field(default_factory=list)
    total: int
    limit: int
    offset: int
