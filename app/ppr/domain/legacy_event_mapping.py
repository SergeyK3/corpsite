"""Legacy PMF event → canonical descriptor mapping contract (R3, read-only)."""
from __future__ import annotations

from app.ppr.domain.errors import (
    PprLegacyEventMappingAmbiguousError,
    PprLegacyEventMappingError,
)
from app.ppr.domain.event_models import (
    EVENT_CATEGORY_LEGACY,
    EVENT_CATEGORY_SECTION,
    EVENT_TYPE_PPR_SECTION_ADDED,
    EVENT_TYPE_PPR_SECTION_SUPERSEDED,
    EVENT_TYPE_PPR_SECTION_VOIDED,
    LEGACY_EVENT_TYPE_EDUCATION_MIGRATED,
    LEGACY_EVENT_TYPE_EDUCATION_SUPERSEDED,
    LEGACY_EVENT_TYPE_EDUCATION_VOIDED,
    CanonicalPprEventDescriptor,
    DOMAIN_TO_SECTION_CODE,
    LegacyPprEventView,
)


def _section_code_for_domain(domain_code: str) -> str | None:
    return DOMAIN_TO_SECTION_CODE.get(domain_code)


def map_legacy_event_to_canonical_descriptor(
    legacy: LegacyPprEventView,
) -> CanonicalPprEventDescriptor:
    """Map a legacy personnel_record_events row to a canonical semantic descriptor.

    Deterministic, does not write to DB or rename stored event_type.
    """
    section_code = _section_code_for_domain(legacy.domain_code)

    if legacy.event_type == LEGACY_EVENT_TYPE_EDUCATION_VOIDED:
        return CanonicalPprEventDescriptor(
            event_type=EVENT_TYPE_PPR_SECTION_VOIDED,
            category=EVENT_CATEGORY_SECTION,
            section_code=section_code,
            change_kind="void",
            domain_code=legacy.domain_code,
        )

    if legacy.event_type == LEGACY_EVENT_TYPE_EDUCATION_SUPERSEDED:
        return CanonicalPprEventDescriptor(
            event_type=EVENT_TYPE_PPR_SECTION_SUPERSEDED,
            category=EVENT_CATEGORY_SECTION,
            section_code=section_code,
            change_kind="supersede",
            domain_code=legacy.domain_code,
        )

    if legacy.event_type == LEGACY_EVENT_TYPE_EDUCATION_MIGRATED:
        payload = legacy.event_payload
        has_supersede_context = "superseded_record_id" in payload
        has_commit_context = (
            legacy.migration_run_id is not None
            or legacy.migration_item_id is not None
            or "source_kind" in payload
        )
        if has_supersede_context:
            return CanonicalPprEventDescriptor(
                event_type=EVENT_TYPE_PPR_SECTION_ADDED,
                category=EVENT_CATEGORY_SECTION,
                section_code=section_code,
                change_kind="create",
                domain_code=legacy.domain_code,
            )
        if has_commit_context:
            return CanonicalPprEventDescriptor(
                event_type=EVENT_TYPE_PPR_SECTION_ADDED,
                category=EVENT_CATEGORY_SECTION,
                section_code=section_code,
                change_kind="create",
                domain_code=legacy.domain_code,
            )
        raise PprLegacyEventMappingAmbiguousError(
            f"Cannot determine EDUCATION_MIGRATED semantics for record_id={legacy.record_id}: "
            "missing supersede, migration, and commit payload markers."
        )

    raise PprLegacyEventMappingError(
        f"Unknown legacy event_type for canonical mapping: {legacy.event_type!r}"
    )
