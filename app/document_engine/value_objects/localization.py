"""Localization value objects (UDE-003)."""
from __future__ import annotations

from enum import Enum


class LocaleCode(str, Enum):
    """Supported locale tags for bilingual documents."""

    RU = "ru"
    KK = "kk"


class StalenessState(str, Enum):
    """Derived staleness reason for a locale representation."""

    CURRENT = "CURRENT"
    STALE_SEMANTIC_CHANGE = "STALE_SEMANTIC_CHANGE"
    STALE_RU_CHANGE_AFTER_KK = "STALE_RU_CHANGE_AFTER_KK"
    STALE_FINGERPRINT_MISMATCH = "STALE_FINGERPRINT_MISMATCH"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
