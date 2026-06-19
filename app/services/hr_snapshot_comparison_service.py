"""ADR-040 Phase F — snapshot comparison and materialized HR change events."""
from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import date, datetime
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.services.hr_canonical_snapshot_service import (
    NORMALIZED_COMPARE_FIELDS,
    RECORD_KIND_ROSTER,
    ROSTER_COMPARE_FIELDS,
)
from app.services.hr_import_monthly_diff_service import compute_field_diffs

logger = logging.getLogger(__name__)

EVENT_TYPE_NEW = "NEW"
EVENT_TYPE_REMOVED = "REMOVED"
EVENT_TYPE_POSITION_CHANGED = "POSITION_CHANGED"
EVENT_TYPE_DEPARTMENT_CHANGED = "DEPARTMENT_CHANGED"
EVENT_TYPE_EDUCATION_CHANGED = "EDUCATION_CHANGED"
EVENT_TYPE_CERTIFICATE_CHANGED = "CERTIFICATE_CHANGED"

EVENT_TYPES = frozenset(
    {
        EVENT_TYPE_NEW,
        EVENT_TYPE_REMOVED,
        EVENT_TYPE_POSITION_CHANGED,
        EVENT_TYPE_DEPARTMENT_CHANGED,
        EVENT_TYPE_EDUCATION_CHANGED,
        EVENT_TYPE_CERTIFICATE_CHANGED,
    }
)

ROSTER_FIELD_EVENT_MAP = {
    "position_raw": EVENT_TYPE_POSITION_CHANGED,
    "department": EVENT_TYPE_DEPARTMENT_CHANGED,
    "org_unit_id": EVENT_TYPE_DEPARTMENT_CHANGED,
    "education_raw": EVENT_TYPE_EDUCATION_CHANGED,
    "certification_raw": EVENT_TYPE_CERTIFICATE_CHANGED,
}

NORMALIZED_KIND_EVENT_MAP = {
    "education": EVENT_TYPE_EDUCATION_CHANGED,
    "certificate": EVENT_TYPE_CERTIFICATE_CHANGED,
}


