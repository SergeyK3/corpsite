"""Shared PMF service types, errors, and plugin protocol."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

from sqlalchemy.engine import Connection


class PersonnelMigrationError(Exception):
    """Base error for PMF service layer."""


class PersonnelMigrationValidationError(PersonnelMigrationError):
    """Invalid input or precondition failure."""

    def __init__(
        self,
        message: str,
        *,
        item_errors: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.item_errors = item_errors or []


class PersonnelMigrationConflictError(PersonnelMigrationError):
    """Run/item state conflict (wrong status, already committed)."""


class PersonnelMigrationNotFoundError(LookupError, PersonnelMigrationError):
    """Run, item, domain, or target record not found."""


@dataclass(frozen=True)
class RunContext:
    run_id: int
    domain_code: str
    employee_context_id: Optional[int]
    person_id: int
    run_status: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DraftItemContext:
    item_id: int
    run_id: int
    domain_code: str
    source_kind: str
    source_record_id: Optional[str]
    import_batch_id: Optional[int]
    import_row_id: Optional[int]
    record_kind: Optional[str]
    draft_payload: dict[str, Any]
    source_payload: dict[str, Any]
    validation_errors: list[Any]


@dataclass(frozen=True)
class WrittenRecord:
    item_id: int
    target_table_name: str
    target_record_id: int


class PersonnelMigrationDomainPlugin(Protocol):
    domain_code: str

    def validate_draft(
        self,
        conn: Connection,
        *,
        item: DraftItemContext,
        run: RunContext,
    ) -> list[str]:
        """Return human-readable validation errors (empty list = valid)."""

    def write_records(
        self,
        conn: Connection,
        *,
        run: RunContext,
        items: list[DraftItemContext],
        actor_id: str,
    ) -> list[WrittenRecord]:
        """Insert person-owned target rows; return mapping per item."""

    def event_type_for_commit(self) -> str: ...

    def event_type_for_void(self) -> str: ...

    def event_type_for_supersede(self) -> str: ...

    def target_table_for_record_kind(self, record_kind: str) -> str: ...

    def void_target_record(
        self,
        conn: Connection,
        *,
        target_table_name: str,
        target_record_id: int,
        void_reason: str,
    ) -> None:
        """Set lifecycle_status=voided on a committed target row."""

    def supersede_target_record(
        self,
        conn: Connection,
        *,
        run: RunContext,
        target_table_name: str,
        target_record_id: int,
        replacement_payload: dict[str, Any],
        actor_id: str,
        provenance: dict[str, Any],
    ) -> WrittenRecord:
        """Mark old record superseded and insert replacement active record."""
