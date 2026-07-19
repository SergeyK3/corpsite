"""Reconcile Detected Differences against comparison candidates."""
from __future__ import annotations

from collections import Counter

from app.mrd.application.difference_producer import DifferenceProducer
from app.mrd.domain.comparison_models import ComparisonCandidate
from app.mrd.domain.difference_models import DetectedDifferenceRecord
from app.mrd.domain.reconcile import ReconcileActionKind, plan_reconcile
from app.mrd.domain.types import ORIGIN_IMPORT_COMPARE
from app.mrd.infrastructure.repository import SqlAlchemyMrdRepository


class DifferenceReconcileService:
    """Materializes reconcile plan into hr_detected_differences."""

    def __init__(self, repo: SqlAlchemyMrdRepository, producer: DifferenceProducer) -> None:
        self._repo = repo
        self._producer = producer

    def reconcile_import_compare(
        self,
        *,
        mrd_id: int,
        comparison_run_id: int,
        candidates: list[ComparisonCandidate],
    ) -> dict[str, int]:
        existing = self._repo.list_differences_for_mrd(mrd_id)
        actions = plan_reconcile(candidates=candidates, existing=existing)
        stats: Counter[str] = Counter()

        for action in actions:
            if action.kind == ReconcileActionKind.SKIP_TERMINAL:
                stats["skipped_terminal"] += 1
                continue
            if action.kind == ReconcileActionKind.KEEP_DETECTED:
                assert action.existing_difference_id is not None
                self._repo.touch_comparison_run(
                    action.existing_difference_id,
                    comparison_run_id=comparison_run_id,
                )
                stats["kept_detected"] += 1
                continue
            if action.kind == ReconcileActionKind.SUPERSEDE_ORPHAN:
                assert action.existing_difference_id is not None
                existing_row = self._require_difference(action.existing_difference_id)
                self._repo.mark_superseded(
                    action.existing_difference_id,
                    expected_row_version=existing_row.row_version,
                )
                stats["superseded_orphan"] += 1
                continue
            if action.kind in {
                ReconcileActionKind.CREATE_DETECTED,
                ReconcileActionKind.SUPERSEDE_AND_CREATE,
            }:
                assert action.candidate is not None
                supersedes_id: int | None = None
                if action.kind == ReconcileActionKind.SUPERSEDE_AND_CREATE:
                    assert action.existing_difference_id is not None
                    existing_row = self._require_difference(action.existing_difference_id)
                    self._repo.mark_superseded(
                        action.existing_difference_id,
                        expected_row_version=existing_row.row_version,
                    )
                    supersedes_id = action.existing_difference_id
                    stats["superseded_changed"] += 1
                self._create_from_candidate(
                    action.candidate,
                    comparison_run_id=comparison_run_id,
                    supersedes_difference_id=supersedes_id,
                )
                stats["created_detected"] += 1

        return dict(stats)

    def _create_from_candidate(
        self,
        candidate: ComparisonCandidate,
        *,
        comparison_run_id: int,
        supersedes_difference_id: int | None,
    ) -> DetectedDifferenceRecord:
        return self._producer.create_difference(
            report_period=candidate.report_period,
            mrd_id=candidate.mrd_id,
            entity_scope=candidate.entity_scope,
            attribute=candidate.attribute,
            business_type=candidate.business_type,
            difference_origin_code=ORIGIN_IMPORT_COMPARE,
            origin_context=candidate.origin_context,
            old_value=candidate.old_value,
            new_value=candidate.new_value,
            record_kind=candidate.record_kind,
            technical_diff_class=candidate.technical_diff_class,
            supersedes_difference_id=supersedes_difference_id,
            last_comparison_run_id=comparison_run_id,
            logical_key=candidate.logical_key,
        )

    def _require_difference(self, difference_id: int) -> DetectedDifferenceRecord:
        row = self._repo.load_difference(difference_id)
        if row is None:
            raise RuntimeError(f"difference_id={difference_id} disappeared during reconcile")
        return row
