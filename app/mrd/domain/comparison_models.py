"""Comparison candidate models for MRD automatic comparison."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.mrd.domain.logical_key import build_logical_key, candidate_signature


@dataclass(frozen=True, slots=True)
class ComparisonCandidate:
    """Attribute-level diff candidate produced by comparison engine."""

    report_period: date
    mrd_id: int
    entity_scope: str
    attribute: str
    business_type: str
    technical_diff_class: str
    old_value: Any
    new_value: Any
    record_kind: str | None = None
    match_key: str | None = None
    origin_context: dict[str, Any] = field(default_factory=dict)

    @property
    def logical_key(self) -> str:
        return build_logical_key(
            report_period=self.report_period,
            mrd_id=self.mrd_id,
            entity_scope=self.entity_scope,
            attribute=self.attribute,
            record_kind=self.record_kind,
        )

    @property
    def signature(self) -> str:
        return candidate_signature(old_value=self.old_value, new_value=self.new_value)
