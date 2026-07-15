"""PprEventRepository contract (WP-PR-010 §4.6, R3 append-only audit)."""
from __future__ import annotations

from typing import Protocol

from app.ppr.domain.event_models import PprEventAppendRequest, PprEventRecord


class PprEventRepository(Protocol):
    """Append-only audit journal for PPR events on personnel_record_events.

    Does not commit, authorize, resolve identity, or mutate envelope/person state.
    """

    def append(self, request: PprEventAppendRequest) -> PprEventRecord:
        """Append one event row; returns persisted record with generated event_id."""
        ...

    def load_by_id(self, event_id: int) -> PprEventRecord | None:
        """Load persisted event by surrogate id; None when absent."""
        ...

    def exists_by_correlation(
        self,
        correlation_id: str,
        *,
        event_type: str | None = None,
    ) -> bool:
        """True when an event with the given correlation_id (and optional type) exists."""
        ...

    def exists_by_source_event(
        self,
        source_event_id: str,
        *,
        event_type: str | None = None,
    ) -> bool:
        """True when an event with the given source_event_id (and optional type) exists."""
        ...
