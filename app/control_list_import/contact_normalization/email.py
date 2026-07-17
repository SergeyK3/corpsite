"""Email normalization (WP-CL-007)."""
from __future__ import annotations

import re
from typing import Any

from app.control_list_import.domain.contact_candidate import NormalizedEmail
from app.control_list_import.normalization.strings import normalize_plain_string, to_raw_text

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def normalize_contact_email(value: Any) -> NormalizedEmail:
    raw = to_raw_text(value)
    if not raw:
        return NormalizedEmail(raw=None)

    text, issues = normalize_plain_string(value)
    if not text:
        return NormalizedEmail(raw=raw or None)

    candidate = text.lower().replace(" ", "")
    if not _EMAIL_RE.match(candidate):
        return NormalizedEmail(raw=raw, issues=("contact_email_unrecognized_format",))

    return NormalizedEmail(raw=raw, address=candidate, issues=issues)
