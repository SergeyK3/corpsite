"""Event summary reader for composite read (R6 — read-only, no append)."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.ppr.domain.event_models import PprEventRecord
from app.ppr.infrastructure.ppr_event_repository import _EVENT_SELECT_COLUMNS, _mapping_to_event
from app.ppr.read.models import PprEventSummary, PprEventSummaryEntry


class PprEventSummaryReader:
    """Loads recent event rows for a person — not full history."""

    DEFAULT_LIMIT = 10

    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def load_recent(
        self,
        person_id: int,
        *,
        limit: int = DEFAULT_LIMIT,
    ) -> PprEventSummary:
        bounded_limit = max(1, min(int(limit), 100))
        rows = (
            self._conn.execute(
                text(
                    f"""
                    SELECT {_EVENT_SELECT_COLUMNS}
                    FROM public.personnel_record_events
                    WHERE person_id = :person_id
                    ORDER BY event_at DESC, event_id DESC
                    LIMIT :limit
                    """
                ),
                {"person_id": int(person_id), "limit": bounded_limit},
            )
            .mappings()
            .all()
        )
        recent = tuple(
            PprEventSummaryEntry.from_record(_mapping_to_event(row)) for row in rows
        )
        return PprEventSummary(
            recent=recent,
            returned_count=len(recent),
            limit=bounded_limit,
        )

    def load_by_id(self, event_id: int) -> PprEventRecord | None:
        row = (
            self._conn.execute(
                text(
                    f"""
                    SELECT {_EVENT_SELECT_COLUMNS}
                    FROM public.personnel_record_events
                    WHERE event_id = :event_id
                    """
                ),
                {"event_id": int(event_id)},
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        return _mapping_to_event(row)
