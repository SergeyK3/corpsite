"""Narrow, approved position names used by personnel-order text generators."""
from __future__ import annotations

from typing import Any, Mapping


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _normalized_russian_position(value: str) -> str:
    """Normalize only case and ordinary dash variants for an exact dictionary key."""
    return " ".join(
        value.casefold()
        .replace("‐", "-")
        .replace("‑", "-")
        .replace("–", "-")
        .replace("—", "-")
        .split()
    ).replace(" - ", "-").replace(" -", "-").replace("- ", "-")


_RU_TO_KK = {
    "старшая медсестра": "Аға мейіргер",
    "врач (ординатор)": "дәрігері (ординатор)",
    "медсестра-анестезистка": "анестезист мейіргері",
}

# Document wording is nominative: it is a controlled display form, not a
# morphological transformation.  Keys are normalized source dictionary names.
_RU_DOCUMENT_NOMINATIVE = {
    "врач": "врач",
}


def document_nominative_personnel_order_position(value: Any) -> str:
    """Return the approved Russian document form in lower-case nominative."""
    source = localized_personnel_order_position(value, "ru")
    if source == "—":
        return ""
    normalized = _normalized_russian_position(source)
    approved = _RU_DOCUMENT_NOMINATIVE.get(normalized)
    if approved:
        return approved
    # Positions absent from the narrow override dictionary retain their source
    # spelling, with only the leading letter adjusted for sentence position.
    return source[:1].lower() + source[1:]


def localized_personnel_order_position(value: Any, locale: str) -> str:
    """Resolve a position without overwriting an explicitly saved localization."""
    lang = str(locale or "").strip().lower()
    if isinstance(value, Mapping):
        preferred = _clean(value.get(lang))
        if preferred:
            return preferred
        russian = _clean(value.get("ru"))
        if lang == "kk" and russian:
            return _RU_TO_KK.get(_normalized_russian_position(russian), russian)
        for key in ("kk", "ru", "name"):
            fallback = _clean(value.get(key))
            if fallback:
                return fallback
        return "—"
    text = _clean(value)
    if lang == "kk" and text:
        return _RU_TO_KK.get(_normalized_russian_position(text), text)
    return text or "—"
