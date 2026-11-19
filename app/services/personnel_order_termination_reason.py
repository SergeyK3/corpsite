"""Controlled termination-reason values shared by editorial and template rendering."""
from __future__ import annotations
from typing import Any, Mapping

EMPLOYEE_INITIATIVE = "EMPLOYEE_INITIATIVE"
EMPLOYER_INITIATIVE = "EMPLOYER_INITIATIVE"
CONTRACT_EXPIRATION = "CONTRACT_EXPIRATION"
_MANUAL_BASIS_REASONS = frozenset({EMPLOYER_INITIATIVE, CONTRACT_EXPIRATION})

_LABELS = {
    EMPLOYEE_INITIATIVE: {
        "ru": "по инициативе работника",
        "kk": "жұмыскердің бастамасы бойынша",
    },
    EMPLOYER_INITIATIVE: {
        "ru": "по инициативе работодателя",
        "kk": "жұмыс берушінің бастамасы бойынша",
    },
    CONTRACT_EXPIRATION: {
        "ru": "В связи с истечением срока трудового договора",
        "kk": "Еңбек шарты мерзімінің аяқталуына байланысты",
    },
}


def termination_reason_text(value: object, locale: str) -> str:
    """Resolve a controlled code, retaining legacy free text for existing records."""
    raw = str(value or "").strip()
    return _LABELS.get(raw, {}).get(locale, raw)


def termination_reason_basis_text(value: object, locale: str) -> str:
    """Use a chosen reason as the visible basis when no document was supplied."""
    reason = termination_reason_text(value, locale).strip().rstrip(".")
    if not reason:
        return ""
    heading = "Негіз" if locale == "kk" else "Основание"
    return f"{heading}: {reason[0].upper()}{reason[1:]}."


def termination_basis_is_manual(reason: object) -> bool:
    """These reasons do not identify a particular supporting document."""
    return str(reason or "").strip() in _MANUAL_BASIS_REASONS


def termination_basis_is_explicit(basis: Mapping[str, Any] | None) -> bool:
    """A bare PERSONAL_APPLICATION row is the old generated default."""
    if not basis:
        return False
    kind = str(basis.get("basis_type") or "").strip().upper()
    details = any(str(basis.get(key) or "").strip() for key in ("document_date", "document_number", "free_text"))
    return details or kind not in {"", "PERSONAL_APPLICATION", "OTHER"}
