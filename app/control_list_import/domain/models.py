"""Read models for mapping profile repository (WP-CL-003)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class MappingProfileColumnSnapshot:
    profile_column_id: int
    profile_sheet_id: int
    column_index: int
    column_letter: Optional[str]
    raw_header: Optional[str]
    semantic_field: str
    parser_code: str
    is_required: bool


@dataclass(frozen=True)
class MappingProfileSheetSnapshot:
    profile_sheet_id: int
    profile_id: int
    sheet_name: str
    personnel_category: str
    employment_mode: str
    sheet_purpose: str
    header_row_override: Optional[int]
    columns: list[MappingProfileColumnSnapshot] = field(default_factory=list)


@dataclass(frozen=True)
class MappingProfileSnapshot:
    profile_id: int
    profile_code: str
    profile_version: int
    profile_name: str
    description: Optional[str]
    status: str
    created_at: datetime
    created_by: int
    updated_at: Optional[datetime]
    sheets: list[MappingProfileSheetSnapshot] = field(default_factory=list)


@dataclass(frozen=True)
class MappingProfileSummary:
    profile_id: int
    profile_code: str
    profile_version: int
    profile_name: str
    status: str
    created_at: datetime
