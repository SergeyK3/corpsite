"""ADR-040 Phase B — monthly diff engine against active canonical HR snapshot."""
from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.models.hr_import import SOURCE_TYPE_HR_CONTROL_LIST
from app.services.hr_import_analytics_service import (
    BatchNotFoundError,
    _ensure_batch_exists,
    _load_staging_rows,
    is_real_employee_row,
)
from app.services.hr_canonical_snapshot_service import (
    RECORD_KIND_ROSTER,
    ROSTER_COMPARE_FIELDS,
    NORMALIZED_COMPARE_FIELDS,
    SNAPSHOT_STATUS_ACTIVE,
    build_normalized_base_payload,
    build_normalized_effective_payload,
    build_roster_base_payload,
    build_roster_effective_payload,
    canonical_snapshot_available,
    compute_canonical_hash,
    compute_normalized_match_key,
    compute_roster_match_key,
    get_active_snapshot,
)
from app.services.hr_import_normalized_record_service import normalized_records_available

logger = logging.getLogger(__name__)

DIFF_STATUS_UNCHANGED = "UNCHANGED"
DIFF_STATUS_NEW = "NEW"
DIFF_STATUS_CHANGED = "CHANGED"
DIFF_STATUS_REMOVED = "REMOVED"
DIFF_STATUS_CONFLICT = "CONFLICT"

DIFF_STATUSES = frozenset(
    {
        DIFF_STATUS_UNCHANGED,
        DIFF_STATUS_NEW,
        DIFF_STATUS_CHANGED,
        DIFF_STATUS_REMOVED,
        DIFF_STATUS_CONFLICT,
    }
)

DIFF_STATUSES_VISIBLE_IN_REVIEW = frozenset(
    {
        DIFF_STATUS_NEW,
        DIFF_STATUS_CHANGED,
        DIFF_STATUS_REMOVED,
        DIFF_STATUS_CONFLICT,
    }
)

HIDE_UNCHANGED_SQL = "(diff_status IS NULL OR diff_status <> 'UNCHANGED')"


class MonthlyDiffError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def row_passes_hide_unchanged(diff_status: Optional[str], *, hide_unchanged: bool) -> bool:
    if not hide_unchanged:
        return True
    return diff_status != DIFF_STATUS_UNCHANGED


def build_review_visibility(summary: dict[str, int]) -> dict[str, Any]:
    hidden_unchanged = int(summary.get(DIFF_STATUS_UNCHANGED, 0))
    visible_records = sum(int(summary.get(status, 0)) for status in DIFF_STATUSES_VISIBLE_IN_REVIEW)
    no_changes_detected = hidden_unchanged > 0 and visible_records == 0
    return {
        "visible_records": visible_records,
        "hidden_unchanged": hidden_unchanged,
        "no_changes_detected": no_changes_detected,
        "review_complete": no_changes_detected,
    }


def monthly_diff_available(conn: Connection) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'hr_import_rows'
              AND column_name = 'diff_status'
            LIMIT 1
            """
        )
    ).first()
    return row is not None


def _serialize_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _display_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def compute_field_diffs(
    *,
    canonical_payload: dict[str, Any],
    incoming_payload: dict[str, Any],
    compare_fields: frozenset[str],
) -> dict[str, dict[str, Any]]:
    diffs: dict[str, dict[str, Any]] = {}
    for field in sorted(compare_fields):
        canonical_val = _display_value(canonical_payload.get(field))
        incoming_val = _display_value(incoming_payload.get(field))
        if canonical_val != incoming_val:
            diffs[field] = {
                "canonical": canonical_val,
                "incoming": incoming_val,
            }
    return diffs


def _classify_incoming_status(
    *,
    canonical_entry: Optional[dict[str, Any]],
    incoming_hash: str,
    canonical_hash: Optional[str],
    field_diffs: dict[str, dict[str, Any]],
    incoming_base: dict[str, Any],
    incoming_effective: dict[str, Any],
    duplicate_incoming: bool,
) -> str:
    if duplicate_incoming:
        return DIFF_STATUS_CONFLICT
    if canonical_entry is None:
        return DIFF_STATUS_NEW
    if canonical_hash == incoming_hash:
        return DIFF_STATUS_UNCHANGED

    canonical_payload = dict(canonical_entry.get("payload") or {})
    corrected_fields = set(canonical_payload.get("_canonical_correction_fields") or [])
    if field_diffs and corrected_fields.intersection(field_diffs):
        return DIFF_STATUS_CONFLICT
    return DIFF_STATUS_CHANGED


def _load_active_snapshot_entries(conn: Connection, snapshot_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT
                entry_id,
                snapshot_id,
                entity_scope,
                record_kind,
                match_key,
                canonical_hash,
                employee_id,
                iin,
                payload,
                source_row_id,
                source_normalized_record_id
            FROM public.hr_canonical_snapshot_entries
            WHERE snapshot_id = :snapshot_id
            ORDER BY entry_id
            """
        ),
        {"snapshot_id": snapshot_id},
    ).mappings().all()
    return [dict(row) for row in rows]


