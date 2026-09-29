"""Controlled termination-reason values shared by editorial and template rendering."""
from __future__ import annotations

EMPLOYEE_INITIATIVE = "EMPLOYEE_INITIATIVE"

_LABELS = {
    EMPLOYEE_INITIATIVE: {
        "ru": "по инициативе работника",
        "kk": "жұмыскердің бастамасы бойынша",
    },
}


def termination_reason_text(value: object, locale: str) -> str:
    """Resolve a controlled code, retaining legacy free text for existing records."""
    raw = str(value or "").strip()
    return _LABELS.get(raw, {}).get(locale, raw)
