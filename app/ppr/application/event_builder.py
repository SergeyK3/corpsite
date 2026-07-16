"""Canonical PPR event builders for application write path (R5)."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.ppr.domain.event_models import (
    DEFAULT_PPR_EVENT_SCHEMA_VERSION,
    EVENT_CATEGORY_LIFECYCLE,
    EVENT_CATEGORY_SECTION,
    EVENT_TYPE_PPR_CREATED,
    EVENT_TYPE_PPR_LIFECYCLE_CHANGED,
    EVENT_TYPE_PPR_SECTION_ADDED,
    EVENT_TYPE_PPR_SECTION_SUPERSEDED,
    EVENT_TYPE_PPR_SECTION_UPDATED,
    EVENT_TYPE_PPR_SECTION_VOIDED,
    PprEventAppendRequest,
)
from app.ppr.domain.section_models import (
    MUTATION_KIND_INSERT,
    MUTATION_KIND_SUPERSEDE,
    MUTATION_KIND_UPDATE,
    MUTATION_KIND_VOID,
    SectionMutationResult,
    SectionRecord,
)

METADATA_TABLE_ENVELOPE = "personnel_record_metadata"


def build_ppr_created_event(
    *,
    person_id: int,
    actor_id: str,
    command_id: str,
    correlation_id: str | None,
    hr_relationship_context: str,
    envelope_version: int,
) -> PprEventAppendRequest:
    return PprEventAppendRequest(
        person_id=person_id,
        event_type=EVENT_TYPE_PPR_CREATED,
        category=EVENT_CATEGORY_LIFECYCLE,
        record_table_name=METADATA_TABLE_ENVELOPE,
        record_id=person_id,
        actor_id=actor_id,
        command_id=command_id,
        correlation_id=correlation_id,
        payload={
            "hr_relationship_context": hr_relationship_context,
            "envelope_version": envelope_version,
        },
        schema_version=DEFAULT_PPR_EVENT_SCHEMA_VERSION,
    )


def build_lifecycle_changed_event(
    *,
    person_id: int,
    actor_id: str,
    command_id: str,
    correlation_id: str | None,
    previous_state: str,
    new_state: str,
    command_type: str,
    envelope_version: int,
) -> PprEventAppendRequest:
    return PprEventAppendRequest(
        person_id=person_id,
        event_type=EVENT_TYPE_PPR_LIFECYCLE_CHANGED,
        category=EVENT_CATEGORY_LIFECYCLE,
        record_table_name=METADATA_TABLE_ENVELOPE,
        record_id=person_id,
        actor_id=actor_id,
        command_id=command_id,
        correlation_id=correlation_id,
        payload={
            "previous_state": previous_state,
            "new_state": new_state,
            "command_type": command_type,
            "envelope_version": envelope_version,
        },
        schema_version=DEFAULT_PPR_EVENT_SCHEMA_VERSION,
    )


def _section_table_name(section_code: str) -> str:
    if section_code == "PPR-EDUCATION":
        return "person_education"
    if section_code == "PPR-TRAINING":
        return "person_training"
    if section_code == "PPR-FAMILY":
        return "person_relatives"
    if section_code == "PPR-EMPLOYMENT-BIOGRAPHY":
        return "person_external_employment"
    if section_code == "PPR-MILITARY":
        return "person_military_service"
    raise ValueError(f"Unsupported section_code: {section_code!r}")


def _section_event_type(mutation_kind: str) -> str:
    mapping = {
        MUTATION_KIND_INSERT: EVENT_TYPE_PPR_SECTION_ADDED,
        MUTATION_KIND_UPDATE: EVENT_TYPE_PPR_SECTION_UPDATED,
        MUTATION_KIND_VOID: EVENT_TYPE_PPR_SECTION_VOIDED,
        MUTATION_KIND_SUPERSEDE: EVENT_TYPE_PPR_SECTION_SUPERSEDED,
    }
    try:
        return mapping[mutation_kind]
    except KeyError as exc:
        raise ValueError(f"Unknown mutation_kind: {mutation_kind!r}") from exc


def build_section_event(
    *,
    person_id: int,
    actor_id: str,
    command_id: str,
    correlation_id: str | None,
    employee_context_id: int | None,
    mutation: SectionMutationResult,
) -> PprEventAppendRequest:
    record = mutation.record
    section_code = record.section_code
    record_id = record.record_id or 0
    payload: dict[str, Any] = {
        "person_id": person_id,
        "section_code": section_code,
        "record_id": record_id,
        "mutation_kind": mutation.mutation_kind,
        "command_id": command_id,
    }
    if mutation.prior_record is not None and mutation.prior_record.record_id is not None:
        payload["prior_record_id"] = mutation.prior_record.record_id
    if employee_context_id is not None:
        payload["employee_context_id"] = employee_context_id

    return PprEventAppendRequest(
        person_id=person_id,
        event_type=_section_event_type(mutation.mutation_kind),
        category=EVENT_CATEGORY_SECTION,
        record_table_name=_section_table_name(section_code),
        record_id=record_id,
        actor_id=actor_id,
        command_id=command_id,
        correlation_id=correlation_id,
        section_code=section_code,
        employee_context_id=employee_context_id,
        payload=payload,
        schema_version=DEFAULT_PPR_EVENT_SCHEMA_VERSION,
    )


def fingerprint_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return dict(payload)
