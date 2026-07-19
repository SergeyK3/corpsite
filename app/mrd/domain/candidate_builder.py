"""Build attribute-level comparison candidates from ADR-040 item diff results."""
from __future__ import annotations

from datetime import date
from typing import Any

from app.mrd.domain.comparison_models import ComparisonCandidate
from app.mrd.domain.types import (
    DIFFERENCE_BUSINESS_NEVER_CONFIRMED,
    DIFFERENCE_BUSINESS_PERIOD_CHANGED,
    TECHNICAL_DIFF_CHANGED,
    TECHNICAL_DIFF_CONFLICT,
    TECHNICAL_DIFF_NEW,
    TECHNICAL_DIFF_REMOVED,
)
from app.services.hr_import_monthly_diff_service import (
    DIFF_STATUS_CHANGED,
    DIFF_STATUS_CONFLICT,
    DIFF_STATUS_NEW,
    DIFF_STATUS_REMOVED,
    DIFF_STATUS_UNCHANGED,
)

RECORD_PRESENCE_ATTRIBUTE = "__record__"
CONFLICT_ATTRIBUTE = "__conflict__"


def build_candidates_for_item(
    *,
    report_period: date,
    mrd_id: int,
    match_key: str,
    entity_scope: str,
    record_kind: str,
    diff_status: str,
    field_diffs: dict[str, dict[str, Any]],
    incoming_effective: dict[str, Any],
    canonical_payload: dict[str, Any],
    compare_fields: frozenset[str],
    batch_id: int,
    row_id: int | None = None,
    normalized_record_id: int | None = None,
) -> list[ComparisonCandidate]:
    if diff_status == DIFF_STATUS_UNCHANGED:
        return []

    origin_base: dict[str, Any] = {
        "batch_id": batch_id,
        "match_key": match_key,
    }
    if row_id is not None:
        origin_base["row_id"] = row_id
    if normalized_record_id is not None:
        origin_base["normalized_record_id"] = normalized_record_id

    if diff_status == DIFF_STATUS_CONFLICT:
        return [
            ComparisonCandidate(
                report_period=report_period,
                mrd_id=mrd_id,
                entity_scope=entity_scope,
                attribute=CONFLICT_ATTRIBUTE,
                business_type=DIFFERENCE_BUSINESS_PERIOD_CHANGED,
                technical_diff_class=TECHNICAL_DIFF_CONFLICT,
                old_value=canonical_payload or None,
                new_value=incoming_effective,
                record_kind=record_kind,
                match_key=match_key,
                origin_context={**origin_base, "reason": "conflict"},
            )
        ]

    if diff_status == DIFF_STATUS_REMOVED:
        return [
            ComparisonCandidate(
                report_period=report_period,
                mrd_id=mrd_id,
                entity_scope=entity_scope,
                attribute=RECORD_PRESENCE_ATTRIBUTE,
                business_type=DIFFERENCE_BUSINESS_PERIOD_CHANGED,
                technical_diff_class=TECHNICAL_DIFF_REMOVED,
                old_value=canonical_payload,
                new_value=None,
                record_kind=record_kind,
                match_key=match_key,
                origin_context=origin_base,
            )
        ]

    if diff_status == DIFF_STATUS_NEW:
        candidates: list[ComparisonCandidate] = []
        for field in sorted(compare_fields):
            value = incoming_effective.get(field)
            if value is None or value == "":
                continue
            candidates.append(
                ComparisonCandidate(
                    report_period=report_period,
                    mrd_id=mrd_id,
                    entity_scope=entity_scope,
                    attribute=field,
                    business_type=DIFFERENCE_BUSINESS_NEVER_CONFIRMED,
                    technical_diff_class=TECHNICAL_DIFF_NEW,
                    old_value=None,
                    new_value=value,
                    record_kind=record_kind,
                    match_key=match_key,
                    origin_context=origin_base,
                )
            )
        return candidates

    if diff_status == DIFF_STATUS_CHANGED:
        return [
            ComparisonCandidate(
                report_period=report_period,
                mrd_id=mrd_id,
                entity_scope=entity_scope,
                attribute=field,
                business_type=DIFFERENCE_BUSINESS_PERIOD_CHANGED,
                technical_diff_class=TECHNICAL_DIFF_CHANGED,
                old_value=diff.get("canonical"),
                new_value=diff.get("incoming"),
                record_kind=record_kind,
                match_key=match_key,
                origin_context=origin_base,
            )
            for field, diff in sorted(field_diffs.items())
        ]

    return []
