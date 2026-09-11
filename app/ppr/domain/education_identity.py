"""Conservative identity comparison for person-owned education records.

Education is a 0..N section.  Institution and kind identify a comparison
scope, not a unique diploma.  A serial/number is the strongest discriminator;
without one we only distinguish records on independently present profile data.
"""
from __future__ import annotations

from typing import Any, Mapping


IDENTITY_FIELDS = (
    "education_kind",
    "institution_name",
    "specialty",
    "qualification",
    "completed_at",
    "diploma_number",
)
_NO_SERIAL_DISCRIMINATORS = ("specialty", "qualification", "completed_at")

EXACT = "exact"
DISTINCT = "distinct"
SERIAL_CONFLICT = "serial_conflict"
AMBIGUOUS = "ambiguous"


def normalize_education_value(value: Any) -> str | None:
    normalized = " ".join(str(value or "").strip().split())
    return normalized.casefold() if normalized else None


def education_identity_values(record: Mapping[str, Any] | Any) -> dict[str, str | None]:
    def value(field: str) -> Any:
        if isinstance(record, Mapping):
            return record.get(field)
        return getattr(record, field, None)

    return {field: normalize_education_value(value(field)) for field in IDENTITY_FIELDS}


def compare_education_identity(left: Mapping[str, Any] | Any, right: Mapping[str, Any] | Any) -> str:
    """Classify two records sharing a person without choosing a replacement.

    ``AMBIGUOUS`` deliberately never authorizes an automatic update/supersede.
    """
    a = education_identity_values(left)
    b = education_identity_values(right)
    if (a["education_kind"], a["institution_name"]) != (
        b["education_kind"],
        b["institution_name"],
    ):
        return DISTINCT
    if all(a[field] == b[field] for field in IDENTITY_FIELDS):
        return EXACT

    left_serial, right_serial = a["diploma_number"], b["diploma_number"]
    if left_serial and right_serial:
        return DISTINCT if left_serial != right_serial else SERIAL_CONFLICT

    # Where a serial is missing, only two independently supplied, different
    # values prove that these are distinct diplomas.  A value-versus-blank is
    # enrichment-versus-new-record ambiguity and must remain review-only.
    if any(
        a[field] is not None and b[field] is not None and a[field] != b[field]
        for field in _NO_SERIAL_DISCRIMINATORS
    ):
        return DISTINCT
    return AMBIGUOUS
