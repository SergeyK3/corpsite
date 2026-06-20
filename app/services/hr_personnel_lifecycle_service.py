"""ADR-043 Phase C3 — orchestrated monthly personnel lifecycle."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.engine import engine
from app.services.hr_effective_monthly_diff_service import (
    EffectiveMonthlyDiffError,
    ensure_effective_cache_for_snapshots,
    run_effective_monthly_diff,
)
from app.services.hr_person_assignment_sync_service import (
    PersonAssignmentSyncError,
    sync_personnel_events_tx,
)

logger = logging.getLogger(__name__)

RUN_STATUS_RUNNING = "running"
RUN_STATUS_COMPLETED = "completed"
RUN_STATUS_FAILED = "failed"
RUN_STATUS_CANCELLED = "cancelled"


class PersonnelLifecycleError(Exception):
    def __init__(self, message: str, *, stage: Optional[str] = None) -> None:
        self.message = message
        self.stage = stage
        super().__init__(message)


@dataclass
class PersonnelLifecycleReport:
    run_id: Optional[int] = None
    previous_snapshot_id: int = 0
    snapshot_id: int = 0
    dry_run: bool = True
    refresh_cache: bool = True
    enqueue: bool = False
    sync_persons: bool = False
    run_status: str = RUN_STATUS_RUNNING
    duration_ms: float = 0.0
    effective_cache: dict[str, Any] = field(default_factory=dict)
    monthly_diff: dict[str, Any] = field(default_factory=dict)
    personnel_events: dict[str, Any] = field(default_factory=dict)
    enrollment: dict[str, Any] = field(default_factory=dict)
    person_sync: dict[str, Any] = field(default_factory=dict)
    validation: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _table_exists(conn: Connection, table: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = :table
            LIMIT 1
            """
        ),
        {"table": table},
    ).first()
    return row is not None


def lifecycle_runs_available(conn: Connection) -> bool:
    return _table_exists(conn, "hr_personnel_lifecycle_runs")


def _serialize_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str, sort_keys=True)


def _resolve_actor_user_id(conn: Connection, actor_user_id: Optional[int]) -> Optional[int]:
    if actor_user_id is not None:
        return int(actor_user_id)
    row = conn.execute(
        text(
            """
            SELECT user_id
            FROM public.users
            WHERE is_active = TRUE
            ORDER BY user_id
            LIMIT 1
            """
        )
    ).mappings().first()
    return int(row["user_id"]) if row else None


def _create_lifecycle_run(
    conn: Connection,
    *,
    previous_snapshot_id: int,
    snapshot_id: int,
    dry_run: bool,
    refresh_cache: bool,
    enqueue: bool,
    sync_persons: bool,
    actor_user_id: Optional[int],
) -> Optional[int]:
    if not lifecycle_runs_available(conn):
        return None
    row = conn.execute(
        text(
            """
            INSERT INTO public.hr_personnel_lifecycle_runs (
                previous_snapshot_id,
                snapshot_id,
                status,
                actor_user_id,
                dry_run,
                refresh_cache,
                enqueue,
                sync_persons
            )
            VALUES (
                :previous_snapshot_id,
                :snapshot_id,
                :status,
                :actor_user_id,
                :dry_run,
                :refresh_cache,
                :enqueue,
                :sync_persons
            )
            RETURNING run_id
            """
        ),
        {
            "previous_snapshot_id": int(previous_snapshot_id),
            "snapshot_id": int(snapshot_id),
            "status": RUN_STATUS_RUNNING,
            "actor_user_id": actor_user_id,
            "dry_run": bool(dry_run),
            "refresh_cache": bool(refresh_cache),
            "enqueue": bool(enqueue),
            "sync_persons": bool(sync_persons),
        },
    ).mappings().one()
    return int(row["run_id"])