def _clear_batch_diff_state(conn: Connection, batch_id: int) -> dict[int, dict[str, Any]]:
    from app.services.hr_import_diff_removal_decision_service import stash_removal_decisions

    stashed = stash_removal_decisions(conn, batch_id)
    conn.execute(
        text(
            """
            UPDATE public.hr_import_rows
            SET diff_status = NULL,
                canonical_snapshot_id = NULL,
                canonical_entry_id = NULL,
                canonical_hash = NULL,
                field_diffs = NULL,
                diff_computed_at = NULL
            WHERE batch_id = :batch_id
            """
        ),
        {"batch_id": batch_id},
    )
    if normalized_records_available(conn):
        conn.execute(
            text(
                """
                UPDATE public.hr_import_normalized_records
                SET diff_status = NULL,
                    canonical_snapshot_id = NULL,
                    canonical_entry_id = NULL,
                    canonical_hash = NULL,
                    field_diffs = NULL,
                    diff_computed_at = NULL
                WHERE batch_id = :batch_id
                """
            ),
            {"batch_id": batch_id},
        )
    conn.execute(
        text("DELETE FROM public.hr_import_diff_removals WHERE batch_id = :batch_id"),
        {"batch_id": batch_id},
    )
    return stashed


def _persist_row_diff(
    conn: Connection,
    *,
    row_id: int,
    snapshot_id: Optional[int],
    entry_id: Optional[int],
    diff_status: str,
    canonical_hash: Optional[str],
    field_diffs: Optional[dict[str, Any]],
    computed_at: datetime,
) -> None:
    conn.execute(
        text(
            """
            UPDATE public.hr_import_rows
            SET diff_status = :diff_status,
                canonical_snapshot_id = :snapshot_id,
                canonical_entry_id = :entry_id,
                canonical_hash = :canonical_hash,
                field_diffs = CAST(:field_diffs AS JSONB),
                diff_computed_at = :computed_at
            WHERE row_id = :row_id
            """
        ),
        {
            "row_id": row_id,
            "diff_status": diff_status,
            "snapshot_id": snapshot_id,
            "entry_id": entry_id,
            "canonical_hash": canonical_hash,
            "field_diffs": _serialize_json(field_diffs) if field_diffs else None,
            "computed_at": computed_at,
        },
    )


def _persist_normalized_diff(
    conn: Connection,
    *,
    normalized_record_id: int,
    snapshot_id: Optional[int],
    entry_id: Optional[int],
    diff_status: str,
    canonical_hash: Optional[str],
    field_diffs: Optional[dict[str, Any]],
    computed_at: datetime,
) -> None:
    conn.execute(
        text(
            """
            UPDATE public.hr_import_normalized_records
            SET diff_status = :diff_status,
                canonical_snapshot_id = :snapshot_id,
                canonical_entry_id = :entry_id,
                canonical_hash = :canonical_hash,
                field_diffs = CAST(:field_diffs AS JSONB),
                diff_computed_at = :computed_at
            WHERE normalized_record_id = :normalized_record_id
            """
        ),
        {
            "normalized_record_id": normalized_record_id,
            "diff_status": diff_status,
            "snapshot_id": snapshot_id,
            "entry_id": entry_id,
            "canonical_hash": canonical_hash,
            "field_diffs": _serialize_json(field_diffs) if field_diffs else None,
            "computed_at": computed_at,
        },
    )


