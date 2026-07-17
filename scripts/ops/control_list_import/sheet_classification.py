"""Sheet name classification — personnel category and employment mode (recommendations only)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

PersonnelCategory = str  # doctor | nursing_staff | junior_medical_staff | other_staff | unknown
EmploymentMode = str  # primary | concurrent | unknown
SheetPurpose = str  # personnel_control_list | declaration | unknown

CONCURRENT_EXACT_TOKENS = frozenset(
    {
        "совместитель",
        "совместители",
        "совместительство",
        "совмест",
        "совм",
    }
)

CATEGORY_TOKEN_MAP: dict[str, set[str]] = {
    "doctor": {"врач", "врачи"},
    "nursing_staff": {"медсестра", "медсестры", "смр"},
    "junior_medical_staff": {"санитарка", "санитарки", "ммп"},
    "other_staff": {"прочее", "прочие"},
}

CATEGORY_PHRASE_MAP: dict[str, tuple[str, ...]] = {
    "nursing_staff": ("средний медицинский персонал",),
    "junior_medical_staff": ("младший медицинский персонал",),
    "other_staff": ("иной персонал",),
}


@dataclass(frozen=True)
class SheetClassification:
    proposed_personnel_category: PersonnelCategory
    proposed_employment_mode: EmploymentMode
    proposed_sheet_purpose: SheetPurpose
    classification_confidence: float
    matched_classification_rules: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "proposed_personnel_category": self.proposed_personnel_category,
            "proposed_employment_mode": self.proposed_employment_mode,
            "proposed_sheet_purpose": self.proposed_sheet_purpose,
            "classification_confidence": self.classification_confidence,
            "matched_classification_rules": list(self.matched_classification_rules),
        }


def normalize_sheet_name(name: str) -> str:
    text = str(name or "").strip().lower().replace("ё", "е")
    return re.sub(r"\s+", " ", text)


def tokenize_sheet_name(name: str) -> list[str]:
    norm = normalize_sheet_name(name)
    tokens = re.findall(r"[a-zа-я0-9]+", norm, flags=re.IGNORECASE)
    return tokens


def is_concurrent_sheet_name(name: str) -> tuple[bool, list[str]]:
    """Token-aware concurrent detection; avoids bare substring hits inside unrelated words."""
    norm = normalize_sheet_name(name)
    tokens = tokenize_sheet_name(name)
    matched: list[str] = []

    for token in tokens:
        if token in CONCURRENT_EXACT_TOKENS:
            matched.append("employment_concurrent_token")
            return True, matched

    concurrent_phrases = (
        r"\bсовместител(?:ь|и|ей|ем|я|ю|и)\b",
        r"\bсовместительство\b",
        r"\bсовмест\b",
        r"\bсовм\.?\b",
    )
    for pattern in concurrent_phrases:
        if re.search(pattern, norm):
            matched.append("employment_concurrent_phrase")
            return True, matched

    return False, matched


def _detect_personnel_category(name: str) -> tuple[PersonnelCategory, float, list[str]]:
    norm = normalize_sheet_name(name)
    tokens = set(tokenize_sheet_name(name))
    matched_rules: list[str] = []
    hits: list[tuple[str, float]] = []

    for category, category_tokens in CATEGORY_TOKEN_MAP.items():
        if tokens & category_tokens:
            matched_rules.append(f"category_{category}")
            hits.append((category, 0.95))

    for category, phrases in CATEGORY_PHRASE_MAP.items():
        for phrase in phrases:
            if phrase in norm:
                matched_rules.append(f"category_{category}")
                hits.append((category, 0.9))

    if not hits:
        return "unknown", 0.0, matched_rules

    if len({h[0] for h in hits}) > 1:
        return "unknown", 0.35, matched_rules

    category, confidence = hits[0]
    return category, confidence, matched_rules


def classify_sheet_name(
    sheet_name: str,
    *,
    is_declaration_excluded: bool = False,
) -> SheetClassification:
    """Recommend sheet classification from source sheet name (profile-driven, not Person attribute)."""
    matched_rules: list[str] = []

    if is_declaration_excluded:
        matched_rules.append("purpose_declaration")
        category, cat_conf, cat_rules = _detect_personnel_category(sheet_name)
        matched_rules.extend(cat_rules)
        return SheetClassification(
            proposed_personnel_category=category,
            proposed_employment_mode="unknown",
            proposed_sheet_purpose="declaration",
            classification_confidence=round(max(cat_conf, 0.85), 3),
            matched_classification_rules=tuple(matched_rules),
        )

    category, cat_conf, cat_rules = _detect_personnel_category(sheet_name)
    matched_rules.extend(cat_rules)

    is_concurrent, concurrent_rules = is_concurrent_sheet_name(sheet_name)
    matched_rules.extend(concurrent_rules)

    if category != "unknown":
        purpose: SheetPurpose = "personnel_control_list"
        matched_rules.append("purpose_personnel_control_list")
        if is_concurrent:
            employment: EmploymentMode = "concurrent"
            matched_rules.append("employment_concurrent")
            confidence = min(1.0, cat_conf + 0.05)
        else:
            employment = "primary"
            matched_rules.append("employment_primary_control_list")
            confidence = cat_conf
    else:
        purpose = "unknown"
        employment = "unknown"
        confidence = 0.0
        if is_concurrent:
            employment = "concurrent"
            matched_rules.append("employment_concurrent")
            confidence = 0.4

    return SheetClassification(
        proposed_personnel_category=category,
        proposed_employment_mode=employment,
        proposed_sheet_purpose=purpose,
        classification_confidence=round(confidence, 3),
        matched_classification_rules=tuple(dict.fromkeys(matched_rules)),
    )
