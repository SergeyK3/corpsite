"""Automatic IMPORT_COMPARE orchestration for MRD."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.mrd.application.active_mrd_service import require_active_mrd_for_period, resolve_active_mrd

__all__ = ["AutomaticComparisonError", "require_active_mrd_for_period", "resolve_active_mrd", "run_automatic_import_comparison"]
from app.mrd.application.comparison_engine import ImportMrdComparisonEngine
from app.mrd.application.difference_producer import DifferenceProducer
from app.mrd.application.reconcile_service import DifferenceReconcileService
from app.mrd.domain.difference_models import ComparisonRunResult
from app.mrd.domain.errors import MrdNotFoundError
from app.mrd.infrastructure.repository import SqlAlchemyMrdRepository, mrd_tables_available
from app.services.hr_import_analytics_service import _ensure_batch_exists


class AutomaticComparisonError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def run_automatic_import_comparison(
    conn: Connection,
    batch_id: int,
    *,
    started_by: int | None = None,
) -> ComparisonRunResult:
    """Run IMPORT_COMPARE: candidates → comparison_run → reconcile. Does not mutate MRD entries."""
    if not mrd_tables_available(conn):
        raise AutomaticComparisonError("MRD schema is not available")

    _ensure_batch_exists(conn, batch_id)
    from app.services.hr_baseline_service import _resolve_batch_report_period

    report_period = _resolve_batch_report_period(conn, batch_id)
    repo = SqlAlchemyMrdRepository(conn)
    active_mrd = resolve_active_mrd(conn, report_period)
    if active_mrd is None:
        raise MrdNotFoundError(f"No ACTIVE MRD for report_period={report_period.isoformat()}")

    engine = ImportMrdComparisonEngine(conn)
    candidates = engine.build_candidates(
        batch_id=batch_id,
        mrd_id=active_mrd.mrd_id,
        report_period=report_period,
    )

    producer = DifferenceProducer(repo)
    reconcile = DifferenceReconcileService(repo, producer)
    reconcile_stats = {"candidate_count": len(candidates)}

    comparison_run_id = repo.insert_comparison_run(
        batch_id=batch_id,
        mrd_id=active_mrd.mrd_id,
        report_period=report_period,
        started_by=started_by,
        stats=reconcile_stats,
    )
    reconcile_stats.update(
        reconcile.reconcile_import_compare(
            mrd_id=active_mrd.mrd_id,
            comparison_run_id=comparison_run_id,
            candidates=candidates,
        )
    )

    from app.services.hr_import_review_exception_service import run_post_difference_review_completion

    actor = int(started_by) if started_by is not None else None
    if actor is None:
        row = conn.execute(
            text("SELECT imported_by FROM public.hr_import_batches WHERE batch_id = :batch_id"),
            {"batch_id": batch_id},
        ).scalar_one_or_none()
        actor = int(row) if row is not None else None
    if actor is not None:
        run_post_difference_review_completion(
            conn,
            batch_id=int(batch_id),
            actor_user_id=actor,
        )

    return ComparisonRunResult(
        comparison_run_id=comparison_run_id,
        batch_id=batch_id,
        mrd_id=active_mrd.mrd_id,
        report_period=report_period,
        stats=reconcile_stats,
    )
