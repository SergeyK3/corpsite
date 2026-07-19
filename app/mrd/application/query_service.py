"""MRD read/query helpers for REST API (WP-MRD-004)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.engine import Connection

from app.mrd.domain.active_resolver import require_active_mrd
from app.mrd.domain.errors import ActiveMrdMissingError
from app.mrd.infrastructure.repository import MrdVersionDetailRow, SqlAlchemyMrdRepository


@dataclass(frozen=True, slots=True)
class PeriodVersionsSnapshot:
    report_period: date
    active: MrdVersionDetailRow | None
    versions: tuple[MrdVersionDetailRow, ...]


@dataclass(frozen=True, slots=True)
class ForkSourcesSnapshot:
    items: tuple[MrdVersionDetailRow, ...]
    active_by_period: dict[str, int]


def list_all_mrd_versions(conn: Connection) -> list[MrdVersionDetailRow]:
    repo = SqlAlchemyMrdRepository(conn)
    return repo.list_mrd_version_details()


def get_period_versions(conn: Connection, report_period: date) -> PeriodVersionsSnapshot:
    repo = SqlAlchemyMrdRepository(conn)
    versions = repo.list_mrd_version_details(report_period=report_period)
    active = get_active_mrd(conn, report_period)
    return PeriodVersionsSnapshot(
        report_period=report_period,
        active=active,
        versions=tuple(versions),
    )


def get_active_mrd(conn: Connection, report_period: date) -> MrdVersionDetailRow | None:
    repo = SqlAlchemyMrdRepository(conn)
    active = repo.resolve_active_mrd(report_period)
    if active is None:
        return None
    return repo.load_mrd_version_detail(active.mrd_id)


def require_active_mrd_detail(conn: Connection, report_period: date) -> MrdVersionDetailRow:
    repo = SqlAlchemyMrdRepository(conn)
    active = require_active_mrd(repo, report_period)
    detail = repo.load_mrd_version_detail(active.mrd_id)
    if detail is None:
        raise ActiveMrdMissingError(f"No ACTIVE MRD for report_period={report_period.isoformat()}")
    return detail


def list_fork_sources(conn: Connection) -> ForkSourcesSnapshot:
    repo = SqlAlchemyMrdRepository(conn)
    items = repo.list_mrd_version_details()
    active_by_period: dict[str, int] = {}
    for row in items:
        if row.status == "ACTIVE":
            active_by_period[row.report_period.isoformat()] = row.mrd_id
    return ForkSourcesSnapshot(items=tuple(items), active_by_period=active_by_period)
