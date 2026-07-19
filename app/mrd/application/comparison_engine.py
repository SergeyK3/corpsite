"""Import vs ACTIVE MRD comparison engine (reuses ADR-040 primitives)."""
from __future__ import annotations

from datetime import date

from sqlalchemy.engine import Connection

from app.mrd.domain.candidate_builder import build_candidates_for_item
from app.mrd.domain.comparison_models import ComparisonCandidate
from app.mrd.infrastructure.repository import SqlAlchemyMrdRepository
from app.services.hr_canonical_snapshot_service import compute_canonical_hash
from app.services.hr_import_monthly_diff_service import (
    DIFF_STATUS_NEW,
    DIFF_STATUS_REMOVED,
    _build_incoming_normalized_items,
    _build_incoming_roster_items,
    _classify_incoming_status,
    compute_field_diffs,
)


class ImportMrdComparisonEngine:
    """Build attribute-level candidates by comparing import batch to ACTIVE MRD."""

    def __init__(self, conn: Connection) -> None:
        self._conn = conn
        self._repo = SqlAlchemyMrdRepository(conn)

    def build_candidates(
        self,
        *,
        batch_id: int,
        mrd_id: int,
        report_period: date,
    ) -> list[ComparisonCandidate]:
        roster_items = _build_incoming_roster_items(self._conn, batch_id)
        roster_match_keys = {item["row_id"]: item["match_key"] for item in roster_items}
        normalized_items = _build_incoming_normalized_items(
            self._conn,
            batch_id,
            roster_match_keys,
        )
        incoming_items = roster_items + normalized_items

        mrd_entries = self._repo.load_mrd_entries(mrd_id)
        mrd_by_key = {entry.match_key: entry for entry in mrd_entries}
        matched_keys: set[str] = set()
        candidates: list[ComparisonCandidate] = []

        incoming_key_counts: dict[str, int] = {}
        for item in incoming_items:
            incoming_key_counts[item["match_key"]] = incoming_key_counts.get(item["match_key"], 0) + 1

        for item in incoming_items:
            match_key = str(item["match_key"])
            duplicate_incoming = incoming_key_counts[match_key] > 1
            mrd_entry = mrd_by_key.get(match_key)
            canonical_payload = dict(mrd_entry.effective_payload) if mrd_entry else {}
            record_kind = str(item["record_kind"])
            entity_scope = str(item["entity_scope"])

            field_diffs = (
                compute_field_diffs(
                    canonical_payload=canonical_payload,
                    incoming_payload=item["effective_payload"],
                    compare_fields=item["compare_fields"],
                )
                if mrd_entry
                else {}
            )
            canonical_hash = (
                compute_canonical_hash(
                    record_kind=record_kind,
                    entity_scope=entity_scope,
                    payload=canonical_payload,
                )
                if mrd_entry
                else None
            )
            diff_status = _classify_incoming_status(
                canonical_entry={"payload": canonical_payload} if mrd_entry else None,
                incoming_hash=item["canonical_hash"],
                canonical_hash=canonical_hash,
                field_diffs=field_diffs,
                incoming_base=item["base_payload"],
                incoming_effective=item["effective_payload"],
                duplicate_incoming=duplicate_incoming,
            )
            candidates.extend(
                build_candidates_for_item(
                    report_period=report_period,
                    mrd_id=mrd_id,
                    match_key=match_key,
                    entity_scope=entity_scope,
                    record_kind=record_kind,
                    diff_status=diff_status,
                    field_diffs=field_diffs,
                    incoming_effective=item["effective_payload"],
                    canonical_payload=canonical_payload,
                    compare_fields=item["compare_fields"],
                    batch_id=batch_id,
                    row_id=int(item["row_id"]) if item.get("row_id") is not None else None,
                    normalized_record_id=(
                        int(item["normalized_record_id"])
                        if item.get("normalized_record_id") is not None
                        else None
                    ),
                )
            )
            if mrd_entry is not None and not duplicate_incoming:
                matched_keys.add(match_key)

        for entry in mrd_entries:
            if entry.match_key in matched_keys:
                continue
            candidates.extend(
                build_candidates_for_item(
                    report_period=report_period,
                    mrd_id=mrd_id,
                    match_key=entry.match_key,
                    entity_scope=entry.entity_scope,
                    record_kind=entry.record_kind,
                    diff_status=DIFF_STATUS_REMOVED,
                    field_diffs={},
                    incoming_effective={},
                    canonical_payload=entry.effective_payload,
                    compare_fields=frozenset(),
                    batch_id=batch_id,
                )
            )

        return candidates
