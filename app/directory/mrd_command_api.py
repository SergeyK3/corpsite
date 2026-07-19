"""MRD command API adapters (WP-MRD-004)."""
from __future__ import annotations

from datetime import date

from sqlalchemy.engine import Connection

from app.mrd.application.fork_period_service import ForkPeriodService
from app.mrd.application.fork_version_service import ForkVersionService
from app.mrd.application.query_service import (
    ForkSourcesSnapshot,
    PeriodVersionsSnapshot,
    get_active_mrd,
    get_period_versions,
    list_all_mrd_versions,
    list_fork_sources,
)
from app.mrd.domain.fork_models import ForkPeriodCommand, ForkVersionCommand, ForkPeriodResult, ForkVersionResult
from app.mrd.infrastructure.command_idempotency_repository import SqlAlchemyMrdCommandIdempotencyRepository
from app.mrd.infrastructure.repository import MrdVersionDetailRow, SqlAlchemyMrdRepository

MUTATION_STATUS_COMMITTED = "committed"
MUTATION_STATUS_IDEMPOTENT_REPLAY = "idempotent_replay"


def _to_summary(row: MrdVersionDetailRow, *, active_by_period: dict[str, int] | None = None) -> dict:
    period_key = row.report_period.isoformat()
    is_active = (
        row.status == "ACTIVE"
        if active_by_period is None
        else active_by_period.get(period_key) == row.mrd_id
    )
    return {
        "mrd_id": row.mrd_id,
        "report_period": row.report_period,
        "version": row.version,
        "status": row.status,
        "row_version": row.row_version,
        "entry_count": row.entry_count,
        "forked_from_reference_id": row.forked_from_reference_id,
        "is_active_for_period": is_active,
    }


def fetch_active_mrd(conn: Connection, report_period: date) -> dict:
    active = get_active_mrd(conn, report_period)
    return {
        "report_period": report_period,
        "active": _to_summary(active) if active is not None else None,
    }


def fetch_period_versions(conn: Connection, report_period: date) -> dict:
    snapshot: PeriodVersionsSnapshot = get_period_versions(conn, report_period)
    active_id = snapshot.active.mrd_id if snapshot.active is not None else None
    active_by_period = {report_period.isoformat(): active_id} if active_id is not None else {}
    return {
        "report_period": report_period,
        "active": _to_summary(snapshot.active) if snapshot.active is not None else None,
        "items": [_to_summary(row, active_by_period=active_by_period) for row in snapshot.versions],
    }


def fetch_all_versions(conn: Connection) -> dict:
    rows = list_all_mrd_versions(conn)
    active_by_period = {
        row.report_period.isoformat(): row.mrd_id for row in rows if row.status == "ACTIVE"
    }
    return {
        "report_period": None,
        "active": None,
        "items": [_to_summary(row, active_by_period=active_by_period) for row in rows],
    }


def fetch_fork_sources(conn: Connection) -> dict:
    snapshot: ForkSourcesSnapshot = list_fork_sources(conn)
    return {
        "items": [_to_summary(row, active_by_period=snapshot.active_by_period) for row in snapshot.items],
        "active_by_period": snapshot.active_by_period,
    }


def run_fork_version(
    conn: Connection,
    *,
    command_id: str,
    source_mrd_id: int,
    performed_by: int,
    expected_active_row_version: int | None,
    notes: str | None,
) -> tuple[str, ForkVersionResult]:
    repo = SqlAlchemyMrdRepository(conn)
    idempotency = SqlAlchemyMrdCommandIdempotencyRepository(conn)
    service = ForkVersionService(repo, idempotency)
    result = service.fork_version(
        ForkVersionCommand(
            command_id=command_id,
            source_mrd_id=source_mrd_id,
            performed_by=performed_by,
            expected_active_row_version=expected_active_row_version,
            notes=notes,
        )
    )
    status = MUTATION_STATUS_IDEMPOTENT_REPLAY if result.idempotent_replay else MUTATION_STATUS_COMMITTED
    return status, result


def run_fork_period(
    conn: Connection,
    *,
    command_id: str,
    source_mrd_id: int,
    target_report_period: date,
    performed_by: int,
    notes: str | None,
) -> tuple[str, ForkPeriodResult]:
    repo = SqlAlchemyMrdRepository(conn)
    idempotency = SqlAlchemyMrdCommandIdempotencyRepository(conn)
    service = ForkPeriodService(repo, idempotency)
    result = service.fork_period(
        ForkPeriodCommand(
            command_id=command_id,
            source_mrd_id=source_mrd_id,
            target_report_period=target_report_period,
            performed_by=performed_by,
            notes=notes,
        )
    )
    status = MUTATION_STATUS_IDEMPOTENT_REPLAY if result.idempotent_replay else MUTATION_STATUS_COMMITTED
    return status, result


def fork_result_to_dict(result: ForkVersionResult | ForkPeriodResult) -> dict:
    payload = {
        "command_id": result.command_id,
        "source_mrd_id": result.source_mrd_id,
        "target_mrd_id": result.target_mrd_id,
        "target_report_period": result.target_report_period,
        "target_version": result.target_version,
        "copied_entry_count": result.copied_entry_count,
        "version_event_ids": list(result.version_event_ids),
    }
    if isinstance(result, ForkVersionResult):
        payload["closed_mrd_id"] = result.closed_mrd_id
    else:
        payload["closed_mrd_id"] = None
    return payload
