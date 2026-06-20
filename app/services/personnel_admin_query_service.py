"""ADR-043 Phase C4.1 — read-only queries for personnel admin API."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.engine import engine

_VALID_EVENT_SORT = frozenset({"detected_at", "personnel_event_id", "event_type", "status"})
_VALID_OVERRIDE_SORT = frozenset({"created_at", "override_id", "status", "tier"})
_VALID_RUN_SORT = frozenset({"started_at", "run_id", "status"})


def _table_exists(conn: Connection, table: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = :table
            LIMIT 1
            """
        ),
        {"table": table},
    ).first()
    return row is not None


def _serialize_dt(value: Any) -> Optional[str]:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value) if value is not None else None


def _parse_json_field(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _serialize_lifecycle_run(row: dict[str, Any], *, include_summary: bool = False) -> dict[str, Any]:
    out = {
        "run_id": int(row["run_id"]),
        "previous_snapshot_id": int(row["previous_snapshot_id"]),
        "snapshot_id": int(row["snapshot_id"]),
        "status": str(row["status"]),
        "started_at": _serialize_dt(row.get("started_at")),
        "completed_at": _serialize_dt(row.get("completed_at")),
        "actor_user_id": int(row["actor_user_id"]) if row.get("actor_user_id") is not None else None,
        "dry_run": bool(row["dry_run"]),
        "refresh_cache": bool(row["refresh_cache"]),
        "enqueue": bool(row["enqueue"]),
        "sync_persons": bool(row["sync_persons"]),
        "effective_entries_processed": int(row.get("effective_entries_processed") or 0),
        "events_created": int(row.get("events_created") or 0),
        "events_existing": int(row.get("events_existing") or 0),
        "enrollment_created": int(row.get("enrollment_created") or 0),
        "enrollment_existing": int(row.get("enrollment_existing") or 0),
        "persons_created": int(row.get("persons_created") or 0),
        "persons_updated": int(row.get("persons_updated") or 0),
        "assignments_created": int(row.get("assignments_created") or 0),
        "assignments_updated": int(row.get("assignments_updated") or 0),
        "assignments_closed": int(row.get("assignments_closed") or 0),
        "warnings_count": int(row.get("warnings_count") or 0),
        "errors_count": int(row.get("errors_count") or 0),
    }
    if include_summary:
        summary = _parse_json_field(row.get("summary"))
        out["summary"] = summary if isinstance(summary, dict) else {}
    return out


def _serialize_personnel_event(row: dict[str, Any], *, detail: bool = False) -> dict[str, Any]:
    out = {
        "personnel_event_id": int(row["personnel_event_id"]),
        "previous_snapshot_id": int(row["previous_snapshot_id"]),
        "snapshot_id": int(row["snapshot_id"]),
        "person_key": str(row["person_key"]),
        "assignment_key": row.get("assignment_key"),
        "event_type": str(row["event_type"]),
        "status": str(row["status"]),
        "field_path": row.get("field_path"),
        "person_id": int(row["person_id"]) if row.get("person_id") is not None else None,
        "assignment_id": int(row["assignment_id"]) if row.get("assignment_id") is not None else None,
        "detected_at": _serialize_dt(row.get("detected_at")),
        "resolved_at": _serialize_dt(row.get("resolved_at")),
    }
    if detail:
        metadata = _parse_json_field(row.get("metadata"))
        out.update(
            {
                "source_event_id": int(row["source_event_id"])
                if row.get("source_event_id") is not None
                else None,
                "old_value": _parse_json_field(row.get("old_value")),
                "new_value": _parse_json_field(row.get("new_value")),
                "effective_old_value": _parse_json_field(row.get("effective_old_value")),
                "effective_new_value": _parse_json_field(row.get("effective_new_value")),
                "resolved_by_user_id": int(row["resolved_by_user_id"])
                if row.get("resolved_by_user_id") is not None
                else None,
                "metadata": metadata if isinstance(metadata, dict) else {},
            }
        )
    return out


def _serialize_override(row: dict[str, Any], *, detail: bool = False) -> dict[str, Any]:
    out = {
        "override_id": int(row["override_id"]),
        "scope_type": str(row["scope_type"]),
        "scope_key": str(row["scope_key"]),
        "field_path": str(row["field_path"]),
        "status": str(row["status"]),
        "tier": int(row["tier"]),
        "owner_domain": str(row["owner_domain"]),
        "person_key": row.get("person_key"),
        "assignment_key": row.get("assignment_key"),
        "stale_flag": bool(row.get("stale_flag")),
        "created_at": _serialize_dt(row.get("created_at")),
        "updated_at": _serialize_dt(row.get("updated_at")),
    }
    if detail:
        metadata = _parse_json_field(row.get("metadata"))
        out.update(
            {
                "person_id": int(row["person_id"]) if row.get("person_id") is not None else None,
                "assignment_id": int(row["assignment_id"])
                if row.get("assignment_id") is not None
                else None,
                "canonical_value": _parse_json_field(row.get("canonical_value")),
                "override_value": _parse_json_field(row.get("override_value")),
                "justification": row.get("justification"),
                "evidence_url": row.get("evidence_url"),
                "created_by_user_id": int(row["created_by_user_id"])
                if row.get("created_by_user_id") is not None
                else None,
                "approved_by_user_id": int(row["approved_by_user_id"])
                if row.get("approved_by_user_id") is not None
                else None,
                "approved_at": _serialize_dt(row.get("approved_at")),
                "supersedes_override_id": int(row["supersedes_override_id"])
                if row.get("supersedes_override_id") is not None
                else None,
                "superseded_by_override_id": int(row["superseded_by_override_id"])
                if row.get("superseded_by_override_id") is not None
                else None,
                "metadata": metadata if isinstance(metadata, dict) else {},
            }
        )
    return out


def list_lifecycle_runs(
    *,
    previous_snapshot_id: Optional[int] = None,
    snapshot_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    sort_by: str = "started_at",
    sort_dir: str = "desc",
) -> dict[str, Any]:
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))
    sort_col = sort_by if sort_by in _VALID_RUN_SORT else "started_at"
    direction = "DESC" if str(sort_dir).lower() != "asc" else "ASC"

    with engine.connect() as conn:
        if not _table_exists(conn, "hr_personnel_lifecycle_runs"):
            return {"items": [], "total": 0, "limit": limit, "offset": offset}

        filters = ["1=1"]
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if previous_snapshot_id is not None:
            filters.append("previous_snapshot_id = :previous_snapshot_id")
            params["previous_snapshot_id"] = int(previous_snapshot_id)
        if snapshot_id is not None:
            filters.append("snapshot_id = :snapshot_id")
            params["snapshot_id"] = int(snapshot_id)
        if status:
            filters.append("status = :status")
            params["status"] = status.strip().lower()

        where_sql = " AND ".join(filters)
        total = int(
            conn.execute(
                text(f"SELECT COUNT(*) FROM public.hr_personnel_lifecycle_runs WHERE {where_sql}"),
                params,
            ).scalar_one()
        )
        rows = conn.execute(
            text(
                f"""
                SELECT *
                FROM public.hr_personnel_lifecycle_runs
                WHERE {where_sql}
                ORDER BY {sort_col} {direction}, run_id DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        ).mappings().all()

    return {
        "items": [_serialize_lifecycle_run(dict(row)) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_lifecycle_run(run_id: int) -> dict[str, Any]:
    with engine.connect() as conn:
        if not _table_exists(conn, "hr_personnel_lifecycle_runs"):
            raise ValueError(f"Lifecycle run not found: {run_id}")
        row = conn.execute(
            text(
                """
                SELECT *
                FROM public.hr_personnel_lifecycle_runs
                WHERE run_id = :run_id
                LIMIT 1
                """
            ),
            {"run_id": int(run_id)},
        ).mappings().first()
        if not row:
            raise ValueError(f"Lifecycle run not found: {run_id}")
        return _serialize_lifecycle_run(dict(row), include_summary=True)


def list_personnel_events(
    *,
    snapshot_id: Optional[int] = None,
    event_type: Optional[str] = None,
    status: Optional[str] = None,
    person_key: Optional[str] = None,
    assignment_key: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
    sort_by: str = "detected_at",
    sort_dir: str = "desc",
) -> dict[str, Any]:
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))
    sort_col = sort_by if sort_by in _VALID_EVENT_SORT else "detected_at"
    direction = "DESC" if str(sort_dir).lower() != "asc" else "ASC"

    with engine.connect() as conn:
        if not _table_exists(conn, "hr_personnel_change_events"):
            return {"items": [], "total": 0, "limit": limit, "offset": offset}

        filters = ["1=1"]
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if snapshot_id is not None:
            filters.append("snapshot_id = :snapshot_id")
            params["snapshot_id"] = int(snapshot_id)
        if event_type:
            filters.append("event_type = :event_type")
            params["event_type"] = event_type.strip().upper()
        if status:
            filters.append("status = :status")
            params["status"] = status.strip().lower()
        if person_key:
            filters.append("person_key = :person_key")
            params["person_key"] = person_key.strip()
        if assignment_key:
            filters.append("lower(assignment_key) = lower(:assignment_key)")
            params["assignment_key"] = assignment_key.strip()
        if date_from is not None:
            filters.append("detected_at >= :date_from")
            params["date_from"] = date_from
        if date_to is not None:
            filters.append("detected_at <= :date_to")
            params["date_to"] = date_to

        where_sql = " AND ".join(filters)
        total = int(
            conn.execute(
                text(f"SELECT COUNT(*) FROM public.hr_personnel_change_events WHERE {where_sql}"),
                params,
            ).scalar_one()
        )
        rows = conn.execute(
            text(
                f"""
                SELECT
                    personnel_event_id,
                    previous_snapshot_id,
                    snapshot_id,
                    person_key,
                    assignment_key,
                    event_type,
                    status,
                    field_path,
                    person_id,
                    assignment_id,
                    detected_at,
                    resolved_at
                FROM public.hr_personnel_change_events
                WHERE {where_sql}
                ORDER BY {sort_col} {direction}, personnel_event_id DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        ).mappings().all()

    return {
        "items": [_serialize_personnel_event(dict(row)) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_personnel_event(event_id: int) -> dict[str, Any]:
    with engine.connect() as conn:
        if not _table_exists(conn, "hr_personnel_change_events"):
            raise ValueError(f"Personnel event not found: {event_id}")
        row = conn.execute(
            text(
                """
                SELECT *
                FROM public.hr_personnel_change_events
                WHERE personnel_event_id = :event_id
                LIMIT 1
                """
            ),
            {"event_id": int(event_id)},
        ).mappings().first()
        if not row:
            raise ValueError(f"Personnel event not found: {event_id}")
        return _serialize_personnel_event(dict(row), detail=True)


def list_overrides(
    *,
    status: Optional[str] = None,
    scope_type: Optional[str] = None,
    person_key: Optional[str] = None,
    assignment_key: Optional[str] = None,
    field_path: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
) -> dict[str, Any]:
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))
    sort_col = sort_by if sort_by in _VALID_OVERRIDE_SORT else "created_at"
    direction = "DESC" if str(sort_dir).lower() != "asc" else "ASC"

    with engine.connect() as conn:
        if not _table_exists(conn, "hr_review_overrides"):
            return {"items": [], "total": 0, "limit": limit, "offset": offset}

        filters = ["1=1"]
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            filters.append("status = :status")
            params["status"] = status.strip().lower()
        if scope_type:
            filters.append("scope_type = :scope_type")
            params["scope_type"] = scope_type.strip().upper()
        if person_key:
            filters.append("person_key = :person_key")
            params["person_key"] = person_key.strip()
        if assignment_key:
            filters.append("lower(assignment_key) = lower(:assignment_key)")
            params["assignment_key"] = assignment_key.strip()
        if field_path:
            filters.append("field_path = :field_path")
            params["field_path"] = field_path.strip()

        where_sql = " AND ".join(filters)
        total = int(
            conn.execute(
                text(f"SELECT COUNT(*) FROM public.hr_review_overrides WHERE {where_sql}"),
                params,
            ).scalar_one()
        )
        rows = conn.execute(
            text(
                f"""
                SELECT
                    override_id,
                    scope_type,
                    scope_key,
                    field_path,
                    status,
                    tier,
                    owner_domain,
                    person_key,
                    assignment_key,
                    stale_flag,
                    created_at,
                    updated_at
                FROM public.hr_review_overrides
                WHERE {where_sql}
                ORDER BY {sort_col} {direction}, override_id DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        ).mappings().all()

    return {
        "items": [_serialize_override(dict(row)) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_override(override_id: int) -> dict[str, Any]:
    with engine.connect() as conn:
        if not _table_exists(conn, "hr_review_overrides"):
            raise ValueError(f"Override not found: {override_id}")
        row = conn.execute(
            text(
                """
                SELECT *
                FROM public.hr_review_overrides
                WHERE override_id = :override_id
                LIMIT 1
                """
            ),
            {"override_id": int(override_id)},
        ).mappings().first()
        if not row:
            raise ValueError(f"Override not found: {override_id}")
        return _serialize_override(dict(row), detail=True)


def get_override_tier(override_id: int) -> int:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT tier
                FROM public.hr_review_overrides
                WHERE override_id = :override_id
                LIMIT 1
                """
            ),
            {"override_id": int(override_id)},
        ).mappings().first()
        if not row:
            raise ValueError(f"Override not found: {override_id}")
        return int(row["tier"])
