"""MRD workspace read model for the baseline records working screen."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy.engine import Connection

from app.mrd.domain.errors import MrdNotFoundError
from app.mrd.domain.period_window import get_creation_window_periods
from app.mrd.domain.types import DIFFERENCE_LIFECYCLE_DETECTED
from app.mrd.infrastructure.repository import MrdEntryRow, MrdVersionDetailRow, SqlAlchemyMrdRepository


@dataclass(frozen=True, slots=True)
class MrdWorkspaceSnapshot:
    summary: MrdVersionDetailRow
    detected_differences_count: int
    pending_differences_count: int
    confirmed_changes_count: int
    entries: tuple[MrdEntryRow, ...]
    entries_total: int
    confirmed_changes: tuple[dict[str, Any], ...]
    confirmed_changes_total: int


def fetch_creation_window(conn: Connection, *, reference: date | None = None) -> dict:
    periods = get_creation_window_periods(reference)
    return {
        "reference_date": (reference or date.today()).isoformat(),
        "allowed_periods": [p.isoformat() for p in periods],
    }


def fetch_mrd_workspace(
    conn: Connection,
    *,
    mrd_id: int,
    entries_limit: int = 50,
    entries_offset: int = 0,
    confirmed_limit: int = 20,
    confirmed_offset: int = 0,
) -> MrdWorkspaceSnapshot:
    repo = SqlAlchemyMrdRepository(conn)
    summary = repo.load_mrd_version_detail(mrd_id)
    if summary is None:
        raise MrdNotFoundError(f"mrd_id={mrd_id} not found")

    entries, entries_total = repo.list_mrd_entries_page(
        mrd_id=mrd_id,
        limit=entries_limit,
        offset=entries_offset,
    )
    confirmed_changes, confirmed_total = repo.list_confirmed_changes_for_mrd(
        mrd_id=mrd_id,
        limit=confirmed_limit,
        offset=confirmed_offset,
    )
    pending = repo.count_differences_for_mrd_by_status(mrd_id, DIFFERENCE_LIFECYCLE_DETECTED)
    detected_total = repo.count_differences_for_mrd(mrd_id)

    return MrdWorkspaceSnapshot(
        summary=summary,
        detected_differences_count=detected_total,
        pending_differences_count=pending,
        confirmed_changes_count=confirmed_total,
        entries=tuple(entries),
        entries_total=entries_total,
        confirmed_changes=tuple(confirmed_changes),
        confirmed_changes_total=confirmed_total,
    )


def workspace_to_dict(snapshot: MrdWorkspaceSnapshot) -> dict:
    summary = snapshot.summary
    return {
        "summary": {
            "mrd_id": summary.mrd_id,
            "report_period": summary.report_period,
            "version": summary.version,
            "status": summary.status,
            "row_version": summary.row_version,
            "entry_count": summary.entry_count,
            "forked_from_reference_id": summary.forked_from_reference_id,
            "is_active_for_period": summary.status == "ACTIVE",
        },
        "metrics": {
            "detected_differences_count": snapshot.detected_differences_count,
            "pending_differences_count": snapshot.pending_differences_count,
            "confirmed_changes_count": snapshot.confirmed_changes_count,
        },
        "entries": {
            "total": snapshot.entries_total,
            "items": [
                {
                    "entry_id": row.entry_id,
                    "match_key": row.match_key,
                    "entity_scope": row.entity_scope,
                    "record_kind": row.record_kind,
                    "effective_payload": row.effective_payload,
                    "row_version": row.row_version,
                }
                for row in snapshot.entries
            ],
        },
        "confirmed_changes": {
            "total": snapshot.confirmed_changes_total,
            "items": [
                {
                    "confirmed_change_id": row["confirmed_change_id"],
                    "entity_scope": row["entity_scope"],
                    "attribute": row["attribute"],
                    "old_value": row["old_value"],
                    "new_value": row["new_value"],
                    "confirmed_at": row["confirmed_at"].isoformat()
                    if hasattr(row["confirmed_at"], "isoformat")
                    else row["confirmed_at"],
                    "difference_origin_code": row["difference_origin_code"],
                    "source_batch_id": row["source_batch_id"],
                    "basis": row["basis"],
                }
                for row in snapshot.confirmed_changes
            ],
        },
    }
