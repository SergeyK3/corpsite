"""ADR-043 Phase C2 — apply hr_personnel_change_events to persons / assignments."""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.engine import engine
from app.services.department_recoding_service import lookup_recoding
from app.services.hr_effective_monthly_diff_service import (
    ASSIGNMENT_COMPARE_FIELDS,
    EVENT_CLOSED_ASSIGNMENT,
    EVENT_DEPARTMENT_CHANGED,
    EVENT_FIELD_CHANGED,
    EVENT_NEW_ASSIGNMENT,
    EVENT_NEW_PERSON,
    EVENT_OVERRIDE_APPLIED,
    EVENT_OVERRIDE_EXPIRED,
    EVENT_POSITION_CHANGED,
    EVENT_RATE_CHANGED,
    EVENT_TERMINATED_PERSON,
    EVENT_TRANSFER,
    IDENTITY_COMPARE_FIELDS,
    NON_ACTIONABLE_FIELD_PREFIXES,
    PERSONNEL_EVENT_TYPES,
    compute_assignment_key,
    personnel_events_available,
)
from app.services.hr_import_roster_promotion_service import _get_or_create_position_id

logger = logging.getLogger(__name__)

STATUS_DETECTED = "detected"
STATUS_ACKNOWLEDGED = "acknowledged"
STATUS_ENROLLED = "enrolled"

PERSON_FIELD_PATHS = frozenset(
    f"identity.{name}" for name in IDENTITY_COMPARE_FIELDS
)
ASSIGNMENT_FIELD_PATHS = frozenset(
    {
        "roster.department",
        "roster.org_unit_id",
        "roster.position_raw",
        "roster.rate",
    }
)
MUTATING_EVENT_TYPES = frozenset(
    {
        EVENT_NEW_PERSON,
        EVENT_TERMINATED_PERSON,
        EVENT_NEW_ASSIGNMENT,
        EVENT_CLOSED_ASSIGNMENT,
        EVENT_TRANSFER,
        EVENT_DEPARTMENT_CHANGED,
        EVENT_POSITION_CHANGED,
        EVENT_RATE_CHANGED,
        EVENT_FIELD_CHANGED,
    }
)
NON_MUTATING_EVENT_TYPES = frozenset({EVENT_OVERRIDE_APPLIED, EVENT_OVERRIDE_EXPIRED})


class PersonAssignmentSyncError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


@dataclass
class PersonAssignmentSyncReport:
    events_seen: int = 0
    events_applied: int = 0
    events_skipped: int = 0
    persons_created: int = 0
    persons_updated: int = 0
    assignments_created: int = 0
    assignments_updated: int = 0
    assignments_closed: int = 0
    links_created: int = 0
    links_updated: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    dry_run: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_json(value: Any) -> Any:
    if isinstance(value, str):
        text_val = value.strip()
        if not text_val:
            return None
        try:
            return json.loads(text_val)
        except json.JSONDecodeError:
            return value
    return value


def _serialize_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str, sort_keys=True)


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


def _fallback_org_unit_id(conn: Connection) -> Optional[int]:
    row = conn.execute(
        text(
            """
            SELECT unit_id
            FROM public.org_units
            WHERE is_active = TRUE
            ORDER BY unit_id
            LIMIT 1
            """
        )
    ).mappings().first()
    return int(row["unit_id"]) if row else None


def _resolve_org_unit_id(conn: Connection, payload: dict[str, Any]) -> Optional[int]:
    raw = payload.get("org_unit_id")
    if raw is not None and str(raw).strip():
        return int(raw)
    department = str(payload.get("department") or "").strip()
    if department:
        rec = lookup_recoding(conn, department)
        if rec and rec.get("org_unit_id"):
            return int(rec["org_unit_id"])
    return _fallback_org_unit_id(conn)


def _resolve_position_id(conn: Connection, payload: dict[str, Any]) -> int:
    raw = payload.get("position_id")
    if raw is not None and str(raw).strip():
        return int(raw)
    position_raw = str(payload.get("position_raw") or "").strip() or "Unknown"
    return _get_or_create_position_id(conn, position_raw)


def _parse_rate(value: Any, *, default: float = 1.0) -> float:
    if value is None:
        return default
    try:
        rate = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.01, min(rate, 1.5))


def _parse_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    text_val = str(value).strip()
    if not text_val:
        return None
    return date.fromisoformat(text_val[:10])


def _resolve_actor_user_id(conn: Connection, actor_user_id: Optional[int]) -> int:
    if actor_user_id is not None:
        return int(actor_user_id)
    row = conn.execute(
        text(
            """
            SELECT user_id
            FROM public.users
            WHERE is_active = TRUE
            ORDER BY user_id
            LIMIT 1
            """
        )
    ).mappings().first()
    if not row:
        raise PersonAssignmentSyncError("No active user available for sync audit metadata")
    return int(row["user_id"])


