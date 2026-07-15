# tests/ppr/test_legacy_event_mapping_unit.py
"""Unit tests for legacy → canonical event mapping contract (R3, no DB)."""
from __future__ import annotations

import pytest

from app.ppr.domain.errors import (
    PprLegacyEventMappingAmbiguousError,
    PprLegacyEventMappingError,
)
from app.ppr.domain.event_models import (
    EVENT_CATEGORY_SECTION,
    EVENT_TYPE_PPR_SECTION_ADDED,
    EVENT_TYPE_PPR_SECTION_SUPERSEDED,
    EVENT_TYPE_PPR_SECTION_VOIDED,
    LEGACY_EVENT_TYPE_EDUCATION_MIGRATED,
    LEGACY_EVENT_TYPE_EDUCATION_SUPERSEDED,
    LEGACY_EVENT_TYPE_EDUCATION_VOIDED,
    SECTION_CODE_PPR_EDUCATION,
    LegacyPprEventView,
)
from app.ppr.domain.legacy_event_mapping import map_legacy_event_to_canonical_descriptor


def _legacy(
    *,
    event_type: str,
    payload: dict | None = None,
    migration_run_id: int | None = None,
    migration_item_id: int | None = None,
) -> LegacyPprEventView:
    return LegacyPprEventView(
        event_type=event_type,
        domain_code="education",
        record_table_name="person_education",
        record_id=42,
        event_payload=payload or {},
        migration_run_id=migration_run_id,
        migration_item_id=migration_item_id,
    )


def test_education_voided_maps_to_section_voided() -> None:
    descriptor = map_legacy_event_to_canonical_descriptor(
        _legacy(event_type=LEGACY_EVENT_TYPE_EDUCATION_VOIDED, payload={"void_reason": "test"})
    )
    assert descriptor.event_type == EVENT_TYPE_PPR_SECTION_VOIDED
    assert descriptor.category == EVENT_CATEGORY_SECTION
    assert descriptor.section_code == SECTION_CODE_PPR_EDUCATION
    assert descriptor.change_kind == "void"
    assert descriptor.domain_code == "education"
    assert descriptor.domain_code != "ppr_core"


def test_education_superseded_maps_to_section_superseded() -> None:
    descriptor = map_legacy_event_to_canonical_descriptor(
        _legacy(
            event_type=LEGACY_EVENT_TYPE_EDUCATION_SUPERSEDED,
            payload={"superseded_record_id": 1, "replacement_record_id": 2},
        )
    )
    assert descriptor.event_type == EVENT_TYPE_PPR_SECTION_SUPERSEDED
    assert descriptor.section_code == SECTION_CODE_PPR_EDUCATION
    assert descriptor.change_kind == "supersede"


def test_education_migrated_commit_payload_maps_to_section_added() -> None:
    descriptor = map_legacy_event_to_canonical_descriptor(
        _legacy(
            event_type=LEGACY_EVENT_TYPE_EDUCATION_MIGRATED,
            payload={
                "record_kind": "education",
                "source_kind": "manual",
                "source_record_id": "src-1",
            },
            migration_run_id=10,
            migration_item_id=20,
        )
    )
    assert descriptor.event_type == EVENT_TYPE_PPR_SECTION_ADDED
    assert descriptor.change_kind == "create"


def test_education_migrated_supersede_payload_maps_to_section_added() -> None:
    descriptor = map_legacy_event_to_canonical_descriptor(
        _legacy(
            event_type=LEGACY_EVENT_TYPE_EDUCATION_MIGRATED,
            payload={"superseded_record_id": 99},
        )
    )
    assert descriptor.event_type == EVENT_TYPE_PPR_SECTION_ADDED
    assert descriptor.change_kind == "create"


def test_unknown_legacy_type_raises() -> None:
    with pytest.raises(PprLegacyEventMappingError):
        map_legacy_event_to_canonical_descriptor(_legacy(event_type="EDUCATION_VERIFIED"))


def test_ambiguous_education_migrated_raises() -> None:
    with pytest.raises(PprLegacyEventMappingAmbiguousError):
        map_legacy_event_to_canonical_descriptor(
            _legacy(event_type=LEGACY_EVENT_TYPE_EDUCATION_MIGRATED, payload={"record_kind": "education"})
        )


def test_mapping_is_deterministic() -> None:
    legacy = _legacy(
        event_type=LEGACY_EVENT_TYPE_EDUCATION_VOIDED,
        payload={"void_reason": "dup"},
    )
    first = map_legacy_event_to_canonical_descriptor(legacy)
    second = map_legacy_event_to_canonical_descriptor(legacy)
    assert first == second


def test_descriptor_contains_section_code() -> None:
    descriptor = map_legacy_event_to_canonical_descriptor(
        _legacy(event_type=LEGACY_EVENT_TYPE_EDUCATION_VOIDED)
    )
    assert descriptor.section_code == SECTION_CODE_PPR_EDUCATION


def test_mapping_does_not_mutate_legacy_view() -> None:
    payload = {"void_reason": "keep-me"}
    legacy = _legacy(event_type=LEGACY_EVENT_TYPE_EDUCATION_VOIDED, payload=payload)
    map_legacy_event_to_canonical_descriptor(legacy)
    assert legacy.event_type == LEGACY_EVENT_TYPE_EDUCATION_VOIDED
    assert legacy.event_payload == payload