def _finalize_lifecycle_run(
    conn: Connection,
    *,
    run_id: Optional[int],
    report: PersonnelLifecycleReport,
) -> None:
    if run_id is None or not lifecycle_runs_available(conn):
        return

    summary = report.to_dict()
    conn.execute(
        text(
            """
            UPDATE public.hr_personnel_lifecycle_runs
            SET
                status = :status,
                completed_at = now(),
                effective_entries_processed = :effective_entries_processed,
                events_created = :events_created,
                events_existing = :events_existing,
                enrollment_created = :enrollment_created,
                enrollment_existing = :enrollment_existing,
                persons_created = :persons_created,
                persons_updated = :persons_updated,
                assignments_created = :assignments_created,
                assignments_updated = :assignments_updated,
                assignments_closed = :assignments_closed,
                warnings_count = :warnings_count,
                errors_count = :errors_count,
                summary = CAST(:summary AS jsonb)
            WHERE run_id = :run_id
            """
        ),
        {
            "run_id": int(run_id),
            "status": report.run_status,
            "effective_entries_processed": int(
                report.effective_cache.get("entries_processed", 0)
                or report.monthly_diff.get("effective_entries_compared", 0)
            ),
            "events_created": int(report.personnel_events.get("events_created", 0)),
            "events_existing": int(report.personnel_events.get("events_existing", 0)),
            "enrollment_created": int(report.enrollment.get("created", 0)),
            "enrollment_existing": int(report.enrollment.get("existing", 0)),
            "persons_created": int(report.person_sync.get("persons_created", 0)),
            "persons_updated": int(report.person_sync.get("persons_updated", 0)),
            "assignments_created": int(report.person_sync.get("assignments_created", 0)),
            "assignments_updated": int(report.person_sync.get("assignments_updated", 0)),
            "assignments_closed": int(report.person_sync.get("assignments_closed", 0)),
            "warnings_count": len(report.warnings),
            "errors_count": len(report.errors),
            "summary": _serialize_json(summary),
        },
    )


def _mark_lifecycle_run_failed(
    conn: Connection,
    *,
    run_id: Optional[int],
    error: str,
    stage: Optional[str],
) -> None:
    if run_id is None or not lifecycle_runs_available(conn):
        return
    conn.execute(
        text(
            """
            UPDATE public.hr_personnel_lifecycle_runs
            SET
                status = :status,
                completed_at = now(),
                errors_count = GREATEST(errors_count, 1),
                summary = summary || CAST(:error_summary AS jsonb)
            WHERE run_id = :run_id
            """
        ),
        {
            "run_id": int(run_id),
            "status": RUN_STATUS_FAILED,
            "error_summary": _serialize_json({"failure": {"stage": stage, "error": error}}),
        },
    )


