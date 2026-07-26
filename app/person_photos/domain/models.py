"""Domain models for person photo canonicalization."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

RESULT_COMMITTED = "committed"
RESULT_IDEMPOTENT_OK = "idempotent_ok"
RESULT_PROVENANCE_LINKED = "provenance_linked"

MUTATION_KIND_INSERT = "insert"
MUTATION_KIND_SUPERSEDE = "supersede"
MUTATION_KIND_LINK = "link"

SECTION_CODE_PPR_PHOTO = "PPR-PHOTO"


@dataclass(frozen=True, slots=True)
class CanonicalizeIntakePhotoRequest:
    person_id: int
    application_id: int
    intake_photo_file_id: str
    canonicalization_mode: str
    actor_user_id: int | None
    correlation_id: str | None = None
    application_status_snapshot: str | None = None


@dataclass(frozen=True, slots=True)
class PersonPhotoRow:
    person_photo_id: int
    person_id: int
    file_id: str
    storage_rel_path: str
    mime_type: str
    byte_size: int
    checksum_sha256: str
    is_active: bool
    superseded_at: datetime | None


@dataclass(frozen=True, slots=True)
class PersonPhotoSourceRow:
    person_photo_source_id: int
    person_photo_id: int
    person_id: int
    source_kind: str
    canonicalization_mode: str
    source_application_id: int | None
    source_intake_photo_file_id: str | None
    command_id: str


@dataclass(frozen=True, slots=True)
class CanonicalizePersonPhotoResult:
    status: str
    person_photo_id: int
    person_photo_source_id: int | None
    command_id: str
    ppr_event_ids: tuple[int, ...]
    storage_rel_path: str | None = None
