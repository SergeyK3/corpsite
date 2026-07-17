"""Comparison keys for Person matching (WP-CL-005)."""
from __future__ import annotations

from typing import Optional

from app.control_list_import.normalization.strings import normalize_comparison_key


def person_fio_comparison_key(full_name: str) -> Optional[str]:
    """Normalize canonical Person full_name for comparison with Person Candidate keys."""
    return normalize_comparison_key(full_name)
