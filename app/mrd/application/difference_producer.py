"""Difference Producer application contract (ADR-058)."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from app.mrd.domain.difference_models import CreateDifferenceCommand, DetectedDifferenceRecord
from app.mrd.domain.errors import DifferenceOriginError
from app.mrd.domain.invariants import (
    validate_difference_origin_required,
    validate_origin_context,
)
from app.mrd.domain.logical_key import build_logical_key
from app.mrd.domain.types import DIFFERENCE_LIFECYCLE_DETECTED, ORIGIN_IMPORT_COMPARE
from app.mrd.infrastructure.repository import SqlAlchemyMrdRepository


class DifferenceProducer:
    """Creates Detected Differences without mutating MRD state."""

    def __init__(self, repo: SqlAlchemyMrdRepository) -> None:
        self._repo = repo

    def create_difference(
        self,
        *,
        report_period: date,
        mrd_id: int,
        entity_scope: str,
        attribute: str,
        business_type: str,
        difference_origin_code: str,
        origin_context: Mapping[str, Any],
        old_value: Any = None,
        new_value: Any = None,
        record_kind: str | None = None,
        technical_diff_class: str | None = None,
        supersedes_difference_id: int | None = None,
        last_comparison_run_id: int | None = None,
        logical_key: str | None = None,
    ) -> DetectedDifferenceRecord:
        validate_difference_origin_required(difference_origin_code)
        validate_origin_context(origin_context)
        if not self._repo.origin_is_active(difference_origin_code):
            raise DifferenceOriginError(
                f"difference_origin_code {difference_origin_code!r} is missing or inactive"
            )

        command = CreateDifferenceCommand(
            report_period=report_period,
            mrd_id=mrd_id,
            logical_key=logical_key
            or build_logical_key(
                report_period=report_period,
                mrd_id=mrd_id,
                entity_scope=entity_scope,
                attribute=attribute,
                record_kind=record_kind,
            ),
            entity_scope=entity_scope,
            attribute=attribute,
            business_type=business_type,
            difference_origin_code=difference_origin_code,
            origin_context=dict(origin_context),
            old_value=old_value,
            new_value=new_value,
            record_kind=record_kind,
            technical_diff_class=technical_diff_class,
            supersedes_difference_id=supersedes_difference_id,
            last_comparison_run_id=last_comparison_run_id,
        )
        inserted = self._repo.insert_difference(command)
        assert inserted.lifecycle_status == DIFFERENCE_LIFECYCLE_DETECTED
        return inserted

    def create_import_compare_difference(
        self,
        *,
        report_period: date,
        mrd_id: int,
        entity_scope: str,
        attribute: str,
        business_type: str,
        origin_context: Mapping[str, Any],
        old_value: Any = None,
        new_value: Any = None,
        record_kind: str | None = None,
        technical_diff_class: str | None = None,
        supersedes_difference_id: int | None = None,
        last_comparison_run_id: int | None = None,
        logical_key: str | None = None,
    ) -> DetectedDifferenceRecord:
        merged_context = {"producer": "IMPORT_COMPARE", **dict(origin_context)}
        return self.create_difference(
            report_period=report_period,
            mrd_id=mrd_id,
            entity_scope=entity_scope,
            attribute=attribute,
            business_type=business_type,
            difference_origin_code=ORIGIN_IMPORT_COMPARE,
            origin_context=merged_context,
            old_value=old_value,
            new_value=new_value,
            record_kind=record_kind,
            technical_diff_class=technical_diff_class,
            supersedes_difference_id=supersedes_difference_id,
            last_comparison_run_id=last_comparison_run_id,
            logical_key=logical_key,
        )