class SnapshotComparisonError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def hr_change_events_available(conn: Connection) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = 'hr_change_events'
            LIMIT 1
            """
        )
    ).first()
    return row is not None


def _serialize_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _display_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        text_val = str(value).strip()
        return text_val or None
    return str(value)


def _load_snapshot_meta(conn: Connection, snapshot_id: int) -> dict[str, Any]:
    row = conn.execute(
        text(
            """
            SELECT snapshot_id, source_batch_id, version, source_type, status,
                   entry_count, promoted_by, promoted_at
            FROM public.hr_canonical_snapshots
            WHERE snapshot_id = :snapshot_id
            """
        ),
        {"snapshot_id": snapshot_id},
    ).mappings().first()
    if not row:
        raise SnapshotComparisonError(f"snapshot_id={snapshot_id} not found")
    return dict(row)


def _load_snapshot_entries(conn: Connection, snapshot_id: int) -> list[dict[str, Any]]:
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


def _index_entries_by_match_key(entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for entry in entries:
        indexed[str(entry["match_key"])] = entry
    return indexed


def _roster_context(entry: dict[str, Any]) -> dict[str, Any]:
    payload = dict(entry.get("payload") or {})
    return {
        "employee_id": entry.get("employee_id"),
        "full_name": _display_text(payload.get("full_name")),
        "iin": _display_text(payload.get("iin") or entry.get("iin")),
        "department": _display_text(payload.get("department")),
        "org_unit_id": payload.get("org_unit_id"),
    }


def _roster_context_for_match_key(
    *,
    match_key: str,
    entry: Optional[dict[str, Any]],
    roster_index: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if entry is not None and str(entry.get("record_kind")) == RECORD_KIND_ROSTER:
        return _roster_context(entry)
    roster_key = match_key.split("|", 1)[0]
    roster_entry = roster_index.get(roster_key)
    if roster_entry is not None:
        ctx = _roster_context(roster_entry)
        if entry is not None:
            payload = dict(entry.get("payload") or {})
            ctx.setdefault("employee_id", entry.get("employee_id"))
            ctx.setdefault("full_name", _display_text(payload.get("full_name")))
            ctx.setdefault("iin", _display_text(entry.get("iin")))
        return ctx
    if entry is not None:
        return _roster_context(entry)
    return {
        "employee_id": None,
        "full_name": None,
        "iin": None,
        "department": None,
        "org_unit_id": None,
    }


def _build_event(
    *,
    prior_snapshot_id: int,
    new_snapshot_id: int,
    event_at: datetime,
    event_type: str,
    match_key: str,
    record_kind: str,
    prior_entry: Optional[dict[str, Any]],
    new_entry: Optional[dict[str, Any]],
    roster_index: dict[str, dict[str, Any]],
    field_name: Optional[str] = None,
    old_value: Any = None,
    new_value: Any = None,
    details: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    source_entry = new_entry or prior_entry
    ctx = _roster_context_for_match_key(
        match_key=match_key,
        entry=source_entry,
        roster_index=roster_index,
    )
    return {
        "prior_snapshot_id": prior_snapshot_id,
        "new_snapshot_id": new_snapshot_id,
        "event_type": event_type,
        "event_at": event_at,
        "employee_id": ctx.get("employee_id"),
        "match_key": match_key,
        "record_kind": record_kind,
        "prior_entry_id": int(prior_entry["entry_id"]) if prior_entry else None,
        "new_entry_id": int(new_entry["entry_id"]) if new_entry else None,
        "field_name": field_name,
        "old_value": _display_text(old_value),
        "new_value": _display_text(new_value),
        "department": ctx.get("department"),
        "org_unit_id": ctx.get("org_unit_id"),
        "full_name": ctx.get("full_name"),
        "iin": ctx.get("iin"),
        "details": details,
    }


def compare_snapshots(
    conn: Connection,
    *,
    prior_snapshot_id: int,
    new_snapshot_id: int,
) -> list[dict[str, Any]]:
    """Compare snapshot N vs snapshot N+1 and return derived change events (not persisted)."""
    prior_meta = _load_snapshot_meta(conn, prior_snapshot_id)
    new_meta = _load_snapshot_meta(conn, new_snapshot_id)
    if int(new_meta["version"]) <= int(prior_meta["version"]):
        raise SnapshotComparisonError(
            f"new snapshot version {new_meta['version']} must be greater than "
            f"prior snapshot version {prior_meta['version']}"
        )

    prior_entries = _load_snapshot_entries(conn, prior_snapshot_id)
    new_entries = _load_snapshot_entries(conn, new_snapshot_id)
    prior_by_key = _index_entries_by_match_key(prior_entries)
    new_by_key = _index_entries_by_match_key(new_entries)

    prior_roster = {
        key: entry for key, entry in prior_by_key.items() if entry["record_kind"] == RECORD_KIND_ROSTER
    }
    new_roster = {
        key: entry for key, entry in new_by_key.items() if entry["record_kind"] == RECORD_KIND_ROSTER
    }
    roster_index = dict(new_roster)
    roster_index.update(prior_roster)

    event_at = new_meta["promoted_at"]
    if not isinstance(event_at, datetime):
        event_at = datetime.fromisoformat(str(event_at))

    events: list[dict[str, Any]] = []

    for match_key, entry in new_roster.items():
        if match_key not in prior_roster:
            events.append(
                _build_event(
                    prior_snapshot_id=prior_snapshot_id,
                    new_snapshot_id=new_snapshot_id,
                    event_at=event_at,
                    event_type=EVENT_TYPE_NEW,
                    match_key=match_key,
                    record_kind=RECORD_KIND_ROSTER,
                    prior_entry=None,
                    new_entry=entry,
                    roster_index=roster_index,
                )
            )

    for match_key, entry in prior_roster.items():
        if match_key not in new_roster:
            events.append(
                _build_event(
                    prior_snapshot_id=prior_snapshot_id,
                    new_snapshot_id=new_snapshot_id,
                    event_at=event_at,
                    event_type=EVENT_TYPE_REMOVED,
                    match_key=match_key,
                    record_kind=RECORD_KIND_ROSTER,
                    prior_entry=entry,
                    new_entry=None,
                    roster_index=roster_index,
                )
            )

    for match_key in sorted(set(prior_roster.keys()) & set(new_roster.keys())):
        prior_entry = prior_roster[match_key]
        new_entry = new_roster[match_key]
        prior_payload = dict(prior_entry.get("payload") or {})
        new_payload = dict(new_entry.get("payload") or {})
        field_diffs = compute_field_diffs(
            canonical_payload=prior_payload,
            incoming_payload=new_payload,
            compare_fields=ROSTER_COMPARE_FIELDS,
        )
        emitted_department = False
        for field_name, diff in field_diffs.items():
            event_type = ROSTER_FIELD_EVENT_MAP.get(field_name)
            if event_type is None:
                continue
            if event_type == EVENT_TYPE_DEPARTMENT_CHANGED:
                if emitted_department:
                    continue
                emitted_department = True
                old_department = _display_text(prior_payload.get("department"))
                new_department = _display_text(new_payload.get("department"))
                old_org = prior_payload.get("org_unit_id")
                new_org = new_payload.get("org_unit_id")
                events.append(
                    _build_event(
                        prior_snapshot_id=prior_snapshot_id,
                        new_snapshot_id=new_snapshot_id,
                        event_at=event_at,
                        event_type=EVENT_TYPE_DEPARTMENT_CHANGED,
                        match_key=match_key,
                        record_kind=RECORD_KIND_ROSTER,
                        prior_entry=prior_entry,
                        new_entry=new_entry,
                        roster_index=roster_index,
                        field_name="department",
                        old_value=old_department or old_org,
                        new_value=new_department or new_org,
                        details={
                            "old_department": old_department,
                            "new_department": new_department,
                            "old_org_unit_id": old_org,
                            "new_org_unit_id": new_org,
                        },
                    )
                )
                continue
            events.append(
                _build_event(
                    prior_snapshot_id=prior_snapshot_id,
                    new_snapshot_id=new_snapshot_id,
                    event_at=event_at,
                    event_type=event_type,
                    match_key=match_key,
                    record_kind=RECORD_KIND_ROSTER,
                    prior_entry=prior_entry,
                    new_entry=new_entry,
                    roster_index=roster_index,
                    field_name=field_name,
                    old_value=diff.get("canonical"),
                    new_value=diff.get("incoming"),
                )
            )

    for record_kind, event_type in NORMALIZED_KIND_EVENT_MAP.items():
        prior_norm = {
            key: entry for key, entry in prior_by_key.items() if entry["record_kind"] == record_kind
        }
        new_norm = {
            key: entry for key, entry in new_by_key.items() if entry["record_kind"] == record_kind
        }
        for match_key in sorted(set(prior_norm.keys()) | set(new_norm.keys())):
            prior_entry = prior_norm.get(match_key)
            new_entry = new_norm.get(match_key)
            if prior_entry is None and new_entry is not None:
                payload = dict(new_entry.get("payload") or {})
                events.append(
                    _build_event(
                        prior_snapshot_id=prior_snapshot_id,
                        new_snapshot_id=new_snapshot_id,
                        event_at=event_at,
                        event_type=event_type,
                        match_key=match_key,
                        record_kind=record_kind,
                        prior_entry=None,
                        new_entry=new_entry,
                        roster_index=roster_index,
                        field_name="title",
                        old_value=None,
                        new_value=payload.get("title"),
                        details={"change": "added"},
                    )
                )
                continue
            if prior_entry is not None and new_entry is None:
                payload = dict(prior_entry.get("payload") or {})
                events.append(
                    _build_event(
                        prior_snapshot_id=prior_snapshot_id,
                        new_snapshot_id=new_snapshot_id,
                        event_at=event_at,
                        event_type=event_type,
                        match_key=match_key,
                        record_kind=record_kind,
                        prior_entry=prior_entry,
                        new_entry=None,
                        roster_index=roster_index,
                        field_name="title",
                        old_value=payload.get("title"),
                        new_value=None,
                        details={"change": "removed"},
                    )
                )
                continue
            if prior_entry is None or new_entry is None:
                continue
            if str(prior_entry.get("canonical_hash")) == str(new_entry.get("canonical_hash")):
                continue
            prior_payload = dict(prior_entry.get("payload") or {})
            new_payload = dict(new_entry.get("payload") or {})
            field_diffs = compute_field_diffs(
                canonical_payload=prior_payload,
                incoming_payload=new_payload,
                compare_fields=NORMALIZED_COMPARE_FIELDS,
            )
            if not field_diffs:
                continue
            primary_field = sorted(field_diffs.keys())[0]
            diff = field_diffs[primary_field]
            events.append(
                _build_event(
                    prior_snapshot_id=prior_snapshot_id,
                    new_snapshot_id=new_snapshot_id,
                    event_at=event_at,
                    event_type=event_type,
                    match_key=match_key,
                    record_kind=record_kind,
                    prior_entry=prior_entry,
                    new_entry=new_entry,
                    roster_index=roster_index,
                    field_name=primary_field,
                    old_value=diff.get("canonical"),
                    new_value=diff.get("incoming"),
                    details={"field_diffs": field_diffs},
                )
            )

    return events


def _delete_events_for_snapshot_pair(
    conn: Connection,
    *,
    prior_snapshot_id: int,
    new_snapshot_id: int,
) -> None:
    conn.execute(
        text(
            """
            DELETE FROM public.hr_change_events
            WHERE prior_snapshot_id = :prior_snapshot_id
              AND new_snapshot_id = :new_snapshot_id
            """
        ),
        {
            "prior_snapshot_id": prior_snapshot_id,
            "new_snapshot_id": new_snapshot_id,
        },
    )


def materialize_snapshot_change_events(
    conn: Connection,
    *,
    prior_snapshot_id: int,
    new_snapshot_id: int,
) -> dict[str, Any]:
    if not hr_change_events_available(conn):
        raise SnapshotComparisonError("hr_change_events is not available")

    events = compare_snapshots(
        conn,
        prior_snapshot_id=prior_snapshot_id,
        new_snapshot_id=new_snapshot_id,
    )
    _delete_events_for_snapshot_pair(
        conn,
        prior_snapshot_id=prior_snapshot_id,
        new_snapshot_id=new_snapshot_id,
    )

    for event in events:
        conn.execute(
            text(
                """
                INSERT INTO public.hr_change_events (
                    prior_snapshot_id,
                    new_snapshot_id,
                    event_type,
                    event_at,
                    employee_id,
                    match_key,
                    record_kind,
                    prior_entry_id,
                    new_entry_id,
                    field_name,
                    old_value,
                    new_value,
                    department,
                    org_unit_id,
                    full_name,
                    iin,
                    details
                )
                VALUES (
                    :prior_snapshot_id,
                    :new_snapshot_id,
                    :event_type,
                    :event_at,
                    :employee_id,
                    :match_key,
                    :record_kind,
                    :prior_entry_id,
                    :new_entry_id,
                    :field_name,
                    :old_value,
                    :new_value,
                    :department,
                    :org_unit_id,
                    :full_name,
                    :iin,
                    CAST(:details AS JSONB)
                )
                """
            ),
            {
                **event,
                "details": _serialize_json(event.get("details")) if event.get("details") is not None else None,
            },
        )

    summary = dict(Counter(event["event_type"] for event in events))
    return {
        "prior_snapshot_id": prior_snapshot_id,
        "new_snapshot_id": new_snapshot_id,
        "event_count": len(events),
        "summary": summary,
    }


def maybe_materialize_change_events_after_snapshot(
    conn: Connection,
    snapshot_result: dict[str, Any],
) -> Optional[dict[str, Any]]:
    if not hr_change_events_available(conn):
        return None
    if not snapshot_result.get("created"):
        return None
    prior_snapshot_id = snapshot_result.get("superseded_snapshot_id")
    new_snapshot_id = snapshot_result.get("snapshot_id")
    if prior_snapshot_id is None or new_snapshot_id is None:
        return None
    try:
        return materialize_snapshot_change_events(
            conn,
            prior_snapshot_id=int(prior_snapshot_id),
            new_snapshot_id=int(new_snapshot_id),
        )
    except Exception:
        logger.exception(
            "failed to materialize hr change events prior=%s new=%s",
            prior_snapshot_id,
            new_snapshot_id,
        )
        return None


def _serialize_change_event(row: dict[str, Any]) -> dict[str, Any]:
    details = row.get("details")
    if isinstance(details, str):
        details = json.loads(details)
    event_at = row.get("event_at")
    if isinstance(event_at, datetime):
        event_at = event_at.isoformat()
    return {
        "change_event_id": int(row["change_event_id"]),
        "prior_snapshot_id": int(row["prior_snapshot_id"]),
        "new_snapshot_id": int(row["new_snapshot_id"]),
        "event_type": row["event_type"],
        "event_at": event_at,
        "employee_id": int(row["employee_id"]) if row.get("employee_id") is not None else None,
        "match_key": row["match_key"],
        "record_kind": row["record_kind"],
        "prior_entry_id": int(row["prior_entry_id"]) if row.get("prior_entry_id") is not None else None,
        "new_entry_id": int(row["new_entry_id"]) if row.get("new_entry_id") is not None else None,
        "field_name": row.get("field_name"),
        "old_value": row.get("old_value"),
        "new_value": row.get("new_value"),
        "department": row.get("department"),
        "org_unit_id": int(row["org_unit_id"]) if row.get("org_unit_id") is not None else None,
        "full_name": row.get("full_name"),
        "iin": row.get("iin"),
        "details": details,
    }


def list_hr_change_events(
    conn: Connection,
    *,
    employee_id: Optional[int] = None,
    department: Optional[str] = None,
    org_unit_id: Optional[int] = None,
    event_type: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    prior_snapshot_id: Optional[int] = None,
    new_snapshot_id: Optional[int] = None,
    source_batch_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    if not hr_change_events_available(conn):
        raise SnapshotComparisonError("hr_change_events is not available")

    if event_type is not None:
        normalized_type = event_type.strip().upper()
        if normalized_type not in EVENT_TYPES:
            raise HTTPException(status_code=422, detail="Invalid event_type filter.")
        event_type = normalized_type

    where_parts = ["TRUE"]
    params: dict[str, Any] = {
        "limit": int(limit),
        "offset": int(offset),
    }

    if employee_id is not None:
        where_parts.append("e.employee_id = :employee_id")
        params["employee_id"] = int(employee_id)
    if org_unit_id is not None:
        where_parts.append("e.org_unit_id = :org_unit_id")
        params["org_unit_id"] = int(org_unit_id)
    if department is not None:
        where_parts.append("LOWER(TRIM(e.department)) = LOWER(TRIM(:department))")
        params["department"] = department.strip()
    if event_type is not None:
        where_parts.append("e.event_type = :event_type")
        params["event_type"] = event_type
    if date_from is not None:
        where_parts.append("e.event_at::date >= :date_from")
        params["date_from"] = date_from
    if date_to is not None:
        where_parts.append("e.event_at::date <= :date_to")
        params["date_to"] = date_to
    if prior_snapshot_id is not None:
        where_parts.append("e.prior_snapshot_id = :prior_snapshot_id")
        params["prior_snapshot_id"] = int(prior_snapshot_id)
    if new_snapshot_id is not None:
        where_parts.append("e.new_snapshot_id = :new_snapshot_id")
        params["new_snapshot_id"] = int(new_snapshot_id)
    if source_batch_id is not None:
        where_parts.append(
            """
            EXISTS (
                SELECT 1
                FROM public.hr_canonical_snapshots AS s
                WHERE s.snapshot_id = e.new_snapshot_id
                  AND s.source_batch_id = :source_batch_id
            )
            """
        )
        params["source_batch_id"] = int(source_batch_id)

    where_sql = " AND ".join(where_parts)
    total = conn.execute(
        text(
            f"""
            SELECT COUNT(*) AS cnt
            FROM public.hr_change_events e
            WHERE {where_sql}
            """
        ),
        params,
    ).scalar_one()

    rows = conn.execute(
        text(
            f"""
            SELECT
                e.change_event_id,
                e.prior_snapshot_id,
                e.new_snapshot_id,
                e.event_type,
                e.event_at,
                e.employee_id,
                e.match_key,
                e.record_kind,
                e.prior_entry_id,
                e.new_entry_id,
                e.field_name,
                e.old_value,
                e.new_value,
                e.department,
                e.org_unit_id,
                e.full_name,
                e.iin,
                e.details
            FROM public.hr_change_events e
            WHERE {where_sql}
            ORDER BY e.event_at DESC, e.change_event_id DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()

    return {
        "items": [_serialize_change_event(dict(row)) for row in rows],
        "total": int(total),
        "limit": int(limit),
        "offset": int(offset),
    }
