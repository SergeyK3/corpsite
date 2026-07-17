"""Employment mode normalization from sheet snapshot (WP-CL-006)."""
from __future__ import annotations

from app.db.models.control_list_mapping import (
    EMPLOYMENT_MODE_CONCURRENT,
    EMPLOYMENT_MODE_PRIMARY,
    EMPLOYMENT_MODE_UNKNOWN,
)


def normalize_employment_mode(value: str | None) -> tuple[str, tuple[str, ...]]:
    if value in {EMPLOYMENT_MODE_PRIMARY, EMPLOYMENT_MODE_CONCURRENT}:
        return value, ()
    if value == EMPLOYMENT_MODE_UNKNOWN:
        return EMPLOYMENT_MODE_UNKNOWN, ("employment_mode_unknown",)
    if not value:
        return EMPLOYMENT_MODE_UNKNOWN, ("employment_mode_missing",)
    return EMPLOYMENT_MODE_UNKNOWN, ("employment_mode_unrecognized",)
