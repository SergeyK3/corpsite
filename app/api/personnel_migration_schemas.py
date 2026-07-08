"""Pydantic schemas for PMF-3A/3B personnel migration API."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MigrationDomainOut(BaseModel):
    domain_code: str
    display_name: str
    description: Optional[str] = None
    is_enabled: bool
    target_table_names: List[str] = Field(default_factory=list)
    control_list_columns: List[str] = Field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class MigrationDomainListResponse(BaseModel):
    items: List[MigrationDomainOut]


class CreateDraftRunRequest(BaseModel):
    domain_code: str = Field(min_length=1, max_length=100)
    employee_context_id: int = Field(ge=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MigrationItemOut(BaseModel):
    item_id: int
    run_id: int
    domain_code: str
    source_kind: str
    source_record_id: Optional[str] = None
    import_batch_id: Optional[int] = None
    import_row_id: Optional[int] = None
    record_kind: Optional[str] = None
    target_table_name: Optional[str] = None
    target_record_id: Optional[int] = None
    item_status: str
    draft_payload: Dict[str, Any] = Field(default_factory=dict)
    source_payload: Dict[str, Any] = Field(default_factory=dict)
    validation_errors: List[Any] = Field(default_factory=list)
    created_at: Optional[str] = None
    committed_at: Optional[str] = None
    voided_at: Optional[str] = None
    void_reason: Optional[str] = None


class MigrationRunOut(BaseModel):
    run_id: int
    domain_code: str
    employee_context_id: Optional[int] = None
    person_id: Optional[int] = None
    run_status: str
    started_at: Optional[str] = None
    committed_at: Optional[str] = None
    voided_at: Optional[str] = None
    started_by: Optional[str] = None
    committed_by: Optional[str] = None
    voided_by: Optional[str] = None
    void_reason: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    items: List[MigrationItemOut] = Field(default_factory=list)


class CreateDraftRunResponse(BaseModel):
    run: MigrationRunOut


class AddDraftItemRequest(BaseModel):
    source_kind: str = Field(min_length=1, max_length=100)
    source_record_id: Optional[str] = Field(default=None, max_length=500)
    import_batch_id: Optional[int] = Field(default=None, ge=1)
    import_row_id: Optional[int] = Field(default=None, ge=1)
    record_kind: Optional[str] = Field(default=None, max_length=100)
    draft_payload: Dict[str, Any] = Field(default_factory=dict)
    source_payload: Dict[str, Any] = Field(default_factory=dict)


class AddDraftItemResponse(BaseModel):
    item: MigrationItemOut
    run: MigrationRunOut


class CommitRunRequest(BaseModel):
    confirm: bool = True


class CommittedItemOut(BaseModel):
    item_id: int
    target_table_name: str
    target_record_id: int
    event_id: int


class CommitRunResponse(BaseModel):
    run: MigrationRunOut
    committed_items: List[CommittedItemOut]
    event_ids: List[int]


class VoidRunRequest(BaseModel):
    void_reason: str = Field(min_length=1, max_length=2000)


class VoidedItemOut(BaseModel):
    item_id: int
    target_table_name: str
    target_record_id: int
    event_id: int


class VoidRunResponse(BaseModel):
    run: MigrationRunOut
    voided_items: List[VoidedItemOut]
    event_ids: List[int]


class SupersedeRecordRequest(BaseModel):
    domain_code: str = Field(min_length=1, max_length=100)
    employee_context_id: int = Field(ge=1)
    record_table_name: str = Field(min_length=1, max_length=100)
    record_id: int = Field(ge=1)
    replacement_payload: Dict[str, Any] = Field(default_factory=dict)
    provenance: Dict[str, Any] = Field(default_factory=dict)


class SupersedeRecordResponse(BaseModel):
    superseded_record_id: int
    replacement_record_id: int
    target_table_name: str
    supersede_event_id: int
    migrate_event_id: int


class PersonnelRecordEventOut(BaseModel):
    event_id: int
    person_id: int
    employee_context_id: Optional[int] = None
    domain_code: str
    record_table_name: str
    record_id: int
    event_type: str
    event_at: Optional[str] = None
    actor_id: Optional[str] = None
    event_payload: Dict[str, Any] = Field(default_factory=dict)
    migration_run_id: Optional[int] = None
    migration_item_id: Optional[int] = None


class RecordEventListResponse(BaseModel):
    items: List[PersonnelRecordEventOut]
    total: int
    limit: int
    offset: int
