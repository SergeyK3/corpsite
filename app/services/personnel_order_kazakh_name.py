"""A conservative document order for a Kazakh personnel order name."""
from __future__ import annotations

import re
from typing import Any, Mapping


_PATRONYMIC = re.compile(r"(?:ович|евич|ич|овна|евна|ична|ұлы|қызы)$", re.I)
_SURNAME = re.compile(r"(?:ов|ев|ин|ын|ова|ева|ина|ына|ский|цкий|ская|цкая)$", re.I)


def document_name_kk(source: str, *, name: Mapping[str, Any] | None = None) -> str:
    """Return a clear given/patronymic/surname order, or the unchanged source."""
    source = str(source or "").strip()
    fields = name or {}
    first = str(fields.get("first_name") or "").strip()
    middle = str(fields.get("middle_name") or "").strip()
    last = str(fields.get("last_name") or "").strip()
    if first and last:
        return " ".join(part for part in (first, middle, last) if part)
    parts = source.split()
    if len(parts) == 3:
        if _SURNAME.search(parts[0]) and _PATRONYMIC.search(parts[2]) and not _PATRONYMIC.search(parts[1]):
            return " ".join((parts[1], parts[2], parts[0]))
        if _PATRONYMIC.search(parts[1]) and _SURNAME.search(parts[2]) and not _SURNAME.search(parts[0]):
            return source
    if len(parts) == 2:
        if _SURNAME.search(parts[0]) and not _SURNAME.search(parts[1]) and len(parts[1]) > 1 and parts[1].isalpha():
            return " ".join((parts[1], parts[0]))
    return source
