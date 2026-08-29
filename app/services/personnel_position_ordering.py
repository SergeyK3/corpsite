"""Shared personnel position hierarchy for reports and operational lists."""
from __future__ import annotations

import re
from typing import Any

from app.medical_org_groups import (
    BY_SLUG,
    SLUG_ADMIN_HOUSEHOLD,
    SLUG_CLINICAL,
    SLUG_PARACLINICAL,
)


CLINICAL_GROUP_ID = BY_SLUG[SLUG_CLINICAL].group_id
PARACLINICAL_GROUP_ID = BY_SLUG[SLUG_PARACLINICAL].group_id
ADMINISTRATIVE_GROUP_ID = BY_SLUG[SLUG_ADMIN_HOUSEHOLD].group_id
MEDICAL_GROUP_IDS = frozenset({CLINICAL_GROUP_ID, PARACLINICAL_GROUP_ID})
LEADER_POSITION_CATEGORY = "leaders"

RANK_DEPARTMENT_HEAD = 0
RANK_DOCTOR = 1
RANK_SENIOR_NURSE = 2
RANK_NURSE = 3
RANK_HOUSEKEEPING_NURSE = 4
RANK_ORDERLY = 5
RANK_OTHER = 6

RANK_ADMIN_LEADER = 0
RANK_ADMIN_OTHER = 1


def normalize_position_name(value: str | None) -> str:
    """Normalize case, ё/е, hyphens, punctuation, and repeated whitespace."""
    normalized = str(value or "").casefold().replace("ё", "е")
    normalized = re.sub(r"[-‐‑‒–—−]+", " ", normalized)
    normalized = re.sub(r"[^\w\s]+", " ", normalized, flags=re.UNICODE)
    return " ".join(normalized.split())


def _is_nurse(position_name: str) -> bool:
    return bool(
        re.search(r"\bмедсестр\w*\b", position_name)
        or re.search(r"\bмедбрат\w*\b", position_name)
        or re.search(r"\bмедицинск\w*\s+(?:сестр\w*|брат\w*)\b", position_name)
    )


def personnel_position_rank(
    *,
    group_id: int,
    position_name: str | None,
    position_category: str | None,
    has_current_assignment: bool = True,
) -> int:
    """Return the canonical position rank; lower values are shown first."""
    if not has_current_assignment:
        return RANK_OTHER
    normalized = normalize_position_name(position_name)
    category = str(position_category or "").strip().casefold()

    if group_id == ADMINISTRATIVE_GROUP_ID:
        return RANK_ADMIN_LEADER if category == LEADER_POSITION_CATEGORY else RANK_ADMIN_OTHER
    if group_id not in MEDICAL_GROUP_IDS:
        return RANK_OTHER

    # Specific categories must precede the broader doctor/nurse checks.
    if category == LEADER_POSITION_CATEGORY or re.search(r"\bзаведующ\w*\b", normalized):
        return RANK_DEPARTMENT_HEAD
    if re.search(r"\bврач\w*\b", normalized):
        return RANK_DOCTOR
    if re.search(r"\bстарш\w*\b", normalized) and _is_nurse(normalized):
        return RANK_SENIOR_NURSE
    if re.search(r"\bсестр\w*\s+хозяйк\w*\b", normalized):
        return RANK_HOUSEKEEPING_NURSE
    if _is_nurse(normalized):
        return RANK_NURSE
    if re.search(r"\bсанитарк\w*\b|\bсанитар\w*\b", normalized):
        return RANK_ORDERLY
    return RANK_OTHER


def personnel_position_sort_key(
    *,
    group_id: int,
    position_name: str | None,
    position_category: str | None,
    full_name: str | None,
    employee_id: Any,
    has_current_assignment: bool = True,
) -> tuple[int, str, str, tuple[int, int | str]]:
    """Canonical Python key used by structured personnel representations."""
    displayed_name = str(full_name or "")
    return (
        personnel_position_rank(
            group_id=group_id,
            position_name=position_name,
            position_category=position_category,
            has_current_assignment=has_current_assignment,
        ),
        displayed_name.casefold(),
        displayed_name,
        _stable_employee_id(employee_id),
    )


def _stable_employee_id(employee_id: Any) -> tuple[int, int | str]:
    try:
        return (0, int(employee_id))
    except (TypeError, ValueError):
        return (1, str(employee_id))


def normalized_position_name_sql(position_name_expr: str) -> str:
    """Return PostgreSQL normalization equivalent to ``normalize_position_name``."""
    return (
        "BTRIM(REGEXP_REPLACE(REGEXP_REPLACE(REGEXP_REPLACE("
        f"REPLACE(LOWER(COALESCE(CAST({position_name_expr} AS TEXT), '')), 'ё', 'е'), "
        "'[-‐‑‒–—−]+', ' ', 'g'), "
        "'[^[:alnum:]_[:space:]]+', ' ', 'g'), "
        "'[[:space:]]+', ' ', 'g'))"
    )


def personnel_position_rank_sql(
    *,
    group_id_expr: str,
    position_name_expr: str,
    position_category_expr: str,
    has_current_assignment_expr: str | None = None,
) -> str:
    """Return the PostgreSQL CASE expression equivalent to Python ranking."""
    normalized = normalized_position_name_sql(position_name_expr)
    category = f"LOWER(BTRIM(COALESCE(CAST({position_category_expr} AS TEXT), '')))"
    nurse = (
        f"({normalized} ~ '(^| )(медсестр[[:alnum:]_]*|медбрат[[:alnum:]_]*|"
        "медицинск[[:alnum:]_]* (сестр[[:alnum:]_]*|брат[[:alnum:]_]*))($| )')"
    )
    clauses: list[str] = ["CASE"]
    if has_current_assignment_expr:
        clauses.append(f"WHEN NOT ({has_current_assignment_expr}) THEN {RANK_OTHER}")
    clauses.extend(
        [
            f"WHEN {group_id_expr} = {ADMINISTRATIVE_GROUP_ID} THEN CASE ",
            f"    WHEN {category} = '{LEADER_POSITION_CATEGORY}' THEN {RANK_ADMIN_LEADER} ",
            f"    ELSE {RANK_ADMIN_OTHER} END",
            f"WHEN {group_id_expr} IN ({CLINICAL_GROUP_ID}, {PARACLINICAL_GROUP_ID}) THEN CASE",
            f"    WHEN {category} = '{LEADER_POSITION_CATEGORY}' "
            f"OR {normalized} ~ '(^| )заведующ[[:alnum:]_]*($| )' THEN {RANK_DEPARTMENT_HEAD}",
            f"    WHEN {normalized} ~ '(^| )врач[[:alnum:]_]*($| )' THEN {RANK_DOCTOR}",
            f"    WHEN {normalized} ~ '(^| )старш[[:alnum:]_]*($| )' "
            f"AND {nurse} THEN {RANK_SENIOR_NURSE}",
            f"    WHEN {normalized} ~ '(^| )сестр[[:alnum:]_]* хозяйк[[:alnum:]_]*($| )' "
            f"THEN {RANK_HOUSEKEEPING_NURSE}",
            f"    WHEN {nurse} THEN {RANK_NURSE}",
            f"    WHEN {normalized} ~ '(^| )(санитарк[[:alnum:]_]*|санитар[[:alnum:]_]*)($| )' "
            f"THEN {RANK_ORDERLY}",
            f"    ELSE {RANK_OTHER} END",
            f"ELSE {RANK_OTHER} END",
        ]
    )
    return " ".join(clauses)