def _build_incoming_roster_items(conn: Connection, batch_id: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in _load_staging_rows(conn, batch_id):
        if not is_real_employee_row(row):
            continue
        base = build_roster_base_payload(conn, batch_id=batch_id, row=row)
        effective, employee_id, match_key = build_roster_effective_payload(
            conn,
            batch_id=batch_id,
            row=row,
        )
        entity_scope = match_key
        items.append(
            {
                "row_id": int(row["row_id"]),
                "record_kind": RECORD_KIND_ROSTER,
                "match_key": match_key,
                "entity_scope": entity_scope,
                "employee_id": employee_id,
                "base_payload": base,
                "effective_payload": effective,
                "canonical_hash": compute_canonical_hash(
                    record_kind=RECORD_KIND_ROSTER,
                    entity_scope=entity_scope,
                    payload=effective,
                ),
                "compare_fields": ROSTER_COMPARE_FIELDS,
            }
        )
    return items


def _build_incoming_normalized_items(
    conn: Connection,
    batch_id: int,
    roster_match_keys: dict[int, str],
) -> list[dict[str, Any]]:
    if not normalized_records_available(conn):
        return []

    db_rows = conn.execute(
        text(
            """
            SELECT nr.*
            FROM public.hr_import_normalized_records nr
            WHERE nr.batch_id = :batch_id
            ORDER BY nr.normalized_record_id
            """
        ),
        {"batch_id": batch_id},
    ).mappings().all()

    items: list[dict[str, Any]] = []
    for db_row in db_rows:
        row = dict(db_row)
        row_id = int(row["row_id"])
        roster_match_key = roster_match_keys.get(row_id)
        if roster_match_key is None:
            parent_row = next(
                (r for r in _load_staging_rows(conn, batch_id) if int(r["row_id"]) == row_id),
                None,
            )
            if parent_row and is_real_employee_row(parent_row):
                _, _, roster_match_key = build_roster_effective_payload(
                    conn,
                    batch_id=batch_id,
                    row=parent_row,
                )
        if roster_match_key is None:
            roster_match_key = f"row:{row_id}"

        record_kind = str(row.get("record_kind") or "").strip()
        source_record_key = str(row.get("source_record_key") or "").strip()
        match_key = compute_normalized_match_key(
            roster_match_key=roster_match_key,
            record_kind=record_kind,
            source_record_key=source_record_key,
        )
        base = build_normalized_base_payload(row)
        effective = build_normalized_effective_payload(row)
        entity_scope = f"{roster_match_key}|{record_kind}"
        items.append(
            {
                "normalized_record_id": int(row["normalized_record_id"]),
                "row_id": row_id,
                "record_kind": record_kind,
                "match_key": match_key,
                "entity_scope": entity_scope,
                "employee_id": int(row["employee_id"]) if row.get("employee_id") is not None else None,
                "base_payload": base,
                "effective_payload": effective,
                "canonical_hash": compute_canonical_hash(
                    record_kind=record_kind,
                    entity_scope=entity_scope,
                    payload=effective,
                ),
                "compare_fields": NORMALIZED_COMPARE_FIELDS,
            }
        )
    return items


def compute_batch_monthly_diff(conn: Connection, batch_id: int) -> dict[str, Any]:
    if not monthly_diff_available(conn):
        raise MonthlyDiffError("monthly diff columns are not available")
    if not canonical_snapshot_available(conn):
        raise MonthlyDiffError("canonical snapshot tables are not available")

    _ensure_batch_exists(conn, batch_id)
    batch = conn.execute(
        text(
            """
            SELECT batch_id, source_type
            FROM public.hr_import_batches
            WHERE batch_id = :batch_id
            """
        ),
        {"batch_id": batch_id},
    ).mappings().first()
    if not batch:
        raise BatchNotFoundError(f"batch_id={batch_id} not found")

    source_type = str(batch["source_type"] or SOURCE_TYPE_HR_CONTROL_LIST)
    computed_at = datetime.now(timezone.utc)
    stashed_decisions = _clear_batch_diff_state(conn, batch_id)

    from app.services.hr_baseline_service import (
        baseline_tables_available,
        resolve_comparison_baseline,
        update_batch_diff_tracking,
        _resolve_batch_report_period,
    )

    if baseline_tables_available(conn):
        import_report_period = _resolve_batch_report_period(conn, batch_id)
        comparison_baseline = resolve_comparison_baseline(conn, import_report_period)
    else:
        import_report_period = None
        comparison_baseline = get_active_snapshot(conn, source_type=source_type)
    roster_items = _build_incoming_roster_items(conn, batch_id)
    roster_match_keys = {item["row_id"]: item["match_key"] for item in roster_items}
    normalized_items = _build_incoming_normalized_items(conn, batch_id, roster_match_keys)
    incoming_items = roster_items + normalized_items

    summary = {
        DIFF_STATUS_UNCHANGED: 0,
        DIFF_STATUS_NEW: 0,
        DIFF_STATUS_CHANGED: 0,
        DIFF_STATUS_REMOVED: 0,
        DIFF_STATUS_CONFLICT: 0,
    }

    if comparison_baseline is None:
        snapshot_id = None
        publication_origin_id = None
        for item in incoming_items:
            summary[DIFF_STATUS_NEW] += 1
            if item.get("row_id") is not None and "normalized_record_id" not in item:
                _persist_row_diff(
                    conn,
                    row_id=int(item["row_id"]),
                    snapshot_id=None,
                    entry_id=None,
                    diff_status=DIFF_STATUS_NEW,
                    canonical_hash=item["canonical_hash"],
                    field_diffs=None,
                    computed_at=computed_at,
                )
            elif item.get("normalized_record_id") is not None:
                _persist_normalized_diff(
                    conn,
                    normalized_record_id=int(item["normalized_record_id"]),
                    snapshot_id=None,
                    entry_id=None,
                    diff_status=DIFF_STATUS_NEW,
                    canonical_hash=item["canonical_hash"],
                    field_diffs=None,
                    computed_at=computed_at,
                )
        if baseline_tables_available(conn):
            update_batch_diff_tracking(
                conn,
                batch_id,
                comparison_baseline_id=None,
                comparison_publication_origin_id=None,
            )
        return {
            "batch_id": batch_id,
            "snapshot_id": None,
            "baseline_id": None,
            "computed_at": computed_at.isoformat(),
            "summary": summary,
            "removed": [],
            "skipped": False,
        }

    snapshot_id = int(comparison_baseline["baseline_id"])
    publication_origin_id = comparison_baseline.get("publication_origin_id")
    canonical_entries = _load_active_snapshot_entries(conn, snapshot_id)
    canonical_by_key = {str(entry["match_key"]): entry for entry in canonical_entries}
    incoming_key_counts = Counter(str(item["match_key"]) for item in incoming_items)
    matched_canonical_keys: set[str] = set()

    for item in incoming_items:
        match_key = str(item["match_key"])
        duplicate_incoming = incoming_key_counts[match_key] > 1
        canonical_entry = canonical_by_key.get(match_key)
        canonical_payload = dict(canonical_entry["payload"]) if canonical_entry else {}
        record_kind = str(item["record_kind"])
        entity_scope = str(item["entity_scope"])

        field_diffs = compute_field_diffs(
            canonical_payload=canonical_payload,
            incoming_payload=item["effective_payload"],
            compare_fields=item["compare_fields"],
        ) if canonical_entry else {}

        canonical_hash_for_compare = (
            compute_canonical_hash(
                record_kind=record_kind,
                entity_scope=entity_scope,
                payload=canonical_payload,
            )
            if canonical_entry
            else None
        )

        diff_status = _classify_incoming_status(
            canonical_entry=canonical_entry,
            incoming_hash=item["canonical_hash"],
            canonical_hash=canonical_hash_for_compare,
            field_diffs=field_diffs,
            incoming_base=item["base_payload"],
            incoming_effective=item["effective_payload"],
            duplicate_incoming=duplicate_incoming,
        )
        summary[diff_status] += 1

        entry_id = int(canonical_entry["entry_id"]) if canonical_entry else None
        persist_field_diffs = field_diffs if diff_status in {DIFF_STATUS_CHANGED, DIFF_STATUS_CONFLICT} else None

        if item.get("row_id") is not None and "normalized_record_id" not in item:
            _persist_row_diff(
                conn,
                row_id=int(item["row_id"]),
                snapshot_id=snapshot_id,
                entry_id=entry_id,
                diff_status=diff_status,
                canonical_hash=item["canonical_hash"],
                field_diffs=persist_field_diffs,
                computed_at=computed_at,
            )
        elif item.get("normalized_record_id") is not None:
            _persist_normalized_diff(
                conn,
                normalized_record_id=int(item["normalized_record_id"]),
                snapshot_id=snapshot_id,
                entry_id=entry_id,
                diff_status=diff_status,
                canonical_hash=item["canonical_hash"],
                field_diffs=persist_field_diffs,
                computed_at=computed_at,
            )

        if canonical_entry is not None and not duplicate_incoming:
            matched_canonical_keys.add(match_key)

    removed_items: list[dict[str, Any]] = []
    for entry in canonical_entries:
        match_key = str(entry["match_key"])
        if match_key in matched_canonical_keys:
            continue
        summary[DIFF_STATUS_REMOVED] += 1
        conn.execute(
            text(
                """
                INSERT INTO public.hr_import_diff_removals (
                    batch_id,
                    canonical_snapshot_id,
                    canonical_entry_id,
                    match_key,
                    record_kind,
                    canonical_hash,
                    payload,
                    diff_status,
                    diff_computed_at
                )
                VALUES (
                    :batch_id,
                    :snapshot_id,
                    :entry_id,
                    :match_key,
                    :record_kind,
                    :canonical_hash,
                    CAST(:payload AS JSONB),
                    :diff_status,
                    :computed_at
                )
                """
            ),
            {
                "batch_id": batch_id,
                "snapshot_id": snapshot_id,
                "entry_id": int(entry["entry_id"]),
                "match_key": match_key,
                "record_kind": str(entry["record_kind"]),
                "canonical_hash": str(entry["canonical_hash"]),
                "payload": _serialize_json(dict(entry.get("payload") or {})),
                "diff_status": DIFF_STATUS_REMOVED,
                "computed_at": computed_at,
            },
        )
        removed_items.append(
            {
                "canonical_entry_id": int(entry["entry_id"]),
                "match_key": match_key,
                "record_kind": str(entry["record_kind"]),
                "diff_status": DIFF_STATUS_REMOVED,
                "payload": dict(entry.get("payload") or {}),
            }
        )

    if baseline_tables_available(conn):
        update_batch_diff_tracking(
            conn,
            batch_id,
            comparison_baseline_id=snapshot_id,
            comparison_publication_origin_id=int(publication_origin_id)
            if publication_origin_id is not None
            else None,
        )

    from app.services.hr_import_diff_removal_decision_service import restore_removal_decisions

    restore_removal_decisions(conn, batch_id, stashed_decisions)

    return {
        "batch_id": batch_id,
        "snapshot_id": snapshot_id,
        "baseline_id": snapshot_id,
        "computed_at": computed_at.isoformat(),
        "summary": summary,
        "removed": removed_items,
        "skipped": False,
    }


def get_batch_diff_summary(conn: Connection, batch_id: int) -> dict[str, Any]:
    _ensure_batch_exists(conn, batch_id)
    from app.services.hr_baseline_service import ensure_batch_diff_fresh

    ensure_batch_diff_fresh(conn, batch_id)
    if not monthly_diff_available(conn):
        return {"batch_id": batch_id, "skipped": True, "summary": {}, "removed": [], "review_visibility": build_review_visibility({})}

    summary = {status: 0 for status in DIFF_STATUSES}
    row_counts = conn.execute(
        text(
            """
            SELECT diff_status, COUNT(*) AS cnt
            FROM public.hr_import_rows
            WHERE batch_id = :batch_id
              AND diff_status IS NOT NULL
            GROUP BY diff_status
            """
        ),
        {"batch_id": batch_id},
    ).mappings().all()
    for row in row_counts:
        summary[str(row["diff_status"])] = int(row["cnt"])

    if normalized_records_available(conn):
        norm_counts = conn.execute(
            text(
                """
                SELECT diff_status, COUNT(*) AS cnt
                FROM public.hr_import_normalized_records
                WHERE batch_id = :batch_id
                  AND diff_status IS NOT NULL
                GROUP BY diff_status
                """
            ),
            {"batch_id": batch_id},
        ).mappings().all()
        for row in norm_counts:
            summary[str(row["diff_status"])] = summary.get(str(row["diff_status"]), 0) + int(row["cnt"])

    from app.services.hr_import_diff_removal_decision_service import (
        count_pending_diff_removals,
        diff_removal_decisions_available,
        list_confirmed_diff_removals,
        list_pending_diff_removals,
        list_restored_diff_removals,
    )

    pending_removed_count = count_pending_diff_removals(conn, batch_id)
    summary[DIFF_STATUS_REMOVED] = summary.get(DIFF_STATUS_REMOVED, 0) + pending_removed_count

    if diff_removal_decisions_available(conn):
        removed = list_pending_diff_removals(conn, batch_id)
        restored = list_restored_diff_removals(conn, batch_id)
        confirmed_removals = list_confirmed_diff_removals(conn, batch_id)
    else:
        removed_rows = conn.execute(
            text(
                """
                SELECT
                    removal_id,
                    canonical_entry_id,
                    match_key,
                    record_kind,
                    canonical_hash,
                    payload,
                    diff_status,
                    diff_computed_at
                FROM public.hr_import_diff_removals
                WHERE batch_id = :batch_id
                ORDER BY removal_id
                """
            ),
            {"batch_id": batch_id},
        ).mappings().all()
        removed = [dict(row) for row in removed_rows]
        restored = []
        confirmed_removals = []

    snapshot_id = conn.execute(
        text(
            """
            SELECT canonical_snapshot_id
            FROM public.hr_import_rows
            WHERE batch_id = :batch_id
              AND canonical_snapshot_id IS NOT NULL
            LIMIT 1
            """
        ),
        {"batch_id": batch_id},
    ).scalar_one_or_none()
    if snapshot_id is None and normalized_records_available(conn):
        snapshot_id = conn.execute(
            text(
                """
                SELECT canonical_snapshot_id
                FROM public.hr_import_normalized_records
                WHERE batch_id = :batch_id
                  AND canonical_snapshot_id IS NOT NULL
                LIMIT 1
                """
            ),
            {"batch_id": batch_id},
        ).scalar_one_or_none()

    diff_computed_at = conn.execute(
        text(
            """
            SELECT MAX(diff_computed_at)
            FROM public.hr_import_rows
            WHERE batch_id = :batch_id
            """
        ),
        {"batch_id": batch_id},
    ).scalar_one_or_none()

    return {
        "batch_id": batch_id,
        "snapshot_id": int(snapshot_id) if snapshot_id is not None else None,
        "computed_at": diff_computed_at.isoformat() if diff_computed_at else None,
        "summary": summary,
        "removed": removed,
        "restored": restored,
        "confirmed_removals": confirmed_removals,
        "pending_removals": pending_removed_count,
        "skipped": False,
        "review_visibility": build_review_visibility(summary),
    }


def load_row_diff_fields(conn: Connection, batch_id: int) -> dict[int, dict[str, Any]]:
    if not monthly_diff_available(conn):
        return {}
    rows = conn.execute(
        text(
            """
            SELECT
                row_id,
                diff_status,
                canonical_snapshot_id,
                canonical_entry_id,
                canonical_hash,
                field_diffs,
                diff_computed_at
            FROM public.hr_import_rows
            WHERE batch_id = :batch_id
            """
        ),
        {"batch_id": batch_id},
    ).mappings().all()
    result: dict[int, dict[str, Any]] = {}
    for row in rows:
        field_diffs = row.get("field_diffs")
        if isinstance(field_diffs, str):
            field_diffs = json.loads(field_diffs)
        result[int(row["row_id"])] = {
            "diff_status": row.get("diff_status"),
            "canonical_snapshot_id": int(row["canonical_snapshot_id"])
            if row.get("canonical_snapshot_id") is not None
            else None,
            "canonical_entry_id": int(row["canonical_entry_id"])
            if row.get("canonical_entry_id") is not None
            else None,
            "canonical_hash": row.get("canonical_hash"),
            "field_diffs": field_diffs,
            "diff_computed_at": row["diff_computed_at"].isoformat()
            if row.get("diff_computed_at") is not None
            else None,
        }
    return result


def maybe_compute_batch_monthly_diff(conn: Connection, batch_id: int) -> Optional[dict[str, Any]]:
    if not monthly_diff_available(conn) or not canonical_snapshot_available(conn):
        return None
    from app.services.hr_baseline_service import ensure_batch_diff_fresh

    stale_result = ensure_batch_diff_fresh(conn, batch_id)
    if stale_result is not None:
        return stale_result
    row = conn.execute(
        text("SELECT diff_status FROM public.hr_import_batches WHERE batch_id = :batch_id"),
        {"batch_id": batch_id},
    ).mappings().first()
    if row and row.get("diff_status") == "CURRENT":
        return None
    savepoint = conn.begin_nested()
    try:
        result = compute_batch_monthly_diff(conn, batch_id)
        savepoint.commit()
        return result
    except Exception:
        savepoint.rollback()
        logger.exception("failed to compute monthly diff for batch_id=%s", batch_id)
        return None
