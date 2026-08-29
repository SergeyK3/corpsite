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
RANK_ADMIN_DEPUTY = 1
RANK_ADMIN_SENIOR_SPECIALIST = 2
RANK_ADMIN_SPECIALIST = 3
RANK_ADMIN_CLERICAL = 4
RANK_ADMIN_TECHNICAL = 5
RANK_ADMIN_SERVICE = 6
RANK_ADMIN_OTHER = 7

_ADMIN_DEPUTY_STEMS = ("заместител", "зам")
_ADMIN_LEADER_STEMS = ("руководител", "начальник", "заведующ", "директор")
_ADMIN_SENIOR_STEMS = ("главн", "ведущ", "старш")
_ADMIN_SPECIALIST_STEMS = (
    "менеджер",
    "бухгалтер",
    "экономист",
    "юрист",
    "юрисконсульт",
    "специалист",
    "инспектор",
    "инженер",
    "программист",
    "администратор",
    "переводчик",
    "психолог",
    "аналитик",
    "эксперт",
)
_ADMIN_CLERICAL_STEMS = ("архивариус", "делопроизводител", "секретар", "оператор")
_ADMIN_TECHNICAL_STEMS = (
    "техник",
    "водител",
    "электрик",
    "сантехник",
    "слесар",
    "кладовщик",
    "рабоч",
    "машинист",
)
_ADMIN_SERVICE_STEMS = (
    "уборщ",
    "дворник",
    "гардеробщ",
    "сторож",
    "вахтер",
    "санитар",
)


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


def _has_stem(position_name: str, stems: tuple[str, ...]) -> bool:
    alternatives = "|".join(re.escape(stem) for stem in stems)
    return bool(re.search(rf"\b(?:{alternatives})\w*\b", position_name))


def _administrative_position_rank(position_name: str, category: str) -> int:
    # Compound deputy names must precede the general structured leaders category.
    if _has_stem(position_name, _ADMIN_DEPUTY_STEMS):
        return RANK_ADMIN_DEPUTY
    if (
        _has_stem(position_name, ("главн",))
        and _has_stem(position_name, ("бухгалтер",))
    ):
        return RANK_ADMIN_LEADER
    if category == LEADER_POSITION_CATEGORY or _has_stem(
        position_name, _ADMIN_LEADER_STEMS
    ):
        return RANK_ADMIN_LEADER
    if _has_stem(position_name, _ADMIN_SENIOR_STEMS) and _has_stem(
        position_name, _ADMIN_SPECIALIST_STEMS
    ):
        return RANK_ADMIN_SENIOR_SPECIALIST
    if _has_stem(position_name, _ADMIN_SPECIALIST_STEMS):
        return RANK_ADMIN_SPECIALIST
    if _has_stem(position_name, _ADMIN_CLERICAL_STEMS):
        return RANK_ADMIN_CLERICAL
    if _has_stem(position_name, _ADMIN_TECHNICAL_STEMS):
        return RANK_ADMIN_TECHNICAL
    if _has_stem(position_name, _ADMIN_SERVICE_STEMS):
        return RANK_ADMIN_SERVICE
    return RANK_ADMIN_OTHER


def personnel_position_rank(
    *,
    group_id: int,
    position_name: str | None,
    position_category: str | None,
    has_current_assignment: bool = True,
) -> int:
    """Return the canonical position rank; lower values are shown first."""
    normalized = normalize_position_name(position_name)
    category = str(position_category or "").strip().casefold()

    if group_id in MEDICAL_GROUP_IDS and not has_current_assignment:
        return RANK_OTHER

    # ``position_name`` is the effective position displayed by the caller.  A
    # legacy projection remains rankable when no current assignment exists;
    # only a genuinely empty displayed position uses the fallback rank.
    if not normalized:
        return RANK_ADMIN_OTHER if group_id == ADMINISTRATIVE_GROUP_ID else RANK_OTHER

    if group_id == ADMINISTRATIVE_GROUP_ID:
        return _administrative_position_rank(normalized, category)
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


def _sql_stem_pattern(stems: tuple[str, ...]) -> str:
    alternatives = "|".join(stems)
    return f"(^| )({alternatives})[[:alnum:]_]*($| )"


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
    admin_deputy = _sql_stem_pattern(_ADMIN_DEPUTY_STEMS)
    admin_leader = _sql_stem_pattern(_ADMIN_LEADER_STEMS)
    admin_senior = _sql_stem_pattern(_ADMIN_SENIOR_STEMS)
    admin_specialist = _sql_stem_pattern(_ADMIN_SPECIALIST_STEMS)
    admin_clerical = _sql_stem_pattern(_ADMIN_CLERICAL_STEMS)
    admin_technical = _sql_stem_pattern(_ADMIN_TECHNICAL_STEMS)
    admin_service = _sql_stem_pattern(_ADMIN_SERVICE_STEMS)
    clauses: list[str] = ["CASE"]
    if has_current_assignment_expr:
        clauses.append(
            f"WHEN {group_id_expr} IN ({CLINICAL_GROUP_ID}, {PARACLINICAL_GROUP_ID}) "
            f"AND NOT ({has_current_assignment_expr}) THEN {RANK_OTHER}"
        )
    clauses.extend(
        [
            f"WHEN {group_id_expr} = {ADMINISTRATIVE_GROUP_ID} THEN CASE",
            f"    WHEN {normalized} ~ '{admin_deputy}' THEN {RANK_ADMIN_DEPUTY}",
            f"    WHEN ({normalized} ~ '{_sql_stem_pattern(('главн',))}' "
            f"AND {normalized} ~ '{_sql_stem_pattern(('бухгалтер',))}') "
            f"THEN {RANK_ADMIN_LEADER}",
            f"    WHEN {category} = '{LEADER_POSITION_CATEGORY}' "
            f"OR {normalized} ~ '{admin_leader}' THEN {RANK_ADMIN_LEADER}",
            f"    WHEN {normalized} ~ '{admin_senior}' "
            f"AND {normalized} ~ '{admin_specialist}' THEN {RANK_ADMIN_SENIOR_SPECIALIST}",
            f"    WHEN {normalized} ~ '{admin_specialist}' THEN {RANK_ADMIN_SPECIALIST}",
            f"    WHEN {normalized} ~ '{admin_clerical}' THEN {RANK_ADMIN_CLERICAL}",
            f"    WHEN {normalized} ~ '{admin_technical}' THEN {RANK_ADMIN_TECHNICAL}",
            f"    WHEN {normalized} ~ '{admin_service}' THEN {RANK_ADMIN_SERVICE}",
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
