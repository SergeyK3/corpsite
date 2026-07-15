"""Domain-shaped PPR audit event types (R3 — append-only journal)."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

# Event categories (WP-PR-007 §3)
EVENT_CATEGORY_LIFECYCLE = "LIFECYCLE"
EVENT_CATEGORY_SECTION = "SECTION"
EVENT_CATEGORY_DERIVED = "DERIVED"
EVENT_CATEGORY_MERGE = "MERGE"
EVENT_CATEGORY_ADMIN = "ADMIN"
EVENT_CATEGORY_LEGACY = "LEGACY"

EVENT_CATEGORIES: frozenset[str] = frozenset(
    {
        EVENT_CATEGORY_LIFECYCLE,
        EVENT_CATEGORY_SECTION,
        EVENT_CATEGORY_DERIVED,
        EVENT_CATEGORY_MERGE,
        EVENT_CATEGORY_ADMIN,
        EVENT_CATEGORY_LEGACY,
    }
)

# Canonical event types (catalog contract — not emitted from production in R3)
EVENT_TYPE_PPR_CREATED = "PPR_CREATED"
EVENT_TYPE_PPR_ENVELOPE_UPDATED = "PPR_ENVELOPE_UPDATED"
EVENT_TYPE_PPR_LIFECYCLE_CHANGED = "PPR_LIFECYCLE_CHANGED"
EVENT_TYPE_PPR_SECTION_ADDED = "PPR_SECTION_ADDED"
EVENT_TYPE_PPR_SECTION_UPDATED = "PPR_SECTION_UPDATED"
EVENT_TYPE_PPR_SECTION_VOIDED = "PPR_SECTION_VOIDED"
EVENT_TYPE_PPR_SECTION_SUPERSEDED = "PPR_SECTION_SUPERSEDED"
EVENT_TYPE_PPR_COMPLETENESS_CHANGED = "PPR_COMPLETENESS_CHANGED"
EVENT_TYPE_PPR_READINESS_CHANGED = "PPR_READINESS_CHANGED"
EVENT_TYPE_PPR_MERGED = "PPR_MERGED"

CANONICAL_EVENT_TYPES: frozenset[str] = frozenset(
    {
        EVENT_TYPE_PPR_CREATED,
        EVENT_TYPE_PPR_ENVELOPE_UPDATED,
        EVENT_TYPE_PPR_LIFECYCLE_CHANGED,
        EVENT_TYPE_PPR_SECTION_ADDED,
        EVENT_TYPE_PPR_SECTION_UPDATED,
        EVENT_TYPE_PPR_SECTION_VOIDED,
        EVENT_TYPE_PPR_SECTION_SUPERSEDED,
        EVENT_TYPE_PPR_COMPLETENESS_CHANGED,
        EVENT_TYPE_PPR_READINESS_CHANGED,
        EVENT_TYPE_PPR_MERGED,
    }
)

# Legacy PMF event types (stored as-is; not canonical names)
LEGACY_EVENT_TYPE_EDUCATION_MIGRATED = "EDUCATION_MIGRATED"
LEGACY_EVENT_TYPE_EDUCATION_VOIDED = "EDUCATION_VOIDED"
LEGACY_EVENT_TYPE_EDUCATION_SUPERSEDED = "EDUCATION_SUPERSEDED"
LEGACY_EVENT_TYPE_EDUCATION_VERIFIED = "EDUCATION_VERIFIED"

LEGACY_EVENT_TYPES: frozenset[str] = frozenset(
    {
        LEGACY_EVENT_TYPE_EDUCATION_MIGRATED,
        LEGACY_EVENT_TYPE_EDUCATION_VOIDED,
        LEGACY_EVENT_TYPE_EDUCATION_SUPERSEDED,
        LEGACY_EVENT_TYPE_EDUCATION_VERIFIED,
    }
)

# Section codes
SECTION_CODE_PPR_EDUCATION = "PPR-EDUCATION"

# Payload envelope keys (stored inside event_payload JSONB until additive DDL in a later WP)
PPR_PAYLOAD_CORRELATION_ID = "correlation_id"
PPR_PAYLOAD_COMMAND_ID = "command_id"
PPR_PAYLOAD_SOURCE_EVENT_ID = "source_event_id"
PPR_PAYLOAD_SCHEMA_VERSION = "ppr_schema_version"
PPR_PAYLOAD_SECTION_CODE = "section_code"
PPR_PAYLOAD_CATEGORY = "category"
PPR_PAYLOAD_SOURCE = "source"

PPR_PAYLOAD_ENVELOPE_KEYS: frozenset[str] = frozenset(
    {
        PPR_PAYLOAD_CORRELATION_ID,
        PPR_PAYLOAD_COMMAND_ID,
        PPR_PAYLOAD_SOURCE_EVENT_ID,
        PPR_PAYLOAD_SCHEMA_VERSION,
        PPR_PAYLOAD_SECTION_CODE,
        PPR_PAYLOAD_CATEGORY,
        PPR_PAYLOAD_SOURCE,
    }
)

DEFAULT_PPR_EVENT_SCHEMA_VERSION = "1"

DOMAIN_TO_SECTION_CODE: dict[str, str] = {
    "education": SECTION_CODE_PPR_EDUCATION,
}


@dataclass(frozen=True, slots=True)
class PprEventAppendRequest:
    """Input for append-only event persistence (no generated fields).

    domain_code is a legacy/transitional PMF classification (FK when non-null).
    It is NULL for canonical non-migration PPR events (envelope/lifecycle/merge/admin).
    Section identity is represented by section_code metadata; NULL domain_code does not
    imply unknown PPR ownership — person_id remains the partition key.
    """

    person_id: int
    event_type: str
    category: str
    record_table_name: str
    record_id: int
    payload: Mapping[str, Any]
    domain_code: str | None = None
    section_code: str | None = None
    occurred_at: datetime | None = None
    actor_id: str | None = None
    command_id: str | None = None
    correlation_id: str | None = None
    source_event_id: str | None = None
    schema_version: str = DEFAULT_PPR_EVENT_SCHEMA_VERSION
    employee_context_id: int | None = None
    migration_run_id: int | None = None
    migration_item_id: int | None = None


@dataclass(frozen=True, slots=True)
class PprEventRecord:
    """Persisted append-only audit event (domain-shaped, not ORM).

    domain_code NULL means canonical PPR event without PMF migration domain coupling.
    """

    event_id: int
    person_id: int
    event_type: str
    category: str
    record_table_name: str
    record_id: int
    occurred_at: datetime
    payload: Mapping[str, Any]
    domain_code: str | None = None
    section_code: str | None = None
    actor_id: str | None = None
    command_id: str | None = None
    correlation_id: str | None = None
    source_event_id: str | None = None
    schema_version: str = DEFAULT_PPR_EVENT_SCHEMA_VERSION
    employee_context_id: int | None = None
    migration_run_id: int | None = None
    migration_item_id: int | None = None


@dataclass(frozen=True, slots=True)
class LegacyPprEventView:
    """Read-only view of a legacy personnel_record_events row for mapping."""

    event_type: str
    domain_code: str
    record_table_name: str
    record_id: int
    event_payload: Mapping[str, Any]
    migration_run_id: int | None = None
    migration_item_id: int | None = None


@dataclass(frozen=True, slots=True)
class CanonicalPprEventDescriptor:
    """Semantic canonical event descriptor — mapping output, not a persisted row."""

    event_type: str
    category: str
    section_code: str | None
    change_kind: str | None = None
    domain_code: str | None = None
