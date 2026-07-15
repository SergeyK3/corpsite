"""PPR identity resolution domain types (R2)."""
from __future__ import annotations

from dataclasses import dataclass

INPUT_KIND_PERSON_ID = "person_id"
INPUT_KIND_EMPLOYEE_ID = "employee_id"

RESULT_DIRECT = "DIRECT"
RESULT_MERGE_REDIRECTED = "MERGE_REDIRECTED"

PERSON_STATUS_ACTIVE = "active"
PERSON_STATUS_INACTIVE = "inactive"
PERSON_STATUS_MERGED = "merged"

PERSON_STATUSES = (
    PERSON_STATUS_ACTIVE,
    PERSON_STATUS_INACTIVE,
    PERSON_STATUS_MERGED,
)

# Conservative fail-closed limit for merge redirect chains (WP-PR-010 / ADR-054).
MAX_MERGE_REDIRECT_DEPTH = 32


@dataclass(frozen=True, slots=True)
class PersonIdentitySnapshot:
    """Identity-owned person row slice for resolution (not cadre writable subset)."""

    person_id: int
    person_status: str
    merged_into_person_id: int | None
    match_key: str
    iin: str | None


@dataclass(frozen=True, slots=True)
class IdentityResolution:
    """Result of resolving a person_id or employee_id to canonical survivor person_id."""

    input_kind: str
    input_id: int
    employee_id: int | None
    source_person_id: int
    resolved_person_id: int
    merge_redirected: bool
    merge_chain: tuple[int, ...]
    result_code: str
