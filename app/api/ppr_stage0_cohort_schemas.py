"""Safe Stage 0 PREVIEW/FREEZE API contracts: no IIN, FIO, or raw source payload."""
from __future__ import annotations
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

class Stage0PreviewRequest(BaseModel):
    source_batch_id: int = Field(ge=1)
    supplemental_of_run_id: Optional[int] = Field(default=None, ge=1)
    correction_details: bool = False

class Stage0FreezeRequest(Stage0PreviewRequest):
    preview_fingerprint: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")

class Stage0ParticipantOut(BaseModel):
    position: int
    employee_id: int
    person_id: int
    source_batch_id: int
    source_row_id: int
    safe_fingerprint: str
    display_name: Optional[str] = None

class Stage0BlockerOut(BaseModel):
    employee_id: Optional[int] = None
    person_id: Optional[int] = None
    source_batch_id: Optional[int] = None
    source_row_id: Optional[int] = None
    category: str
    reason_code: str
    safe_detail: str
    candidate_key: str
    display_name: Optional[str] = None

class Stage0PreviewOut(BaseModel):
    source_batch_id: int
    source_batch_status: str
    preview_fingerprint: str
    counts: Dict[str, int]
    eligible: List[Stage0ParticipantOut]
    blockers: List[Stage0BlockerOut]

class Stage0FreezeOut(BaseModel):
    stage0_cohort_run_id: int
    replay: bool
    counts: Dict[str, int]

class Stage0RunOut(BaseModel):
    run: dict
    participants: List[Stage0ParticipantOut]

class Stage0BlockerListOut(BaseModel):
    items: List[Stage0BlockerOut]

class Stage0SourceBatchOut(BaseModel):
    batch_id: int
    status: str
    imported_at: Optional[datetime] = None
    source_row_count: int

class Stage0SourceBatchListOut(BaseModel):
    items: List[Stage0SourceBatchOut]
