"""Read-only transport schemas for archive-import staging review."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


ArchiveInitialReviewState = Literal[
    "REQUISITES_PRECONFIRMED",
    "NEEDS_REQUISITES",
    "NEEDS_DOCUMENT_TYPE",
    "POSSIBLE_NON_ORDER",
]


class ArchiveReviewBatchOut(BaseModel):
    batch_id: int
    batch_fingerprint: str
    source_manifest_name: str
    imported_at: datetime
    actor_user_id: int


class ArchiveReviewStatsOut(BaseModel):
    total_records: int
    preconfirmed_records: int
    requires_processing: int
    archive_section_count: int
    state_counts: dict[str, int] = Field(default_factory=dict)
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


class ArchiveReviewListOut(BaseModel):
    batch: ArchiveReviewBatchOut | None
    stats: ArchiveReviewStatsOut | None
    sections: list[str] = Field(default_factory=list)
    items: list[ArchiveReviewRowOut] = Field(default_factory=list)
    total: int
    limit: int
    offset: int