def _find_person(
    conn: Connection,
    *,
    person_key: str,
    iin: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    row = conn.execute(
        text(
            """
            SELECT person_id, match_key, person_status, iin, full_name
            FROM public.persons
            WHERE match_key = :match_key
              AND person_status IN ('active', 'inactive')
            LIMIT 1
            """
        ),
        {"match_key": person_key},
    ).mappings().first()
    if row:
        return dict(row)

    if iin and len(str(iin)) == 12:
        row = conn.execute(
            text(
                """
                SELECT person_id, match_key, person_status, iin, full_name
                FROM public.persons
                WHERE iin = :iin
                  AND person_status = 'active'
                LIMIT 1
                """
            ),
            {"iin": str(iin)},
        ).mappings().first()
        if row:
            return dict(row)
    return None


def _find_assignment(
    conn: Connection,
    *,
    person_id: Optional[int],
    assignment_key: Optional[str],
    assignment_id: Optional[int] = None,
    canonical_entry_id: Optional[int] = None,
    active_only: bool = False,
) -> Optional[dict[str, Any]]:
    if assignment_id is not None:
        row = conn.execute(
            text(
                """
                SELECT *
                FROM public.person_assignments
                WHERE assignment_id = :assignment_id
                LIMIT 1
                """
            ),
            {"assignment_id": int(assignment_id)},
        ).mappings().first()
        return dict(row) if row else None

    if canonical_entry_id is not None:
        row = conn.execute(
            text(
                """
                SELECT *
                FROM public.person_assignments
                WHERE canonical_entry_id = :entry_id
                LIMIT 1
                """
            ),
            {"entry_id": int(canonical_entry_id)},
        ).mappings().first()
        if row:
            return dict(row)

    if person_id is not None and assignment_key:
        sql = """
            SELECT *
            FROM public.person_assignments
            WHERE person_id = :person_id
              AND lower(assignment_key) = lower(:assignment_key)
        """
        if active_only:
            sql += " AND lifecycle_status = 'active'"
        sql += " ORDER BY assignment_id DESC LIMIT 1"
        row = conn.execute(
            text(sql),
            {"person_id": int(person_id), "assignment_key": assignment_key},
        ).mappings().first()
        if row:
            return dict(row)

    return None


def _find_active_assignments_for_person(conn: Connection, person_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT *
            FROM public.person_assignments
            WHERE person_id = :person_id
              AND lifecycle_status = 'active'
            ORDER BY assignment_id
            """
        ),
        {"person_id": int(person_id)},
    ).mappings().all()
    return [dict(row) for row in rows]


def _find_employee_for_person(conn: Connection, person_id: int) -> Optional[int]:
    row = conn.execute(
        text(
            """
            SELECT employee_id
            FROM public.employees
            WHERE person_id = :person_id
            ORDER BY employee_id
            LIMIT 1
            """
        ),
        {"person_id": int(person_id)},
    ).mappings().first()
    return int(row["employee_id"]) if row else None


def _load_effective_payload(
    conn: Connection,
    *,
    snapshot_id: int,
    person_key: str,
) -> dict[str, Any]:
    if not _table_exists(conn, "hr_snapshot_effective_entries"):
        return {}
    row = conn.execute(
        text(
            """
            SELECT effective_payload
            FROM public.hr_snapshot_effective_entries
            WHERE snapshot_id = :snapshot_id
              AND match_key = :match_key
            LIMIT 1
            """
        ),
        {"snapshot_id": int(snapshot_id), "match_key": person_key},
    ).mappings().first()
    if not row:
        return {}
    payload = _parse_json(row["effective_payload"])
    return payload if isinstance(payload, dict) else {}


def _event_metadata(event: dict[str, Any]) -> dict[str, Any]:
    metadata = _parse_json(event.get("metadata"))
    return metadata if isinstance(metadata, dict) else {}


def _event_payload_value(event: dict[str, Any], *, prefer_new: bool = True) -> dict[str, Any]:
    key = "effective_new_value" if prefer_new else "effective_old_value"
    value = _parse_json(event.get(key))
    if isinstance(value, dict):
        return value
    if value is not None:
        return {"value": value}
    return {}


def _scalar_from_effective(payload: dict[str, Any], field_name: str) -> Any:
    if field_name in payload:
        return payload[field_name]
    return payload.get("value")


def _merge_payloads(*payloads: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for payload in payloads:
        merged.update({k: v for k, v in payload.items() if v is not None})
    return merged


def _is_whitelisted_field_change(field_path: Optional[str]) -> bool:
    if not field_path:
        return False
    if field_path.startswith(NON_ACTIONABLE_FIELD_PREFIXES):
        return False
    return field_path in PERSON_FIELD_PATHS or field_path in ASSIGNMENT_FIELD_PATHS


def _assignment_key_from_event(event: dict[str, Any], payload: dict[str, Any]) -> str:
    if event.get("assignment_key"):
        return str(event["assignment_key"])
    return compute_assignment_key(str(event["person_key"]), payload)


def _load_pending_events(
    conn: Connection,
    *,
    event_ids: Optional[list[int]] = None,
    snapshot_id: Optional[int] = None,
    event_types: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    if not personnel_events_available(conn):
        raise PersonAssignmentSyncError("hr_personnel_change_events is not available")

    filters = ["status = :status"]
    params: dict[str, Any] = {"status": STATUS_DETECTED}

    if event_ids:
        filters.append("personnel_event_id = ANY(:event_ids)")
        params["event_ids"] = [int(eid) for eid in event_ids]
    if snapshot_id is not None:
        filters.append("snapshot_id = :snapshot_id")
        params["snapshot_id"] = int(snapshot_id)
    if event_types:
        normalized = [et.strip().upper() for et in event_types if et and et.strip()]
        unknown = sorted(set(normalized) - PERSONNEL_EVENT_TYPES)
        if unknown:
            raise PersonAssignmentSyncError(f"Unknown event types: {', '.join(unknown)}")
        filters.append("event_type = ANY(:event_types)")
        params["event_types"] = normalized

    where_sql = " AND ".join(filters)
    rows = conn.execute(
        text(
            f"""
            SELECT *
            FROM public.hr_personnel_change_events
            WHERE {where_sql}
            ORDER BY personnel_event_id ASC
            """
        ),
        params,
    ).mappings().all()
    return [dict(row) for row in rows]


def _mark_event_applied(
    conn: Connection,
    *,
    event: dict[str, Any],
    status: str,
    actor_user_id: int,
    sync_meta: dict[str, Any],
    dry_run: bool,
) -> None:
    if dry_run:
        return
    metadata = _event_metadata(event)
    metadata["sync"] = {
        **metadata.get("sync", {}),
        **sync_meta,
        "applied_at": datetime.now(timezone.utc).isoformat(),
    }
    conn.execute(
        text(
            """
            UPDATE public.hr_personnel_change_events
            SET
                status = :status,
                resolved_at = now(),
                resolved_by_user_id = :actor_user_id,
                person_id = COALESCE(:person_id, person_id),
                assignment_id = COALESCE(:assignment_id, assignment_id),
                metadata = CAST(:metadata AS jsonb),
                detected_at = detected_at
            WHERE personnel_event_id = :event_id
            """
        ),
        {
            "event_id": int(event["personnel_event_id"]),
            "status": status,
            "actor_user_id": int(actor_user_id),
            "person_id": sync_meta.get("person_id"),
            "assignment_id": sync_meta.get("assignment_id"),
            "metadata": _serialize_json(metadata),
        },
    )


def _mark_event_failed(
    conn: Connection,
    *,
    event: dict[str, Any],
    error: str,
    dry_run: bool,
) -> None:
    if dry_run:
        return
    metadata = _event_metadata(event)
    metadata["sync"] = {
        **metadata.get("sync", {}),
        "last_error": error,
        "failed_at": datetime.now(timezone.utc).isoformat(),
    }
    conn.execute(
        text(
            """
            UPDATE public.hr_personnel_change_events
            SET metadata = CAST(:metadata AS jsonb)
            WHERE personnel_event_id = :event_id
            """
        ),
        {
            "event_id": int(event["personnel_event_id"]),
            "metadata": _serialize_json(metadata),
        },
    )


def _create_person(
    conn: Connection,
    *,
    person_key: str,
    payload: dict[str, Any],
    snapshot_id: Optional[int],
    canonical_entry_id: Optional[int],
    personnel_event_id: int,
    dry_run: bool,
) -> Optional[int]:
    existing = _find_person(conn, person_key=person_key, iin=payload.get("iin"))
    if existing:
        return int(existing["person_id"])

    full_name = str(payload.get("full_name") or person_key).strip() or person_key
    iin = payload.get("iin")
    if iin is not None:
        iin = str(iin).strip() or None
        if iin and len(iin) != 12:
            iin = None

    if dry_run:
        return -1

    row = conn.execute(
        text(
            """
            INSERT INTO public.persons (
                iin,
                full_name,
                birth_date,
                match_key,
                person_status,
                source,
                canonical_snapshot_id,
                canonical_entry_id
            )
            VALUES (
                :iin,
                :full_name,
                :birth_date,
                :match_key,
                'active',
                'canonical',
                :snapshot_id,
                :canonical_entry_id
            )
            RETURNING person_id
            """
        ),
        {
            "iin": iin,
            "full_name": full_name,
            "birth_date": _parse_date(payload.get("birth_date")),
            "match_key": person_key,
            "snapshot_id": snapshot_id,
            "canonical_entry_id": canonical_entry_id,
        },
    ).mappings().one()
    person_id = int(row["person_id"])
    logger.info(
        "person created from personnel_event_id=%s person_id=%s",
        personnel_event_id,
        person_id,
    )
    return person_id


def _update_person_fields(
    conn: Connection,
    *,
    person_id: int,
    updates: dict[str, Any],
    personnel_event_id: int,
    dry_run: bool,
) -> bool:
    if not updates:
        return False
    if dry_run:
        return True

    set_parts = []
    params: dict[str, Any] = {"person_id": int(person_id)}
    if "full_name" in updates and updates["full_name"]:
        set_parts.append("full_name = :full_name")
        params["full_name"] = str(updates["full_name"]).strip()
    if "iin" in updates:
        iin = updates["iin"]
        if iin is not None:
            iin = str(iin).strip() or None
            if iin and len(iin) != 12:
                iin = None
        set_parts.append("iin = :iin")
        params["iin"] = iin
    if "birth_date" in updates:
        set_parts.append("birth_date = :birth_date")
        params["birth_date"] = _parse_date(updates["birth_date"])

    if not set_parts:
        return False

    set_parts.append("updated_at = now()")
    conn.execute(
        text(
            f"""
            UPDATE public.persons
            SET {", ".join(set_parts)}
            WHERE person_id = :person_id
            """
        ),
        params,
    )
    logger.info(
        "person updated from personnel_event_id=%s person_id=%s fields=%s",
        personnel_event_id,
        person_id,
        sorted(updates.keys()),
    )
    return True


def _close_assignment(
    conn: Connection,
    *,
    assignment_id: int,
    personnel_event_id: int,
    dry_run: bool,
) -> bool:
    if dry_run:
        return True
    conn.execute(
        text(
            """
            UPDATE public.person_assignments
            SET
                lifecycle_status = 'closed',
                active_flag = FALSE,
                end_date = COALESCE(end_date, CURRENT_DATE),
                updated_at = now()
            WHERE assignment_id = :assignment_id
              AND lifecycle_status = 'active'
            """
        ),
        {"assignment_id": int(assignment_id)},
    )
    logger.info(
        "assignment closed from personnel_event_id=%s assignment_id=%s",
        personnel_event_id,
        assignment_id,
    )
    return True


def _create_assignment(
    conn: Connection,
    *,
    person_id: int,
    assignment_key: str,
    payload: dict[str, Any],
    snapshot_id: Optional[int],
    canonical_entry_id: Optional[int],
    personnel_event_id: int,
    source: str = "canonical",
    dry_run: bool,
) -> Optional[int]:
    existing = _find_assignment(
        conn,
        person_id=person_id,
        assignment_key=assignment_key,
        canonical_entry_id=canonical_entry_id,
        active_only=True,
    )
    if existing:
        return int(existing["assignment_id"])

    org_unit_id = _resolve_org_unit_id(conn, payload)
    if org_unit_id is None:
        raise PersonAssignmentSyncError("Cannot resolve org_unit_id for assignment creation")

    position_id = _resolve_position_id(conn, payload)
    start_date = _parse_date(payload.get("start_date")) or date.today()
    rate = _parse_rate(payload.get("rate"))

    if dry_run:
        return -1

    row = conn.execute(
        text(
            """
            INSERT INTO public.person_assignments (
                person_id,
                org_unit_id,
                position_id,
                employment_type,
                rate,
                start_date,
                active_flag,
                is_primary,
                lifecycle_status,
                assignment_key,
                source,
                canonical_snapshot_id,
                canonical_entry_id
            )
            VALUES (
                :person_id,
                :org_unit_id,
                :position_id,
                'primary',
                :rate,
                :start_date,
                TRUE,
                TRUE,
                'active',
                :assignment_key,
                :source,
                :snapshot_id,
                :canonical_entry_id
            )
            RETURNING assignment_id
            """
        ),
        {
            "person_id": int(person_id),
            "org_unit_id": int(org_unit_id),
            "position_id": int(position_id),
            "rate": rate,
            "start_date": start_date,
            "assignment_key": assignment_key,
            "source": source,
            "snapshot_id": snapshot_id,
            "canonical_entry_id": canonical_entry_id,
        },
    ).mappings().one()
    assignment_id = int(row["assignment_id"])
    logger.info(
        "assignment created from personnel_event_id=%s assignment_id=%s",
        personnel_event_id,
        assignment_id,
    )
    return assignment_id


def _update_assignment_fields(
    conn: Connection,
    *,
    assignment_id: int,
    payload: dict[str, Any],
    personnel_event_id: int,
    source: Optional[str] = None,
    dry_run: bool,
) -> bool:
    set_parts: list[str] = []
    params: dict[str, Any] = {"assignment_id": int(assignment_id)}

    if payload.get("org_unit_id") is not None or payload.get("department"):
        org_unit_id = _resolve_org_unit_id(conn, payload)
        if org_unit_id is not None:
            set_parts.append("org_unit_id = :org_unit_id")
            params["org_unit_id"] = int(org_unit_id)

    if payload.get("position_raw") is not None or payload.get("position_id") is not None:
        position_id = _resolve_position_id(conn, payload)
        set_parts.append("position_id = :position_id")
        params["position_id"] = int(position_id)

    if payload.get("rate") is not None:
        set_parts.append("rate = :rate")
        params["rate"] = _parse_rate(payload.get("rate"))

    if payload.get("assignment_key"):
        set_parts.append("assignment_key = :assignment_key")
        params["assignment_key"] = str(payload["assignment_key"])

    if source:
        set_parts.append("source = :source")
        params["source"] = source

    if not set_parts:
        return False

    if dry_run:
        return True

    set_parts.append("updated_at = now()")
    conn.execute(
        text(
            f"""
            UPDATE public.person_assignments
            SET {", ".join(set_parts)}
            WHERE assignment_id = :assignment_id
            """
        ),
        params,
    )
    logger.info(
        "assignment updated from personnel_event_id=%s assignment_id=%s fields=%s",
        personnel_event_id,
        assignment_id,
        sorted(k for k in params if k != "assignment_id"),
    )
    return True


def _ensure_employee_assignment_link(
    conn: Connection,
    *,
    employee_id: int,
    assignment_id: int,
    actor_user_id: int,
    personnel_event_id: int,
    dry_run: bool,
) -> tuple[bool, bool]:
    existing = conn.execute(
        text(
            """
            SELECT link_id, link_status
            FROM public.employee_assignment_links
            WHERE employee_id = :employee_id
              AND assignment_id = :assignment_id
            LIMIT 1
            """
        ),
        {"employee_id": int(employee_id), "assignment_id": int(assignment_id)},
    ).mappings().first()

    if existing and existing["link_status"] == "active":
        return False, False

    if dry_run:
        return existing is None, existing is not None

    if existing:
        conn.execute(
            text(
                """
                UPDATE public.employee_assignment_links
                SET
                    link_status = 'active',
                    enrolled_at = now(),
                    enrolled_by_user_id = :actor_user_id,
                    unenrolled_at = NULL,
                    unenrolled_by_user_id = NULL
                WHERE link_id = :link_id
                """
            ),
            {
                "link_id": int(existing["link_id"]),
                "actor_user_id": int(actor_user_id),
            },
        )
        logger.info(
            "employee link reactivated personnel_event_id=%s link_id=%s",
            personnel_event_id,
            existing["link_id"],
        )
        return False, True

    conn.execute(
        text(
            """
            INSERT INTO public.employee_assignment_links (
                employee_id,
                assignment_id,
                link_status,
                enrolled_by_user_id
            )
            VALUES (
                :employee_id,
                :assignment_id,
                'active',
                :actor_user_id
            )
            """
        ),
        {
            "employee_id": int(employee_id),
            "assignment_id": int(assignment_id),
            "actor_user_id": int(actor_user_id),
        },
    )
    logger.info(
        "employee link created personnel_event_id=%s employee_id=%s assignment_id=%s",
        personnel_event_id,
        employee_id,
        assignment_id,
    )
    return True, False


def _maybe_sync_employee_link(
    conn: Connection,
    *,
    person_id: int,
    assignment_id: Optional[int],
    actor_user_id: int,
    personnel_event_id: int,
    report: PersonAssignmentSyncReport,
    dry_run: bool,
) -> bool:
    if assignment_id is None:
        return False
    employee_id = _find_employee_for_person(conn, person_id)
    if employee_id is None:
        return False
    created, updated = _ensure_employee_assignment_link(
        conn,
        employee_id=employee_id,
        assignment_id=int(assignment_id),
        actor_user_id=actor_user_id,
        personnel_event_id=personnel_event_id,
        dry_run=dry_run,
    )
    if created:
        report.links_created += 1
    if updated:
        report.links_updated += 1
    return created or updated


def _ensure_person_for_event(
    conn: Connection,
    event: dict[str, Any],
    *,
    payload: dict[str, Any],
    report: PersonAssignmentSyncReport,
    dry_run: bool,
) -> Optional[int]:
    person_key = str(event["person_key"])
    metadata = _event_metadata(event)
    person = _find_person(conn, person_key=person_key, iin=payload.get("iin"))
    if person:
        return int(person["person_id"])

    person_id = event.get("person_id")
    if person_id:
        return int(person_id)

    created_id = _create_person(
        conn,
        person_key=person_key,
        payload=payload,
        snapshot_id=event.get("snapshot_id"),
        canonical_entry_id=metadata.get("canonical_entry_id"),
        personnel_event_id=int(event["personnel_event_id"]),
        dry_run=dry_run,
    )
    if created_id is not None and created_id > 0:
        report.persons_created += 1
    return created_id


def _handle_new_person(
    conn: Connection,
    event: dict[str, Any],
    *,
    report: PersonAssignmentSyncReport,
    dry_run: bool,
) -> dict[str, Any]:
    payload = _merge_payloads(
        _event_payload_value(event, prefer_new=True),
        _load_effective_payload(conn, snapshot_id=int(event["snapshot_id"]), person_key=str(event["person_key"])),
    )
    existing = _find_person(conn, person_key=str(event["person_key"]), iin=payload.get("iin"))
    if existing:
        person_id = int(existing["person_id"])
        return {"person_id": person_id, "status": STATUS_ACKNOWLEDGED, "skipped_create": True}

    person_id = _create_person(
        conn,
        person_key=str(event["person_key"]),
        payload=payload,
        snapshot_id=event.get("snapshot_id"),
        canonical_entry_id=_event_metadata(event).get("canonical_entry_id"),
        personnel_event_id=int(event["personnel_event_id"]),
        dry_run=dry_run,
    )
    if person_id is not None and person_id > 0:
        report.persons_created += 1
    return {"person_id": person_id, "status": STATUS_ACKNOWLEDGED}


def _handle_new_assignment(
    conn: Connection,
    event: dict[str, Any],
    *,
    report: PersonAssignmentSyncReport,
    dry_run: bool,
) -> dict[str, Any]:
    payload = _merge_payloads(
        _event_payload_value(event, prefer_new=True),
        _load_effective_payload(conn, snapshot_id=int(event["snapshot_id"]), person_key=str(event["person_key"])),
    )
    person_id = _ensure_person_for_event(conn, event, payload=payload, report=report, dry_run=dry_run)
    if person_id is None or person_id < 0:
        raise PersonAssignmentSyncError("Person is required before NEW_ASSIGNMENT")

    assignment_key = _assignment_key_from_event(event, payload)
    existing = _find_assignment(
        conn,
        person_id=person_id,
        assignment_key=assignment_key,
        canonical_entry_id=_event_metadata(event).get("canonical_entry_id"),
        active_only=True,
    )
    if existing:
        return {
            "person_id": person_id,
            "assignment_id": int(existing["assignment_id"]),
            "status": STATUS_ACKNOWLEDGED,
            "skipped_create": True,
        }

    assignment_id = _create_assignment(
        conn,
        person_id=person_id,
        assignment_key=assignment_key,
        payload=payload,
        snapshot_id=event.get("snapshot_id"),
        canonical_entry_id=_event_metadata(event).get("canonical_entry_id"),
        personnel_event_id=int(event["personnel_event_id"]),
        dry_run=dry_run,
    )
    if assignment_id is not None and assignment_id > 0:
        report.assignments_created += 1
    return {
        "person_id": person_id,
        "assignment_id": assignment_id,
        "status": STATUS_ACKNOWLEDGED,
    }


def _handle_closed_assignment(
    conn: Connection,
    event: dict[str, Any],
    *,
    report: PersonAssignmentSyncReport,
    dry_run: bool,
) -> dict[str, Any]:
    payload = _merge_payloads(
        _event_payload_value(event, prefer_new=False),
        _load_effective_payload(
            conn,
            snapshot_id=int(event["previous_snapshot_id"]),
            person_key=str(event["person_key"]),
        ),
    )
    person_id = event.get("person_id")
    if person_id is None:
        person = _find_person(conn, person_key=str(event["person_key"]))
        person_id = int(person["person_id"]) if person else None
    if person_id is None:
        raise PersonAssignmentSyncError("Person not found for CLOSED_ASSIGNMENT")

    assignment_key = _assignment_key_from_event(event, payload)
    assignment = _find_assignment(
        conn,
        person_id=int(person_id),
        assignment_key=assignment_key,
        assignment_id=event.get("assignment_id"),
        canonical_entry_id=_event_metadata(event).get("canonical_entry_id"),
        active_only=True,
    )
    if not assignment:
        return {
            "person_id": int(person_id),
            "status": STATUS_ACKNOWLEDGED,
            "skipped_close": True,
        }

    if _close_assignment(
        conn,
        assignment_id=int(assignment["assignment_id"]),
        personnel_event_id=int(event["personnel_event_id"]),
        dry_run=dry_run,
    ):
        report.assignments_closed += 1
    return {
        "person_id": int(person_id),
        "assignment_id": int(assignment["assignment_id"]),
        "status": STATUS_ACKNOWLEDGED,
    }


def _handle_terminated_person(
    conn: Connection,
    event: dict[str, Any],
    *,
    report: PersonAssignmentSyncReport,
    dry_run: bool,
) -> dict[str, Any]:
    person = _find_person(conn, person_key=str(event["person_key"]))
    if not person and event.get("person_id"):
        person = {"person_id": int(event["person_id"])}
    if not person:
        return {"status": STATUS_ACKNOWLEDGED, "skipped": True}

    person_id = int(person["person_id"])
    if not dry_run:
        conn.execute(
            text(
                """
                UPDATE public.persons
                SET person_status = 'inactive', updated_at = now()
                WHERE person_id = :person_id
                  AND person_status = 'active'
                """
            ),
            {"person_id": person_id},
        )
        report.persons_updated += 1

    for assignment in _find_active_assignments_for_person(conn, person_id):
        if _close_assignment(
            conn,
            assignment_id=int(assignment["assignment_id"]),
            personnel_event_id=int(event["personnel_event_id"]),
            dry_run=dry_run,
        ):
            report.assignments_closed += 1

    return {"person_id": person_id, "status": STATUS_ACKNOWLEDGED}


def _resolve_assignment_for_update(
    conn: Connection,
    event: dict[str, Any],
    *,
    payload: dict[str, Any],
) -> tuple[Optional[int], Optional[int]]:
    person_id = event.get("person_id")
    if person_id is None:
        person = _find_person(conn, person_key=str(event["person_key"]))
        person_id = int(person["person_id"]) if person else None
    if person_id is None:
        return None, None

    assignment_key = _assignment_key_from_event(event, payload)
    assignment = _find_assignment(
        conn,
        person_id=int(person_id),
        assignment_key=assignment_key,
        assignment_id=event.get("assignment_id"),
        canonical_entry_id=_event_metadata(event).get("canonical_entry_id"),
    )
    if assignment:
        return int(person_id), int(assignment["assignment_id"])
    return int(person_id), None


def _handle_department_changed(
    conn: Connection,
    event: dict[str, Any],
    *,
    report: PersonAssignmentSyncReport,
    dry_run: bool,
) -> dict[str, Any]:
    effective = _event_payload_value(event, prefer_new=True)
    payload = _merge_payloads(
        effective,
        {"department": _scalar_from_effective(effective, "department")},
        _load_effective_payload(conn, snapshot_id=int(event["snapshot_id"]), person_key=str(event["person_key"])),
    )
    person_id, assignment_id = _resolve_assignment_for_update(conn, event, payload=payload)
    if assignment_id is None:
        raise PersonAssignmentSyncError("Active assignment not found for DEPARTMENT_CHANGED")

    if _update_assignment_fields(
        conn,
        assignment_id=assignment_id,
        payload=payload,
        personnel_event_id=int(event["personnel_event_id"]),
        dry_run=dry_run,
    ):
        report.assignments_updated += 1
    return {"person_id": person_id, "assignment_id": assignment_id, "status": STATUS_ACKNOWLEDGED}


def _handle_position_changed(
    conn: Connection,
    event: dict[str, Any],
    *,
    report: PersonAssignmentSyncReport,
    dry_run: bool,
) -> dict[str, Any]:
    effective = _event_payload_value(event, prefer_new=True)
    payload = _merge_payloads(
        effective,
        {"position_raw": _scalar_from_effective(effective, "position_raw")},
        _load_effective_payload(conn, snapshot_id=int(event["snapshot_id"]), person_key=str(event["person_key"])),
    )
    person_id, assignment_id = _resolve_assignment_for_update(conn, event, payload=payload)
    if assignment_id is None:
        raise PersonAssignmentSyncError("Active assignment not found for POSITION_CHANGED")

    if _update_assignment_fields(
        conn,
        assignment_id=assignment_id,
        payload=payload,
        personnel_event_id=int(event["personnel_event_id"]),
        dry_run=dry_run,
    ):
        report.assignments_updated += 1
    return {"person_id": person_id, "assignment_id": assignment_id, "status": STATUS_ACKNOWLEDGED}


def _handle_rate_changed(
    conn: Connection,
    event: dict[str, Any],
    *,
    report: PersonAssignmentSyncReport,
    dry_run: bool,
) -> dict[str, Any]:
    effective = _event_payload_value(event, prefer_new=True)
    payload = _merge_payloads(
        effective,
        {"rate": _scalar_from_effective(effective, "rate")},
        _load_effective_payload(conn, snapshot_id=int(event["snapshot_id"]), person_key=str(event["person_key"])),
    )
    person_id, assignment_id = _resolve_assignment_for_update(conn, event, payload=payload)
    if assignment_id is None:
        raise PersonAssignmentSyncError("Active assignment not found for RATE_CHANGED")

    if _update_assignment_fields(
        conn,
        assignment_id=assignment_id,
        payload=payload,
        personnel_event_id=int(event["personnel_event_id"]),
        dry_run=dry_run,
    ):
        report.assignments_updated += 1
    return {"person_id": person_id, "assignment_id": assignment_id, "status": STATUS_ACKNOWLEDGED}


def _handle_transfer(
    conn: Connection,
    event: dict[str, Any],
    *,
    report: PersonAssignmentSyncReport,
    dry_run: bool,
) -> dict[str, Any]:
    new_payload = _merge_payloads(
        _event_payload_value(event, prefer_new=True),
        _load_effective_payload(conn, snapshot_id=int(event["snapshot_id"]), person_key=str(event["person_key"])),
    )
    old_payload = _merge_payloads(
        _event_payload_value(event, prefer_new=False),
        _load_effective_payload(
            conn,
            snapshot_id=int(event["previous_snapshot_id"]),
            person_key=str(event["person_key"]),
        ),
    )

    person_id = event.get("person_id")
    if person_id is None:
        person = _find_person(conn, person_key=str(event["person_key"]))
        person_id = int(person["person_id"]) if person else None
    if person_id is None:
        person_id = _ensure_person_for_event(
            conn,
            event,
            payload=new_payload,
            report=report,
            dry_run=dry_run,
        )
    if person_id is None or person_id < 0:
        raise PersonAssignmentSyncError("Person is required for TRANSFER")

    old_key = compute_assignment_key(str(event["person_key"]), old_payload)
    old_assignment = _find_assignment(
        conn,
        person_id=int(person_id),
        assignment_key=old_key,
        assignment_id=event.get("assignment_id"),
        active_only=True,
    )
    if old_assignment:
        if _close_assignment(
            conn,
            assignment_id=int(old_assignment["assignment_id"]),
            personnel_event_id=int(event["personnel_event_id"]),
            dry_run=dry_run,
        ):
            report.assignments_closed += 1

    new_key = _assignment_key_from_event(event, new_payload)
    existing_new = _find_assignment(
        conn,
        person_id=int(person_id),
        assignment_key=new_key,
        active_only=True,
    )
    if existing_new:
        assignment_id = int(existing_new["assignment_id"])
    else:
        assignment_id = _create_assignment(
            conn,
            person_id=int(person_id),
            assignment_key=new_key,
            payload=new_payload,
            snapshot_id=event.get("snapshot_id"),
            canonical_entry_id=_event_metadata(event).get("canonical_entry_id"),
            personnel_event_id=int(event["personnel_event_id"]),
            source="transfer",
            dry_run=dry_run,
        )
        if assignment_id is not None and assignment_id > 0:
            report.assignments_created += 1

    return {
        "person_id": int(person_id),
        "assignment_id": assignment_id if assignment_id and assignment_id > 0 else None,
        "status": STATUS_ACKNOWLEDGED,
    }


def _handle_field_changed(
    conn: Connection,
    event: dict[str, Any],
    *,
    report: PersonAssignmentSyncReport,
    dry_run: bool,
) -> dict[str, Any]:
    field_path = event.get("field_path")
    if not _is_whitelisted_field_change(field_path):
        return {"status": STATUS_ACKNOWLEDGED, "skipped": True, "non_mutating": True}

    new_value = _event_payload_value(event, prefer_new=True)
    payload = _load_effective_payload(
        conn,
        snapshot_id=int(event["snapshot_id"]),
        person_key=str(event["person_key"]),
    )

    result: dict[str, Any] = {"status": STATUS_ACKNOWLEDGED}
    if field_path in PERSON_FIELD_PATHS:
        person = _find_person(conn, person_key=str(event["person_key"]))
        if not person:
            raise PersonAssignmentSyncError(f"Person not found for FIELD_CHANGED {field_path}")
        person_id = int(person["person_id"])
        field_name = field_path.split(".", 1)[1]
        scalar = _scalar_from_effective(new_value, field_name)
        updates = {field_name: scalar}
        if _update_person_fields(
            conn,
            person_id=person_id,
            updates=updates,
            personnel_event_id=int(event["personnel_event_id"]),
            dry_run=dry_run,
        ):
            report.persons_updated += 1
        result["person_id"] = person_id
        return result

    if field_path in ASSIGNMENT_FIELD_PATHS:
        field_name = field_path.split(".", 1)[1]
        update_payload = dict(payload)
        scalar = _scalar_from_effective(new_value, field_name)
        if field_name == "department":
            update_payload["department"] = scalar
        elif field_name == "org_unit_id":
            update_payload["org_unit_id"] = scalar
        elif field_name == "position_raw":
            update_payload["position_raw"] = scalar
        elif field_name == "rate":
            update_payload["rate"] = scalar

        person_id, assignment_id = _resolve_assignment_for_update(
            conn,
            event,
            payload=update_payload,
        )
        if assignment_id is None:
            raise PersonAssignmentSyncError(f"Assignment not found for FIELD_CHANGED {field_path}")
        if _update_assignment_fields(
            conn,
            assignment_id=assignment_id,
            payload=update_payload,
            personnel_event_id=int(event["personnel_event_id"]),
            dry_run=dry_run,
        ):
            report.assignments_updated += 1
        result["person_id"] = person_id
        result["assignment_id"] = assignment_id
    return result


def _handle_override_event(event: dict[str, Any]) -> dict[str, Any]:
    return {"status": STATUS_ACKNOWLEDGED, "non_mutating": True}


def _apply_event(
    conn: Connection,
    event: dict[str, Any],
    *,
    report: PersonAssignmentSyncReport,
    actor_user_id: int,
    dry_run: bool,
) -> dict[str, Any]:
    event_type = str(event["event_type"])
    handlers = {
        EVENT_NEW_PERSON: _handle_new_person,
        EVENT_NEW_ASSIGNMENT: _handle_new_assignment,
        EVENT_CLOSED_ASSIGNMENT: _handle_closed_assignment,
        EVENT_TERMINATED_PERSON: _handle_terminated_person,
        EVENT_DEPARTMENT_CHANGED: _handle_department_changed,
        EVENT_POSITION_CHANGED: _handle_position_changed,
        EVENT_RATE_CHANGED: _handle_rate_changed,
        EVENT_TRANSFER: _handle_transfer,
        EVENT_FIELD_CHANGED: _handle_field_changed,
        EVENT_OVERRIDE_APPLIED: lambda c, e, **kw: _handle_override_event(e),
        EVENT_OVERRIDE_EXPIRED: lambda c, e, **kw: _handle_override_event(e),
    }
    handler = handlers.get(event_type)
    if handler is None:
        raise PersonAssignmentSyncError(f"Unsupported event type: {event_type}")

    outcome = handler(conn, event, report=report, dry_run=dry_run)
    status = str(outcome.get("status") or STATUS_ACKNOWLEDGED)

    link_touched = False
    link_eligible = event_type in {
        EVENT_NEW_ASSIGNMENT,
        EVENT_TRANSFER,
        EVENT_DEPARTMENT_CHANGED,
        EVENT_POSITION_CHANGED,
        EVENT_RATE_CHANGED,
        EVENT_FIELD_CHANGED,
    }
    assignment_id = outcome.get("assignment_id")
    if (
        link_eligible
        and not outcome.get("non_mutating")
        and outcome.get("person_id")
        and assignment_id
        and int(assignment_id) > 0
    ):
        link_touched = _maybe_sync_employee_link(
            conn,
            person_id=int(outcome["person_id"]),
            assignment_id=int(assignment_id),
            actor_user_id=actor_user_id,
            personnel_event_id=int(event["personnel_event_id"]),
            report=report,
            dry_run=dry_run,
        )

    if link_touched:
        status = STATUS_ENROLLED

    sync_meta = {
        "personnel_event_id": int(event["personnel_event_id"]),
        "event_type": event_type,
        "dry_run": dry_run,
        "person_id": outcome.get("person_id"),
        "assignment_id": outcome.get("assignment_id"),
        "non_mutating": bool(outcome.get("non_mutating")),
        "skipped": bool(outcome.get("skipped") or outcome.get("skipped_create") or outcome.get("skipped_close")),
    }
    _mark_event_applied(
        conn,
        event=event,
        status=status,
        actor_user_id=actor_user_id,
        sync_meta=sync_meta,
        dry_run=dry_run,
    )
    return outcome


def sync_personnel_events_tx(
    conn: Connection,
    *,
    dry_run: bool = True,
    event_ids: Optional[list[int]] = None,
    snapshot_id: Optional[int] = None,
    event_types: Optional[list[str]] = None,
    actor_user_id: Optional[int] = None,
) -> dict[str, Any]:
    report = PersonAssignmentSyncReport(dry_run=dry_run)
    actor_id = _resolve_actor_user_id(conn, actor_user_id)

    events = _load_pending_events(
        conn,
        event_ids=event_ids,
        snapshot_id=snapshot_id,
        event_types=event_types,
    )
    report.events_seen = len(events)

    for event in events:
        event_id = int(event["personnel_event_id"])
        try:
            outcome = _apply_event(
                conn,
                event,
                report=report,
                actor_user_id=actor_id,
                dry_run=dry_run,
            )
            if outcome.get("skipped") or outcome.get("non_mutating"):
                report.events_skipped += 1
            else:
                report.events_applied += 1
        except PersonAssignmentSyncError as exc:
            msg = str(exc.message)
            report.errors.append({"personnel_event_id": event_id, "error": msg})
            _mark_event_failed(conn, event=event, error=msg, dry_run=dry_run)
            logger.warning("personnel sync failed event_id=%s error=%s", event_id, msg)
        except Exception as exc:  # pragma: no cover - safety net for retryable failures
            msg = str(exc)
            report.errors.append({"personnel_event_id": event_id, "error": msg})
            _mark_event_failed(conn, event=event, error=msg, dry_run=dry_run)
            logger.exception("personnel sync unexpected failure event_id=%s", event_id)

    return report.to_dict()


def sync_personnel_events(
    *,
    dry_run: bool = True,
    event_ids: Optional[list[int]] = None,
    snapshot_id: Optional[int] = None,
    event_types: Optional[list[str]] = None,
    actor_user_id: Optional[int] = None,
    conn: Optional[Connection] = None,
) -> dict[str, Any]:
    """Apply detected hr_personnel_change_events to persons and assignments."""
    if conn is not None:
        return sync_personnel_events_tx(
            conn,
            dry_run=dry_run,
            event_ids=event_ids,
            snapshot_id=snapshot_id,
            event_types=event_types,
            actor_user_id=actor_user_id,
        )

    with engine.begin() as owned_conn:
        return sync_personnel_events_tx(
            owned_conn,
            dry_run=dry_run,
            event_ids=event_ids,
            snapshot_id=snapshot_id,
            event_types=event_types,
            actor_user_id=actor_user_id,
        )
