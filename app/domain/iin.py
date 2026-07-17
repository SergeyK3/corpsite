"""Production IIN normalization and validation (ADR-057 D9, Phase 1)."""
from __future__ import annotations

import re

class IinValidationError(ValueError):
    """Invalid IIN input (Phase 1 — 12 digits, no checksum)."""


_IIN_DIGITS_RE = re.compile(r"\D")


def normalize_iin(raw: str | None) -> str:
    """Strip non-digits and return normalized IIN string."""
    if raw is None:
        raise IinValidationError("IIN is required.")
    normalized = _IIN_DIGITS_RE.sub("", str(raw).strip())
    if not normalized:
        raise IinValidationError("IIN is required.")
    return normalized


def validate_iin(normalized: str) -> str:
    """Validate normalized IIN is exactly 12 decimal digits (no checksum in Phase 1)."""
    if len(normalized) != 12 or not normalized.isdigit():
        raise IinValidationError("IIN must be exactly 12 digits.")
    return normalized


def normalize_and_validate_iin(raw: str | None) -> str:
    """Normalize then validate IIN — single production entry point."""
    return validate_iin(normalize_iin(raw))
