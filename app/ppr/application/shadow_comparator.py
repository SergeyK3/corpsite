"""Deterministic shadow comparison for PPR read-switch (R7)."""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.ppr.read.models import PprCompositeReadModel

logger = logging.getLogger("app.ppr.read_switch")

SHADOW_RESULT_MATCH = "match"
SHADOW_RESULT_MISMATCH = "mismatch"
SHADOW_RESULT_PPR_ERROR = "ppr_error"


@dataclass(frozen=True, slots=True)
class ShadowComparisonResult:
    result: str
    mismatch_fields: tuple[str, ...]
    resolved_person_id: int | None
    education_active_count: int | None
    training_active_count: int | None
    materialized: bool | None


def _normalize_name(value: str | None) -> str:
    return " ".join(str(value or "").split()).casefold()


def _iin_fingerprint(value: str | None) -> str:
    if not value:
        return "absent"
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if not digits:
        return "absent"
    return f"present:{len(digits)}"


def _education_fingerprint(records: tuple[Any, ...]) -> str:
    parts: list[str] = []
    for record in records:
        institution = getattr(record, "institution_name", None) or ""
        specialty = getattr(record, "specialty", None) or ""
        parts.append(f"{institution}|{specialty}".casefold())
    return hashlib.sha256("|".join(sorted(parts)).encode()).hexdigest()[:16]


def _legacy_education_count(legacy: dict[str, Any]) -> int:
    profile = legacy.get("profile") or {}
    education = profile.get("education")
    if isinstance(education, list):
        return len(education)
    return 0


def _legacy_training_count(legacy: dict[str, Any]) -> int:
    profile = legacy.get("profile") or {}
    training = profile.get("training")
    if isinstance(training, list):
        return len(training)
    return 0


def _legacy_birth_date(legacy: dict[str, Any]) -> date | None:
    profile = legacy.get("profile") or {}
    basic = profile.get("basic") or {}
    raw = basic.get("birth_date")
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            return None
    return None


def compare_legacy_import_card_to_ppr(
    legacy: dict[str, Any],
    ppr: PprCompositeReadModel,
) -> ShadowComparisonResult:
    """Compare normalized business fields — no sensitive payload logging."""
    mismatches: list[str] = []

    legacy_name = _normalize_name(legacy.get("full_name"))
    ppr_name = _normalize_name(ppr.general.full_name)
    if legacy_name != ppr_name:
        mismatches.append("full_name")

    legacy_iin = _iin_fingerprint((legacy.get("profile") or {}).get("basic", {}).get("iin"))
    ppr_iin = _iin_fingerprint(ppr.general.iin)
    if legacy_iin != ppr_iin:
        mismatches.append("iin_presence")

    legacy_birth = _legacy_birth_date(legacy)
    if legacy_birth != ppr.general.birth_date:
        mismatches.append("birth_date")

    legacy_edu_count = _legacy_education_count(legacy)
    ppr_edu_count = len(ppr.education.active)
    if legacy_edu_count != ppr_edu_count:
        mismatches.append("education_active_count")

    legacy_train_count = _legacy_training_count(legacy)
    ppr_train_count = len(ppr.training.active)
    if legacy_train_count != ppr_train_count:
        mismatches.append("training_active_count")

    result = SHADOW_RESULT_MATCH if not mismatches else SHADOW_RESULT_MISMATCH
    return ShadowComparisonResult(
        result=result,
        mismatch_fields=tuple(mismatches),
        resolved_person_id=ppr.person_id,
        education_active_count=ppr_edu_count,
        training_active_count=ppr_train_count,
        materialized=ppr.materialized,
    )


def log_shadow_comparison(
    *,
    employee_id: int,
    comparison: ShadowComparisonResult,
    read_mode: str,
    correlation_id: str | None = None,
) -> None:
    logger.info(
        "ppr_shadow_compare employee_id=%s person_id=%s result=%s mismatches=%s "
        "education_active=%s training_active=%s materialized=%s read_mode=%s correlation_id=%s",
        employee_id,
        comparison.resolved_person_id,
        comparison.result,
        ",".join(comparison.mismatch_fields) if comparison.mismatch_fields else "-",
        comparison.education_active_count,
        comparison.training_active_count,
        comparison.materialized,
        read_mode,
        correlation_id or "-",
    )
