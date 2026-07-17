"""Helpers for intake section payload inspection."""
from __future__ import annotations

from typing import Any

from app.personnel_intake.domain.review_status import (
    INTAKE_REVIEW_SECTIONS,
    INTAKE_SECTION_CONTACTS,
    INTAKE_SECTION_EDUCATION,
    INTAKE_SECTION_EMPLOYMENT_BIOGRAPHY,
    INTAKE_SECTION_MILITARY,
    INTAKE_SECTION_PERSONAL,
    INTAKE_SECTION_RELATIVES,
    INTAKE_SECTION_TRAINING,
)


def _has_text(value: Any) -> bool:
    return bool(str(value or "").strip())


def is_intake_section_empty(section_code: str, payload: dict[str, Any]) -> bool:
    if section_code == INTAKE_SECTION_PERSONAL:
        block = payload.get("personal") or {}
        return not any(_has_text(block.get(k)) for k in block)
    if section_code == INTAKE_SECTION_CONTACTS:
        block = payload.get("contacts") or {}
        return not any(_has_text(block.get(k)) for k in block)
    if section_code == INTAKE_SECTION_EDUCATION:
        items = payload.get("education") or []
        return not isinstance(items, list) or len(items) == 0
    if section_code == INTAKE_SECTION_TRAINING:
        items = payload.get("training") or []
        return not isinstance(items, list) or len(items) == 0
    if section_code == INTAKE_SECTION_RELATIVES:
        items = payload.get("relatives") or []
        return not isinstance(items, list) or len(items) == 0
    if section_code == INTAKE_SECTION_EMPLOYMENT_BIOGRAPHY:
        items = payload.get("employment_biography") or []
        return not isinstance(items, list) or len(items) == 0
    if section_code == INTAKE_SECTION_MILITARY:
        block = payload.get("military") or {}
        return not any(_has_text(block.get(k)) for k in block)
    return True


def extract_section_payload(section_code: str, payload: dict[str, Any]) -> Any:
    if section_code == INTAKE_SECTION_PERSONAL:
        return payload.get("personal") or {}
    if section_code == INTAKE_SECTION_CONTACTS:
        return payload.get("contacts") or {}
    if section_code == INTAKE_SECTION_MILITARY:
        return payload.get("military") or {}
    return payload.get(section_code) or []


def all_review_sections_present(section_codes: list[str]) -> bool:
    return set(section_codes) == set(INTAKE_REVIEW_SECTIONS)
