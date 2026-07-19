"""ACTIVE MRD application helpers (WP-MRD-003)."""
from __future__ import annotations

from datetime import date

from sqlalchemy.engine import Connection

from app.mrd.domain.active_resolver import require_active_mrd
from app.mrd.infrastructure.repository import MonthlyReferenceRow, SqlAlchemyMrdRepository


def resolve_active_mrd(conn: Connection, report_period: date) -> MonthlyReferenceRow | None:
    """Return ACTIVE MRD for report_period or None (non-strict)."""
    repo = SqlAlchemyMrdRepository(conn)
    return repo.resolve_active_mrd(report_period)


def require_active_mrd_for_period(conn: Connection, report_period: date) -> MonthlyReferenceRow:
    """Return the single ACTIVE MRD or raise ActiveMrdMissingError / ActiveMrdAmbiguousError."""
    repo = SqlAlchemyMrdRepository(conn)
    return require_active_mrd(repo, report_period)