def run_post_lifecycle_validation(
    conn: Connection,
    *,
    previous_snapshot_id: int,
    snapshot_id: int,
) -> dict[str, Any]:
    """Post-run validation checks for the lifecycle pipeline."""
    checks: list[dict[str, Any]] = []
    warnings: list[str] = []
    errors: list[str] = []

    if _table_exists(conn, "hr_review_overrides"):
        dup_overrides = conn.execute(
            text(
                """
                SELECT scope_key, field_path, COUNT(*) AS cnt
                FROM public.hr_review_overrides
                WHERE status = 'active'
                GROUP BY scope_key, field_path
                HAVING COUNT(*) > 1
                ORDER BY cnt DESC
                LIMIT 20
                """
            )
        ).mappings().all()
        count = len(dup_overrides)
        checks.append(
            {
                "code": "duplicate_active_overrides",
                "severity": "error" if count else "ok",
                "count": count,
                "samples": [dict(r) for r in dup_overrides[:5]],
            }
        )
        if count:
            errors.append(f"duplicate active overrides: {count}")

    if _table_exists(conn, "person_assignments"):
        dup_assignments = conn.execute(
            text(
                """
                SELECT person_id, lower(assignment_key) AS assignment_key, COUNT(*) AS cnt
                FROM public.person_assignments
                WHERE lifecycle_status = 'active'
                GROUP BY person_id, lower(assignment_key)
                HAVING COUNT(*) > 1
                ORDER BY cnt DESC
                LIMIT 20
                """
            )
        ).mappings().all()
        count = len(dup_assignments)
        checks.append(
            {
                "code": "duplicate_active_assignments",
                "severity": "error" if count else "ok",
                "count": count,
                "samples": [dict(r) for r in dup_assignments[:5]],
            }
        )
        if count:
            errors.append(f"duplicate active assignments: {count}")

    if _table_exists(conn, "persons") and _table_exists(conn, "person_assignments"):
        persons_without_assignment = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*) AS cnt
                    FROM public.persons p
                    WHERE p.person_status = 'active'
                      AND NOT EXISTS (
                          SELECT 1
                          FROM public.person_assignments pa
                          WHERE pa.person_id = p.person_id
                            AND pa.lifecycle_status = 'active'
                      )
                    """
                )
            ).scalar_one()
        )
        checks.append(
            {
                "code": "persons_without_active_assignment",
                "severity": "warning" if persons_without_assignment else "ok",
                "count": persons_without_assignment,
            }
        )
        if persons_without_assignment:
            warnings.append(
                f"active persons without active assignment: {persons_without_assignment}"
            )

        orphan_assignments = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*) AS cnt
                    FROM public.person_assignments pa
                    LEFT JOIN public.persons p ON p.person_id = pa.person_id
                    WHERE pa.lifecycle_status = 'active'
                      AND p.person_id IS NULL
                    """
                )
            ).scalar_one()
        )
        checks.append(
            {
                "code": "active_assignment_without_person",
                "severity": "error" if orphan_assignments else "ok",
                "count": orphan_assignments,
            }
        )
        if orphan_assignments:
            errors.append(f"active assignments without person: {orphan_assignments}")

    if _table_exists(conn, "hr_personnel_change_events"):
        stuck_detected = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*) AS cnt
                    FROM public.hr_personnel_change_events
                    WHERE previous_snapshot_id = :prior_id
                      AND snapshot_id = :new_id
                      AND status = 'detected'
                    """
                ),
                {"prior_id": int(previous_snapshot_id), "new_id": int(snapshot_id)},
            ).scalar_one()
        )
        checks.append(
            {
                "code": "personnel_events_stuck_detected",
                "severity": "warning" if stuck_detected else "ok",
                "count": stuck_detected,
            }
        )
        if stuck_detected:
            warnings.append(f"personnel events still detected: {stuck_detected}")

    if _table_exists(conn, "hr_snapshot_effective_entries") and _table_exists(
        conn, "hr_canonical_snapshot_entries"
    ):
        outdated_rows = conn.execute(
            text(
                """
                SELECT
                    s.snapshot_id,
                    COALESCE(ce.roster_count, 0) AS canonical_roster_count,
                    COALESCE(ee.effective_count, 0) AS effective_count
                FROM public.hr_canonical_snapshots s
                LEFT JOIN LATERAL (
                    SELECT COUNT(*) AS roster_count
                    FROM public.hr_canonical_snapshot_entries e
                    WHERE e.snapshot_id = s.snapshot_id
                      AND e.record_kind = 'roster'
                ) ce ON TRUE
                LEFT JOIN LATERAL (
                    SELECT COUNT(*) AS effective_count
                    FROM public.hr_snapshot_effective_entries h
                    WHERE h.snapshot_id = s.snapshot_id
                      AND h.record_kind = 'roster'
                ) ee ON TRUE
                WHERE s.snapshot_id = ANY(:ids)
                """
            ),
            {"ids": [int(previous_snapshot_id), int(snapshot_id)]},
        ).mappings().all()
        outdated_count = sum(
            1
            for row in outdated_rows
            if int(row["canonical_roster_count"]) > int(row["effective_count"])
        )
        checks.append(
            {
                "code": "outdated_effective_cache",
                "severity": "warning" if outdated_count else "ok",
                "count": outdated_count,
                "snapshots": [dict(r) for r in outdated_rows],
            }
        )
        if outdated_count:
            warnings.append(f"snapshots with outdated effective cache: {outdated_count}")

    return {
        "checks": checks,
        "warnings_count": len(warnings),
        "errors_count": len(errors),
        "warnings": warnings,
        "errors": errors,
        "validated_at": datetime.now(timezone.utc).isoformat(),
    }


def run_monthly_personnel_lifecycle_tx(
    conn: Connection,
    *,
    previous_snapshot_id: int,
    snapshot_id: int,
    dry_run: bool = True,
    refresh_cache: bool = True,
    enqueue: bool = False,
    sync_persons: bool = False,
    actor_user_id: Optional[int] = None,
) -> dict[str, Any]:
    if int(previous_snapshot_id) == int(snapshot_id):
        raise PersonnelLifecycleError(
            "previous_snapshot_id must differ from snapshot_id",
            stage="validation",
        )

    started = time.perf_counter()
    actor_id = _resolve_actor_user_id(conn, actor_user_id)
    report = PersonnelLifecycleReport(
        previous_snapshot_id=int(previous_snapshot_id),
        snapshot_id=int(snapshot_id),
        dry_run=bool(dry_run),
        refresh_cache=bool(refresh_cache),
        enqueue=bool(enqueue),
        sync_persons=bool(sync_persons),
        run_status=RUN_STATUS_RUNNING,
    )

    run_id = _create_lifecycle_run(
        conn,
        previous_snapshot_id=int(previous_snapshot_id),
        snapshot_id=int(snapshot_id),
        dry_run=bool(dry_run),
        refresh_cache=bool(refresh_cache),
        enqueue=bool(enqueue),
        sync_persons=bool(sync_persons),
        actor_user_id=actor_id,
    )
    report.run_id = run_id

    current_stage = "effective_cache"
    try:
        if refresh_cache:
            cache_result = ensure_effective_cache_for_snapshots(
                conn,
                previous_snapshot_id=int(previous_snapshot_id),
                snapshot_id=int(snapshot_id),
            )
            report.effective_cache = {
                "refreshed": True,
                "previous_refreshed": int(cache_result.get("previous_refreshed", 0)),
                "current_refreshed": int(cache_result.get("current_refreshed", 0)),
                "entries_processed": int(cache_result.get("previous_refreshed", 0))
                + int(cache_result.get("current_refreshed", 0)),
            }
        else:
            report.effective_cache = {"refreshed": False, "skipped": True}

        current_stage = "monthly_diff"
        diff_report = run_effective_monthly_diff(
            conn,
            previous_snapshot_id=int(previous_snapshot_id),
            snapshot_id=int(snapshot_id),
            dry_run=bool(dry_run),
            enqueue=bool(enqueue),
            refresh_cache=False,
        )
        report.monthly_diff = diff_report
        report.personnel_events = {
            "events_created": int(diff_report.get("events_created", 0)),
            "events_existing": int(diff_report.get("events_existing", 0)),
            "planned_count": len(diff_report.get("planned_events") or []),
        }
        report.enrollment = {
            "created": int(diff_report.get("enrollment_items_created", 0)),
            "existing": int(diff_report.get("enrollment_items_existing", 0)),
            "enabled": bool(enqueue),
        }
        report.warnings.extend(diff_report.get("warnings") or [])

        if sync_persons:
            current_stage = "person_sync"
            sync_report = sync_personnel_events_tx(
                conn,
                dry_run=bool(dry_run),
                snapshot_id=int(snapshot_id),
                actor_user_id=actor_id,
            )
            report.person_sync = sync_report
            report.warnings.extend(sync_report.get("warnings") or [])
            for item in sync_report.get("errors") or []:
                report.errors.append({"stage": "person_sync", **item})
        else:
            report.person_sync = {"skipped": True}

        current_stage = "validation"
        validation = run_post_lifecycle_validation(
            conn,
            previous_snapshot_id=int(previous_snapshot_id),
            snapshot_id=int(snapshot_id),
        )
        report.validation = validation
        report.warnings.extend(validation.get("warnings") or [])

        if report.errors:
            report.run_status = RUN_STATUS_FAILED
        else:
            report.run_status = RUN_STATUS_COMPLETED

    except (EffectiveMonthlyDiffError, PersonAssignmentSyncError, PersonnelLifecycleError) as exc:
        msg = getattr(exc, "message", str(exc))
        report.run_status = RUN_STATUS_FAILED
        report.errors.append({"stage": current_stage, "error": msg})
        _mark_lifecycle_run_failed(conn, run_id=run_id, error=msg, stage=current_stage)
        report.duration_ms = round((time.perf_counter() - started) * 1000, 2)
        _finalize_lifecycle_run(conn, run_id=run_id, report=report)
        raise PersonnelLifecycleError(msg, stage=current_stage) from exc
    except Exception as exc:
        msg = str(exc)
        report.run_status = RUN_STATUS_FAILED
        report.errors.append({"stage": current_stage, "error": msg})
        _mark_lifecycle_run_failed(conn, run_id=run_id, error=msg, stage=current_stage)
        report.duration_ms = round((time.perf_counter() - started) * 1000, 2)
        _finalize_lifecycle_run(conn, run_id=run_id, report=report)
        logger.exception("personnel lifecycle failed stage=%s", current_stage)
        raise PersonnelLifecycleError(msg, stage=current_stage) from exc

    report.duration_ms = round((time.perf_counter() - started) * 1000, 2)
    _finalize_lifecycle_run(conn, run_id=run_id, report=report)
    return report.to_dict()


def run_monthly_personnel_lifecycle(
    *,
    previous_snapshot_id: int,
    snapshot_id: int,
    dry_run: bool = True,
    refresh_cache: bool = True,
    enqueue: bool = False,
    sync_persons: bool = False,
    actor_user_id: Optional[int] = None,
    conn: Optional[Connection] = None,
) -> dict[str, Any]:
    """Run the full monthly personnel lifecycle pipeline (C3 orchestrator)."""
    kwargs = {
        "previous_snapshot_id": int(previous_snapshot_id),
        "snapshot_id": int(snapshot_id),
        "dry_run": bool(dry_run),
        "refresh_cache": bool(refresh_cache),
        "enqueue": bool(enqueue),
        "sync_persons": bool(sync_persons),
        "actor_user_id": actor_user_id,
    }
    if conn is not None:
        return run_monthly_personnel_lifecycle_tx(conn, **kwargs)

    with engine.begin() as owned_conn:
        return run_monthly_personnel_lifecycle_tx(owned_conn, **kwargs)
