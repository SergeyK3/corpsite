"""Intake education_type contract — maps to PPR education_kind at transfer."""
from __future__ import annotations

from typing import Any

from app.db.models.personnel_migration import (
    EDUCATION_KIND_BASIC,
    EDUCATION_KIND_INTERNSHIP,
    EDUCATION_KIND_MASTERS,
    EDUCATION_KIND_PHD,
    EDUCATION_KIND_RESIDENCY,
)

INTAKE_EDUCATION_TYPE_BASIC = "basic"
INTAKE_EDUCATION_TYPE_INTERNSHIP = "internship"
INTAKE_EDUCATION_TYPE_RESIDENCY = "residency"
INTAKE_EDUCATION_TYPE_MASTERS = "masters"
INTAKE_EDUCATION_TYPE_PHD = "phd"

INTAKE_EDUCATION_TYPES: frozenset[str] = frozenset(
    {
        INTAKE_EDUCATION_TYPE_BASIC,
        INTAKE_EDUCATION_TYPE_INTERNSHIP,
        INTAKE_EDUCATION_TYPE_RESIDENCY,
        INTAKE_EDUCATION_TYPE_MASTERS,
        INTAKE_EDUCATION_TYPE_PHD,
    }
)

_INTAKE_EDUCATION_TYPE_TO_KIND: dict[str, str] = {
    INTAKE_EDUCATION_TYPE_BASIC: EDUCATION_KIND_BASIC,
    INTAKE_EDUCATION_TYPE_INTERNSHIP: EDUCATION_KIND_INTERNSHIP,
    INTAKE_EDUCATION_TYPE_RESIDENCY: EDUCATION_KIND_RESIDENCY,
    INTAKE_EDUCATION_TYPE_MASTERS: EDUCATION_KIND_MASTERS,
    INTAKE_EDUCATION_TYPE_PHD: EDUCATION_KIND_PHD,
}


def normalize_intake_education_type(raw: Any) -> str:
    """Missing or blank intake education_type is treated as basic."""
    text = str(raw or "").strip().lower()
    if not text:
        return INTAKE_EDUCATION_TYPE_BASIC
    return text


def resolve_intake_education_kind(raw: Any) -> str:
    """Map intake education_type to canonical PPR education_kind."""
    education_type = normalize_intake_education_type(raw)
    if education_type not in INTAKE_EDUCATION_TYPES:
        raise ValueError(f"unknown education_type: {education_type!r}")
    return _INTAKE_EDUCATION_TYPE_TO_KIND[education_type]


def intake_education_duplicate_fingerprint(item: dict[str, Any]) -> tuple[str, str]:
    """Fingerprint aligned with PPR duplicate guard: (education_kind, institution)."""
    kind = resolve_intake_education_kind(item.get("education_type"))
    institution = str(item.get("institution") or "").strip()
    return (kind, institution)
