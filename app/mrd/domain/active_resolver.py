"""Strict ACTIVE MRD resolution (WP-MRD-003)."""
from __future__ import annotations

from datetime import date

from app.mrd.domain.errors import ActiveMrdAmbiguousError, ActiveMrdMissingError
from app.mrd.infrastructure.repository import MonthlyReferenceRow, SqlAlchemyMrdRepository


def require_active_mrd(repo: SqlAlchemyMrdRepository, report_period: date) -> MonthlyReferenceRow:
    """Return the single ACTIVE MRD for report_period or raise a domain error."""
    rows = repo.list_active_mrd_candidates(report_period)
    if not rows:
        raise ActiveMrdMissingError(f"No ACTIVE MRD for report_period={report_period.isoformat()}")
    if len(rows) > 1:
        raise ActiveMrdAmbiguousError(
            f"Multiple ACTIVE MRD rows for report_period={report_period.isoformat()}"
        )
    return rows[0]
