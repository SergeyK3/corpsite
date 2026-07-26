"""PPR event builders for canonical person photos (ADR-061 rev.3)."""
from __future__ import annotations

from typing import Any

from app.db.models.person_photos import SOURCE_KIND_INTAKE
from app.ppr.domain.event_models import (
    DEFAULT_PPR_EVENT_SCHEMA_VERSION,
    EVENT_CATEGORY_SECTION,
    EVENT_TYPE_PPR_SECTION_ADDED,
    EVENT_TYPE_PPR_SECTION_SUPERSEDED,
    PprEventAppendRequest,
)
from app.person_photos.domain.models import (
    MUTATION_KIND_INSERT,
    MUTATION_KIND_LINK,
    MUTATION_KIND_SUPERSEDE,
    SECTION_CODE_PPR_PHOTO,
)

RECORD_TABLE_PERSON_PHOTOS = "person_photos"


def build_person_photo_ppr_event(
    *,
    person_id: int,
    person_photo_id: int,
    actor_user_id: int | None,
    command_id: str,
    correlation_id: str | None,
    mutation_kind: str,
    checksum_sha256: str,
    source_kind: str = SOURCE_KIND_INTAKE,
    canonicalization_mode: str,
    source_application_id: int | None,
    source_intake_photo_file_id: str | None,
    prior_active_person_photo_id: int | None = None,
) -> PprEventAppendRequest:
    if mutation_kind == MUTATION_KIND_SUPERSEDE:
        event_type = EVENT_TYPE_PPR_SECTION_SUPERSEDED
        record_id = prior_active_person_photo_id or person_photo_id
    else:
        event_type = EVENT_TYPE_PPR_SECTION_ADDED
        record_id = person_photo_id

    payload: dict[str, Any] = {
        "person_photo_id": person_photo_id,
        "source_kind": source_kind,
        "canonicalization_mode": canonicalization_mode,
        "source_application_id": source_application_id,
        "source_intake_photo_file_id": source_intake_photo_file_id,
        "checksum_sha256": checksum_sha256,
        "mutation_kind": mutation_kind,
        "prior_active_person_photo_id": prior_active_person_photo_id,
        "section_code": SECTION_CODE_PPR_PHOTO,
        "record_id": record_id,
        "command_id": command_id,
    }
    return PprEventAppendRequest(
        person_id=person_id,
        event_type=event_type,
        category=EVENT_CATEGORY_SECTION,
        record_table_name=RECORD_TABLE_PERSON_PHOTOS,
        record_id=record_id,
        actor_id=str(actor_user_id) if actor_user_id is not None else None,
        command_id=command_id,
        correlation_id=correlation_id,
        section_code=SECTION_CODE_PPR_PHOTO,
        payload=payload,
        schema_version=DEFAULT_PPR_EVENT_SCHEMA_VERSION,
    )


def build_provenance_link_event(
    *,
    person_id: int,
    person_photo_id: int,
    actor_user_id: int | None,
    command_id: str,
    correlation_id: str | None,
    checksum_sha256: str,
    canonicalization_mode: str,
    source_application_id: int | None,
    source_intake_photo_file_id: str | None,
) -> PprEventAppendRequest:
    return build_person_photo_ppr_event(
        person_id=person_id,
        person_photo_id=person_photo_id,
        actor_user_id=actor_user_id,
        command_id=command_id,
        correlation_id=correlation_id,
        mutation_kind=MUTATION_KIND_LINK,
        checksum_sha256=checksum_sha256,
        canonicalization_mode=canonicalization_mode,
        source_application_id=source_application_id,
        source_intake_photo_file_id=source_intake_photo_file_id,
    )
