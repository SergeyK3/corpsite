"""PPR Person general read snapshot and field ownership classification (R2).

PersonRepository R2 is read-only. Cadre writes deferred to R5 UpdateGeneralSection
field routing (no persons.version, no write API in R2).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

# Identity-owned fields on persons — Person BC write authority (WP-PR-011).
# May appear on read snapshots as identity-sourced projection only.
IDENTITY_READ_FIELD_IIN = "iin"

IDENTITY_READ_FIELDS: frozenset[str] = frozenset(
    {
        IDENTITY_READ_FIELD_IIN,
        "person_status",
        "merged_into_person_id",
        "match_key",
        "source",
        "canonical_snapshot_id",
        "canonical_entry_id",
    }
)

# PPR-GENERAL cadre scalars readable from persons (WP-PR-003 §2.2, ADR-042 DDL).
# Write ownership and normalization precedence deferred to R5 — not asserted in R2.
PPR_CADRE_READ_FIELD_FULL_NAME = "full_name"
PPR_CADRE_READ_FIELD_LAST_NAME = "last_name"
PPR_CADRE_READ_FIELD_FIRST_NAME = "first_name"
PPR_CADRE_READ_FIELD_MIDDLE_NAME = "middle_name"
PPR_CADRE_READ_FIELD_BIRTH_DATE = "birth_date"

PPR_CADRE_READ_FIELDS: frozenset[str] = frozenset(
    {
        PPR_CADRE_READ_FIELD_FULL_NAME,
        PPR_CADRE_READ_FIELD_LAST_NAME,
        PPR_CADRE_READ_FIELD_FIRST_NAME,
        PPR_CADRE_READ_FIELD_MIDDLE_NAME,
        PPR_CADRE_READ_FIELD_BIRTH_DATE,
    }
)

AUDIT_READ_FIELDS: frozenset[str] = frozenset({"created_at", "updated_at"})

# R2 exposes no PersonRepository write contract. Empty by design — not a future allowlist.
PPR_WRITABLE_FIELD_NAMES: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class PersonGeneralReadSnapshot:
    """Composite read projection for PPR card / general section (not exclusively PPR-owned).

    Includes:
    - PPR cadre read candidates (name parts, birth_date);
    - identity-sourced read-only field(s) such as iin (Person BC owned);
    - audit timestamps (read-only).

    full_name and name parts are stored columns exposed as-is; repository does not
    decide canonical write precedence — deferred to R5 field router.
    """

    person_id: int
    full_name: str
    last_name: str | None
    first_name: str | None
    middle_name: str | None
    birth_date: date | None
    iin: str | None  # identity-sourced; Person BC owned; read-only in R2
    created_at: datetime
    updated_at: datetime
