"""String normalization helpers (WP-CL-004)."""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Optional

_WHITESPACE_RE = re.compile(r"\s+")


def to_raw_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\u00a0", " ").replace("\ufeff", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.strip()


def normalize_plain_string(value: Any) -> tuple[Optional[str], tuple[str, ...]]:
    raw = to_raw_text(value)
    if not raw:
        return None, ()

    normalized = unicodedata.normalize("NFKC", raw)
    normalized = _WHITESPACE_RE.sub(" ", normalized).strip()
    if not normalized:
        return None, ()
    return normalized, ()


def normalize_comparison_key(value: Any) -> Optional[str]:
    text, _ = normalize_plain_string(value)
    if not text:
        return None
    return text.lower().replace("ё", "е")
