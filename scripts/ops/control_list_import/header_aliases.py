"""Known header aliases for Control List semantic fields (recommendations only)."""
from __future__ import annotations

import re
from typing import Optional

# Semantic field ids align with ADR-057 / WP-CL-003 mapping profile vocabulary.
HEADER_ALIASES: dict[str, list[str]] = {
    "person.full_name": [
        "фио",
        "ф.и.о.",
        "ф. и. о.",
        "фамилия имя отчество",
        "фамилия, имя, отчество",
        "фамилия имя отчество (полностью)",
        "сотрудник",
        "работник",
    ],
    "person.birth_date": [
        "дата рождения",
        "год рождения",
        "д.р.",
        "д. р.",
        "др",
        "д р",
        "рожд",
    ],
    "person.iin": [
        "иин",
        "иин/бин",
        "иин бин",
        "иин (бин)",
        "бин/иин",
    ],
    "person.sex": [
        "пол",
    ],
    "person.nationality_raw": [
        "национальность",
        "гражданство",
    ],
    "person.phone": [
        "телефон",
        "контактный телефон",
        "мобильный телефон",
        "тел",
        "тел.",
    ],
    "employment.department_name": [
        "подразделение",
        "структурное подразделение",
        "отделение",
        "отдел",
        "участок",
        "служба",
    ],
    "employment.position_title": [
        "должность",
        "занимаемая должность",
        "занимаемая должность, дата назнач.",
        "занимаемая должность дата назнач",
        "должность (специальность)",
    ],
    "employment.started_at": [
        "дата назначения",
        "дата назнач",
        "назначен",
        "принят",
        "дата приема",
        "дата приёма",
    ],
    "education.records": [
        "образование",
        "вуз, год окончания",
        "вуз год окончания",
        "учебное заведение",
        "сведения об образовании",
    ],
    "training.records": [
        "повышение квалификации",
        "повышения квалификации",
        "пк",
        "обучение",
        "курсы",
        "повышение квалиф",
    ],
    "qualification.category": [
        "квалификационная категория",
        "категория",
        "категория должности",
        "квалификация",
    ],
    "qualification.degree": [
        "ученая степень",
        "степень",
        "уч степень",
    ],
    "person.awards": [
        "награды",
        "поощрения",
        "награждения",
    ],
    "person.notes": [
        "примечание",
        "примечания",
        "комментарий",
        "заметки",
    ],
}

def _normalize_alias_key(value: str) -> str:
    text = value.strip().lower().replace("ё", "е")
    text = re.sub(r"[.,;:]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# Flat lookup: normalized alias -> semantic field
_ALIAS_LOOKUP: dict[str, str] = {}
for _field, _aliases in HEADER_ALIASES.items():
    for _alias in _aliases:
        _ALIAS_LOOKUP[_normalize_alias_key(_alias)] = _field


def normalize_header(value: object) -> str:
    """Normalize a header cell for alias matching."""
    if value is None:
        return ""
    text = str(value).replace("\u00a0", " ").strip().lstrip("\ufeff")
    text = text.replace("\n", " ").replace("\r", " ")
    return _normalize_alias_key(text)


def match_semantic_field(header: object) -> tuple[Optional[str], Optional[str], float]:
    """Return (semantic_field, matched_alias, confidence)."""
    normalized = normalize_header(header)
    if not normalized:
        return None, None, 0.0

    if normalized in _ALIAS_LOOKUP:
        field = _ALIAS_LOOKUP[normalized]
        return field, normalized, 1.0

    best_field: Optional[str] = None
    best_alias: Optional[str] = None
    best_len = 0
    for alias, field in _ALIAS_LOOKUP.items():
        if alias in normalized or normalized in alias:
            if len(alias) > best_len:
                best_field = field
                best_alias = alias
                best_len = len(alias)

    if best_field:
        confidence = min(0.95, 0.55 + best_len / max(len(normalized), 1) * 0.35)
        return best_field, best_alias, round(confidence, 3)

    return None, None, 0.0


def header_alias_tokens() -> frozenset[str]:
    return frozenset(_ALIAS_LOOKUP.keys())
