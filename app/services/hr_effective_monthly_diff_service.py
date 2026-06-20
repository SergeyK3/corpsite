"""ADR-043 Phase C1 — effective snapshot diff and personnel change events."""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.engine import engine
from app.services.hr_canonical_snapshot_service import RECORD_KIND_ROSTER
from app.services.hr_effective_canonical_service import (
    effective_cache_available,
    refresh_snapshot_effective_entries,
)
from app.services.hr_import_monthly_diff_service import compute_field_diffs

logger = logging.getLogger(__name__)

EVENT_NEW_PERSON = "NEW_PERSON"
EVENT_TERMINATED_PERSON = "TERMINATED_PERSON"
EVENT_NEW_ASSIGNMENT = "NEW_ASSIGNMENT"
EVENT_CLOSED_ASSIGNMENT = "CLOSED_ASSIGNMENT"
EVENT_TRANSFER = "TRANSFER"
EVENT_POSITION_CHANGED = "POSITION_CHANGED"
EVENT_DEPARTMENT_CHANGED = "DEPARTMENT_CHANGED"
EVENT_RATE_CHANGED = "RATE_CHANGED"
EVENT_FIELD_CHANGED = "FIELD_CHANGED"
EVENT_OVERRIDE_APPLIED = "OVERRIDE_APPLIED"
EVENT_OVERRIDE_EXPIRED = "OVERRIDE_EXPIRED"

PERSONNEL_EVENT_TYPES = frozenset(
    {
        EVENT_NEW_PERSON,
        EVENT_TERMINATED_PERSON,
        EVENT_NEW_ASSIGNMENT,
        EVENT_CLOSED_ASSIGNMENT,
        EVENT_TRANSFER,
        EVENT_POSITION_CHANGED,
        EVENT_DEPARTMENT_CHANGED,
        EVENT_RATE_CHANGED,
        EVENT_FIELD_CHANGED,
        EVENT_OVERRIDE_APPLIED,
        EVENT_OVERRIDE_EXPIRED,
    }
)

AUTO_ENQUEUE_EVENT_TYPES = frozenset(
    {
        EVENT_NEW_PERSON,
        EVENT_NEW_ASSIGNMENT,
        EVENT_TRANSFER,
        EVENT_DEPARTMENT_CHANGED,
        EVENT_POSITION_CHANGED,
    }
)

SKIP_ENQUEUE_EVENT_TYPES = frozenset(
    {
        EVENT_OVERRIDE_APPLIED,
        EVENT_OVERRIDE_EXPIRED,
    }
)

PERSONNEL_TO_ENROLLMENT_REASON = {
    EVENT_NEW_PERSON: "NEW_ASSIGNMENT",
    EVENT_NEW_ASSIGNMENT: "NEW_ASSIGNMENT",
    EVENT_TRANSFER: "CHANGED_ASSIGNMENT",
    EVENT_DEPARTMENT_CHANGED: "CHANGED_ASSIGNMENT",
    EVENT_POSITION_CHANGED: "CHANGED_ASSIGNMENT",
    EVENT_TERMINATED_PERSON: "REMOVED_ASSIGNMENT",
    EVENT_CLOSED_ASSIGNMENT: "REMOVED_ASSIGNMENT",
}

IDENTITY_COMPARE_FIELDS = frozenset({"full_name", "iin", "birth_date"})
ASSIGNMENT_COMPARE_FIELDS = frozenset({"department", "org_unit_id", "position_raw", "rate"})
NON_ACTIONABLE_FIELD_PREFIXES = ("note.", "display.")

FIELD_TO_PATH = {
    "full_name": "identity.full_name",
    "iin": "identity.iin",
    "birth_date": "identity.birth_date",
    "department": "roster.department",
    "org_unit_id": "roster.org_unit_id",
    "position_raw": "roster.position_raw",
    "rate": "roster.rate",
    "note_raw": "note.text",
}


class EffectiveMonthlyDiffError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


@dataclass
class EffectiveMonthlyDiffReport:
    previous_snapshot_id: int
    snapshot_id: int
    effective_entries_compared: int = 0
    persons_new: int = 0
    persons_terminated: int = 0
    assignments_new: int = 0
    assignments_closed: int = 0
    transfers: int = 0
    field_changes: int = 0
    override_events: int = 0
    events_created: int = 0
    events_existing: int = 0
    enrollment_items_created: int = 0
    enrollment_items_existing: int = 0
    warnings: list[str] = field(default_factory=list)
    dry_run: bool = True
    enqueue: bool = False
    cache_refreshed: bool = False
    planned_events: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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


def personnel_events_available(conn: Connection) -> bool:
    return _table_exists(conn, "hr_personnel_change_events")


def _serialize_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str, sort_keys=True)


def stable_json(value: Any) -> str:
    if value is None:
        return ""
    return json.dumps(value, ensure_ascii=False, default=str, sort_keys=True, separators=(",", ":"))


def compute_personnel_event_hash(
    *,
    previous_snapshot_id: int,
    snapshot_id: int,
    person_key: str,
    assignment_key: Optional[str],
    event_type: str,
    field_path: Optional[str],
    effective_old_value: Any,
    effective_new_value: Any,
) -> str:
    canonical = "|".join(
        [
            str(previous_snapshot_id),
            str(snapshot_id),
            person_key,
            assignment_key or "",
            event_type,
            field_path or "",
            stable_json(effective_old_value),
            stable_json(effective_new_value),
        ]
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_assignment_key(person_key: str, payload: dict[str, Any]) -> str:
    org = str(payload.get("org_unit_id") or payload.get("department") or "").strip().lower()
    pos = str(payload.get("position_raw") or "").strip().lower()
    return f"{person_key}|{org}|{pos}|primary"


def _parse_json(value: Any) -> Any:
    if isinstance(value, str):
        return json.loads(value) if value.strip() else None
    return value


def _parse_payload_row(row: dict[str, Any]) -> dict[str, Any]:
    payload = _parse_json(row.get("effective_payload"))
    if not isinstance(payload, dict):
        payload = {}
    override_ids = _parse_json(row.get("override_ids"))
    if not isinstance(override_ids, list):
        override_ids = []
    return {
        **row,
        "effective_payload": payload,
        "override_ids": [int(x) for x in override_ids if x is not None],
    }


def _load_canonical_payloads(conn: Connection, snapshot_id: int) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT match_key, payload
            FROM public.hr_canonical_snapshot_entries
            WHERE snapshot_id = :snapshot_id
              AND record_kind = :record_kind
            """
        ),
        {"snapshot_id": snapshot_id, "record_kind": RECORD_KIND_ROSTER},
    ).mappings().all()
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        payload = _parse_json(row["payload"])
        result[str(row["match_key"])] = payload if isinstance(payload, dict) else {}
    return result


def _load_effective_roster_entries(conn: Connection, snapshot_id: int) -> dict[str, dict[str, Any]]:
    if not effective_cache_available(conn):
        raise EffectiveMonthlyDiffError("hr_snapshot_effective_entries is not available")

    rows = conn.execute(
        text(
            """
            SELECT
                effective_entry_id,
                snapshot_id,
                canonical_entry_id,
                scope_type,
                scope_key,
                person_key,
                assignment_key,
                match_key,
                record_kind,
                effective_payload,
                override_ids,
                payload_hash,
                override_version_hash,
                computed_at
            FROM public.hr_snapshot_effective_entries
            WHERE snapshot_id = :snapshot_id
              AND record_kind = :record_kind
            ORDER BY match_key
            """
        ),
        {"snapshot_id": snapshot_id, "record_kind": RECORD_KIND_ROSTER},
    ).mappings().all()

    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        parsed = _parse_payload_row(dict(row))
        indexed[str(parsed["match_key"])] = parsed
    return indexed


def ensure_effective_cache_for_snapshots(
    conn: Connection,
    *,
    previous_snapshot_id: int,
    snapshot_id: int,
) -> dict[str, Any]:
    """Build or refresh effective cache rows for both snapshots before diff."""
    if not effective_cache_available(conn):
        raise EffectiveMonthlyDiffError("hr_snapshot_effective_entries is not available")

    prior = refresh_snapshot_effective_entries(conn, snapshot_id=previous_snapshot_id)
    current = refresh_snapshot_effective_entries(conn, snapshot_id=snapshot_id)
    return {
        "previous_snapshot_id": previous_snapshot_id,
        "snapshot_id": snapshot_id,
        "previous_refreshed": prior["refreshed_count"],
        "current_refreshed": current["refreshed_count"],
    }


def _resolve_person_ids(conn: Connection, person_key: str) -> dict[str, Optional[int]]:
    person_id: Optional[int] = None
    row = conn.execute(
        text(
            """
            SELECT person_id
            FROM public.persons
            WHERE match_key = :match_key
              AND person_status IN ('active', 'inactive')
            LIMIT 1
            """
        ),
        {"match_key": person_key},
    ).mappings().first()
    if row:
        person_id = int(row["person_id"])
    return {"person_id": person_id}


def _resolve_assignment_id(
    conn: Connection,
    *,
    person_id: Optional[int],
    assignment_key: Optional[str],
    canonical_entry_id: Optional[int],
) -> Optional[int]:
    if canonical_entry_id is not None:
        row = conn.execute(
            text(
                """
                SELECT assignment_id
                FROM public.person_assignments
                WHERE canonical_entry_id = :entry_id
                LIMIT 1
                """
            ),
            {"entry_id": int(canonical_entry_id)},
        ).mappings().first()
        if row:
            return int(row["assignment_id"])

    if person_id is not None and assignment_key:
        row = conn.execute(
            text(
                """
                SELECT assignment_id
                FROM public.person_assignments
                WHERE person_id = :person_id
                  AND lower(assignment_key) = lower(:assignment_key)
                LIMIT 1
                """
            ),
            {"person_id": person_id, "assignment_key": assignment_key},
        ).mappings().first()
        if row:
            return int(row["assignment_id"])
    return None


def _find_source_change_event_id(
    conn: Connection,
    *,
    previous_snapshot_id: int,
    snapshot_id: int,
    person_key: str,
    event_type: str,
    field_path: Optional[str],
) -> Optional[int]:
    if not _table_exists(conn, "hr_change_events"):
        return None

    legacy_map = {
        EVENT_NEW_PERSON: "NEW",
        EVENT_TERMINATED_PERSON: "REMOVED",
        EVENT_POSITION_CHANGED: "POSITION_CHANGED",
        EVENT_DEPARTMENT_CHANGED: "DEPARTMENT_CHANGED",
        EVENT_TRANSFER: "DEPARTMENT_CHANGED",
    }
    legacy_type = legacy_map.get(event_type)
    if legacy_type is None:
        return None

    field_name = None
    if field_path and "." in field_path:
        field_name = field_path.split(".", 1)[1]

    row = conn.execute(
        text(
            """
            SELECT change_event_id
            FROM public.hr_change_events
            WHERE prior_snapshot_id = :prior_id
              AND new_snapshot_id = :new_id
              AND match_key = :match_key
              AND event_type = :event_type
              AND (
                    :field_name IS NULL
                    OR field_name = :field_name
                    OR field_name IS NULL
                  )
            ORDER BY change_event_id ASC
            LIMIT 1
            """
        ),
        {
            "prior_id": previous_snapshot_id,
            "new_id": snapshot_id,
            "match_key": person_key,
            "event_type": legacy_type,
            "field_name": field_name,
        },
    ).mappings().first()
    return int(row["change_event_id"]) if row else None


def _build_personnel_event(
    *,
    previous_snapshot_id: int,
    snapshot_id: int,
    person_key: str,
    assignment_key: Optional[str],
    event_type: str,
    field_path: Optional[str] = None,
    old_value: Any = None,
    new_value: Any = None,
    effective_old_value: Any = None,
    effective_new_value: Any = None,
    person_id: Optional[int] = None,
    assignment_id: Optional[int] = None,
    source_event_id: Optional[int] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    event_hash = compute_personnel_event_hash(
        previous_snapshot_id=previous_snapshot_id,
        snapshot_id=snapshot_id,
        person_key=person_key,
        assignment_key=assignment_key,
        event_type=event_type,
        field_path=field_path,
        effective_old_value=effective_old_value,
        effective_new_value=effective_new_value,
    )
    return {
        "previous_snapshot_id": previous_snapshot_id,
        "snapshot_id": snapshot_id,
        "person_key": person_key,
        "assignment_key": assignment_key,
        "event_type": event_type,
        "field_path": field_path,
        "old_value": old_value,
        "new_value": new_value,
        "effective_old_value": effective_old_value,
        "effective_new_value": effective_new_value,
        "event_hash": event_hash,
        "status": "detected",
        "person_id": person_id,
        "assignment_id": assignment_id,
        "source_event_id": source_event_id,
        "metadata": metadata or {},
    }


def _is_actionable_field_change(field_path: str) -> bool:
    return not field_path.startswith(NON_ACTIONABLE_FIELD_PREFIXES)


def compare_effective_snapshots(
    conn: Connection,
    *,
    previous_snapshot_id: int,
    snapshot_id: int,
) -> list[dict[str, Any]]:
    """Compare effective roster entries between two snapshots; return planned personnel events."""
    if previous_snapshot_id == snapshot_id:
        raise EffectiveMonthlyDiffError("previous_snapshot_id must differ from snapshot_id")

    prior_effective = _load_effective_roster_entries(conn, previous_snapshot_id)
    new_effective = _load_effective_roster_entries(conn, snapshot_id)
    prior_canonical = _load_canonical_payloads(conn, previous_snapshot_id)
    new_canonical = _load_canonical_payloads(conn, snapshot_id)

    prior_keys = set(prior_effective.keys())
    new_keys = set(new_effective.keys())

    events: list[dict[str, Any]] = []

    for person_key in sorted(new_keys - prior_keys):
        entry = new_effective[person_key]
        payload = entry["effective_payload"]
        assignment_key = compute_assignment_key(person_key, payload)
        person_ids = _resolve_person_ids(conn, person_key)
        events.append(
            _build_personnel_event(
                previous_snapshot_id=previous_snapshot_id,
                snapshot_id=snapshot_id,
                person_key=person_key,
                assignment_key=assignment_key,
                event_type=EVENT_NEW_PERSON,
                effective_new_value={
                    "full_name": payload.get("full_name"),
                    "iin": payload.get("iin"),
                    "assignment_key": assignment_key,
                },
                person_id=person_ids["person_id"],
                assignment_id=_resolve_assignment_id(
                    conn,
                    person_id=person_ids["person_id"],
                    assignment_key=assignment_key,
                    canonical_entry_id=entry.get("canonical_entry_id"),
                ),
                source_event_id=_find_source_change_event_id(
                    conn,
                    previous_snapshot_id=previous_snapshot_id,
                    snapshot_id=snapshot_id,
                    person_key=person_key,
                    event_type=EVENT_NEW_PERSON,
                    field_path=None,
                ),
                metadata={"canonical_entry_id": entry.get("canonical_entry_id")},
            )
        )
        events.append(
            _build_personnel_event(
                previous_snapshot_id=previous_snapshot_id,
                snapshot_id=snapshot_id,
                person_key=person_key,
                assignment_key=assignment_key,
                event_type=EVENT_NEW_ASSIGNMENT,
                effective_new_value={
                    "department": payload.get("department"),
                    "org_unit_id": payload.get("org_unit_id"),
                    "position_raw": payload.get("position_raw"),
                },
                person_id=person_ids["person_id"],
                assignment_id=_resolve_assignment_id(
                    conn,
                    person_id=person_ids["person_id"],
                    assignment_key=assignment_key,
                    canonical_entry_id=entry.get("canonical_entry_id"),
                ),
                metadata={"canonical_entry_id": entry.get("canonical_entry_id")},
            )
        )

    for person_key in sorted(prior_keys - new_keys):
        entry = prior_effective[person_key]
        payload = entry["effective_payload"]
        assignment_key = compute_assignment_key(person_key, payload)
        person_ids = _resolve_person_ids(conn, person_key)
        events.append(
            _build_personnel_event(
                previous_snapshot_id=previous_snapshot_id,
                snapshot_id=snapshot_id,
                person_key=person_key,
                assignment_key=assignment_key,
                event_type=EVENT_TERMINATED_PERSON,
                effective_old_value={
                    "full_name": payload.get("full_name"),
                    "iin": payload.get("iin"),
                },
                person_id=person_ids["person_id"],
                assignment_id=_resolve_assignment_id(
                    conn,
                    person_id=person_ids["person_id"],
                    assignment_key=assignment_key,
                    canonical_entry_id=entry.get("canonical_entry_id"),
                ),
                source_event_id=_find_source_change_event_id(
                    conn,
                    previous_snapshot_id=previous_snapshot_id,
                    snapshot_id=snapshot_id,
                    person_key=person_key,
                    event_type=EVENT_TERMINATED_PERSON,
                    field_path=None,
                ),
            )
        )
        events.append(
            _build_personnel_event(
                previous_snapshot_id=previous_snapshot_id,
                snapshot_id=snapshot_id,
                person_key=person_key,
                assignment_key=assignment_key,
                event_type=EVENT_CLOSED_ASSIGNMENT,
                effective_old_value={
                    "department": payload.get("department"),
                    "org_unit_id": payload.get("org_unit_id"),
                    "position_raw": payload.get("position_raw"),
                },
                person_id=person_ids["person_id"],
                assignment_id=_resolve_assignment_id(
                    conn,
                    person_id=person_ids["person_id"],
                    assignment_key=assignment_key,
                    canonical_entry_id=entry.get("canonical_entry_id"),
                ),
            )
        )

    for person_key in sorted(prior_keys & new_keys):
        prior_entry = prior_effective[person_key]
        new_entry = new_effective[person_key]
        prior_eff = prior_entry["effective_payload"]
        new_eff = new_entry["effective_payload"]
        prior_can = prior_canonical.get(person_key, {})
        new_can = new_canonical.get(person_key, {})

        person_ids = _resolve_person_ids(conn, person_key)
        person_id = person_ids["person_id"]

        prior_assign = compute_assignment_key(person_key, prior_eff)
        new_assign = compute_assignment_key(person_key, new_eff)

        org_changed = prior_eff.get("org_unit_id") != new_eff.get("org_unit_id") or prior_eff.get(
            "department"
        ) != new_eff.get("department")
        pos_changed = prior_eff.get("position_raw") != new_eff.get("position_raw")
        rate_changed = prior_eff.get("rate") != new_eff.get("rate")

        if prior_assign != new_assign or org_changed or pos_changed or rate_changed:
            if org_changed and pos_changed:
                events.append(
                    _build_personnel_event(
                        previous_snapshot_id=previous_snapshot_id,
                        snapshot_id=snapshot_id,
                        person_key=person_key,
                        assignment_key=new_assign,
                        event_type=EVENT_TRANSFER,
                        field_path="roster.org_unit_id",
                        old_value=prior_can.get("org_unit_id"),
                        new_value=new_can.get("org_unit_id"),
                        effective_old_value={
                            "department": prior_eff.get("department"),
                            "org_unit_id": prior_eff.get("org_unit_id"),
                            "position_raw": prior_eff.get("position_raw"),
                        },
                        effective_new_value={
                            "department": new_eff.get("department"),
                            "org_unit_id": new_eff.get("org_unit_id"),
                            "position_raw": new_eff.get("position_raw"),
                        },
                        person_id=person_id,
                        assignment_id=_resolve_assignment_id(
                            conn,
                            person_id=person_id,
                            assignment_key=new_assign,
                            canonical_entry_id=new_entry.get("canonical_entry_id"),
                        ),
                        source_event_id=_find_source_change_event_id(
                            conn,
                            previous_snapshot_id=previous_snapshot_id,
                            snapshot_id=snapshot_id,
                            person_key=person_key,
                            event_type=EVENT_TRANSFER,
                            field_path="roster.org_unit_id",
                        ),
                    )
                )
            elif org_changed:
                events.append(
                    _build_personnel_event(
                        previous_snapshot_id=previous_snapshot_id,
                        snapshot_id=snapshot_id,
                        person_key=person_key,
                        assignment_key=new_assign,
                        event_type=EVENT_DEPARTMENT_CHANGED,
                        field_path="roster.department",
                        old_value=prior_can.get("department"),
                        new_value=new_can.get("department"),
                        effective_old_value=prior_eff.get("department"),
                        effective_new_value=new_eff.get("department"),
                        person_id=person_id,
                        assignment_id=_resolve_assignment_id(
                            conn,
                            person_id=person_id,
                            assignment_key=new_assign,
                            canonical_entry_id=new_entry.get("canonical_entry_id"),
                        ),
                        source_event_id=_find_source_change_event_id(
                            conn,
                            previous_snapshot_id=previous_snapshot_id,
                            snapshot_id=snapshot_id,
                            person_key=person_key,
                            event_type=EVENT_DEPARTMENT_CHANGED,
                            field_path="roster.department",
                        ),
                    )
                )
            elif pos_changed:
                events.append(
                    _build_personnel_event(
                        previous_snapshot_id=previous_snapshot_id,
                        snapshot_id=snapshot_id,
                        person_key=person_key,
                        assignment_key=new_assign,
                        event_type=EVENT_POSITION_CHANGED,
                        field_path="roster.position_raw",
                        old_value=prior_can.get("position_raw"),
                        new_value=new_can.get("position_raw"),
                        effective_old_value=prior_eff.get("position_raw"),
                        effective_new_value=new_eff.get("position_raw"),
                        person_id=person_id,
                        assignment_id=_resolve_assignment_id(
                            conn,
                            person_id=person_id,
                            assignment_key=new_assign,
                            canonical_entry_id=new_entry.get("canonical_entry_id"),
                        ),
                        source_event_id=_find_source_change_event_id(
                            conn,
                            previous_snapshot_id=previous_snapshot_id,
                            snapshot_id=snapshot_id,
                            person_key=person_key,
                            event_type=EVENT_POSITION_CHANGED,
                            field_path="roster.position_raw",
                        ),
                    )
                )
            elif prior_assign != new_assign:
                events.append(
                    _build_personnel_event(
                        previous_snapshot_id=previous_snapshot_id,
                        snapshot_id=snapshot_id,
                        person_key=person_key,
                        assignment_key=prior_assign,
                        event_type=EVENT_CLOSED_ASSIGNMENT,
                        effective_old_value={
                            "department": prior_eff.get("department"),
                            "org_unit_id": prior_eff.get("org_unit_id"),
                            "position_raw": prior_eff.get("position_raw"),
                        },
                        person_id=person_id,
                        assignment_id=_resolve_assignment_id(
                            conn,
                            person_id=person_id,
                            assignment_key=prior_assign,
                            canonical_entry_id=prior_entry.get("canonical_entry_id"),
                        ),
                    )
                )
                events.append(
                    _build_personnel_event(
                        previous_snapshot_id=previous_snapshot_id,
                        snapshot_id=snapshot_id,
                        person_key=person_key,
                        assignment_key=new_assign,
                        event_type=EVENT_NEW_ASSIGNMENT,
                        effective_new_value={
                            "department": new_eff.get("department"),
                            "org_unit_id": new_eff.get("org_unit_id"),
                            "position_raw": new_eff.get("position_raw"),
                        },
                        person_id=person_id,
                        assignment_id=_resolve_assignment_id(
                            conn,
                            person_id=person_id,
                            assignment_key=new_assign,
                            canonical_entry_id=new_entry.get("canonical_entry_id"),
                        ),
                    )
                )

            if rate_changed and not org_changed and not pos_changed:
                events.append(
                    _build_personnel_event(
                        previous_snapshot_id=previous_snapshot_id,
                        snapshot_id=snapshot_id,
                        person_key=person_key,
                        assignment_key=new_assign,
                        event_type=EVENT_RATE_CHANGED,
                        field_path="roster.rate",
                        old_value=prior_can.get("rate"),
                        new_value=new_can.get("rate"),
                        effective_old_value=prior_eff.get("rate"),
                        effective_new_value=new_eff.get("rate"),
                        person_id=person_id,
                        assignment_id=_resolve_assignment_id(
                            conn,
                            person_id=person_id,
                            assignment_key=new_assign,
                            canonical_entry_id=new_entry.get("canonical_entry_id"),
                        ),
                    )
                )

            identity_diffs = compute_field_diffs(
                canonical_payload=prior_eff,
                incoming_payload=new_eff,
                compare_fields=IDENTITY_COMPARE_FIELDS,
            )
            for fld, diff in identity_diffs.items():
                field_path = FIELD_TO_PATH.get(fld, f"identity.{fld}")
                events.append(
                    _build_personnel_event(
                        previous_snapshot_id=previous_snapshot_id,
                        snapshot_id=snapshot_id,
                        person_key=person_key,
                        assignment_key=new_assign,
                        event_type=EVENT_FIELD_CHANGED,
                        field_path=field_path,
                        old_value=prior_can.get(fld),
                        new_value=new_can.get(fld),
                        effective_old_value=diff.get("canonical"),
                        effective_new_value=diff.get("incoming"),
                        person_id=person_id,
                        assignment_id=_resolve_assignment_id(
                            conn,
                            person_id=person_id,
                            assignment_key=new_assign,
                            canonical_entry_id=new_entry.get("canonical_entry_id"),
                        ),
                    )
                )

            other_diffs = compute_field_diffs(
                canonical_payload=prior_eff,
                incoming_payload=new_eff,
                compare_fields=frozenset({"note_raw"}),
            )
            for fld, diff in other_diffs.items():
                field_path = FIELD_TO_PATH.get(fld, fld)
                events.append(
                    _build_personnel_event(
                        previous_snapshot_id=previous_snapshot_id,
                        snapshot_id=snapshot_id,
                        person_key=person_key,
                        assignment_key=new_assign,
                        event_type=EVENT_FIELD_CHANGED,
                        field_path=field_path,
                        old_value=prior_can.get(fld),
                        new_value=new_can.get(fld),
                        effective_old_value=diff.get("canonical"),
                        effective_new_value=diff.get("incoming"),
                        person_id=person_id,
                        assignment_id=_resolve_assignment_id(
                            conn,
                            person_id=person_id,
                            assignment_key=new_assign,
                            canonical_entry_id=new_entry.get("canonical_entry_id"),
                        ),
                    )
                )

            prior_override_fields = set(prior_eff.get("_override_fields") or [])
            new_override_fields = set(new_eff.get("_override_fields") or [])
            for field_path in sorted(new_override_fields - prior_override_fields):
                events.append(
                    _build_personnel_event(
                        previous_snapshot_id=previous_snapshot_id,
                        snapshot_id=snapshot_id,
                        person_key=person_key,
                        assignment_key=new_assign,
                        event_type=EVENT_OVERRIDE_APPLIED,
                        field_path=field_path,
                        effective_new_value=new_eff.get(
                            field_path.split(".", 1)[1]
                            if "." in field_path
                            else field_path
                        ),
                        person_id=person_id,
                        metadata={
                            "override_ids_new": new_entry.get("override_ids"),
                            "override_ids_prior": prior_entry.get("override_ids"),
                        },
                    )
                )
            for field_path in sorted(prior_override_fields - new_override_fields):
                events.append(
                    _build_personnel_event(
                        previous_snapshot_id=previous_snapshot_id,
                        snapshot_id=snapshot_id,
                        person_key=person_key,
                        assignment_key=new_assign,
                        event_type=EVENT_OVERRIDE_EXPIRED,
                        field_path=field_path,
                        effective_old_value=prior_eff.get(
                            field_path.split(".", 1)[1]
                            if "." in field_path
                            else field_path
                        ),
                        person_id=person_id,
                        metadata={
                            "override_ids_new": new_entry.get("override_ids"),
                            "override_ids_prior": prior_entry.get("override_ids"),
                        },
                    )
                )

            prior_ids = set(prior_entry.get("override_ids") or [])
            new_ids = set(new_entry.get("override_ids") or [])
            if prior_ids != new_ids and not (new_override_fields - prior_override_fields):
                if new_ids - prior_ids:
                    events.append(
                        _build_personnel_event(
                            previous_snapshot_id=previous_snapshot_id,
                            snapshot_id=snapshot_id,
                            person_key=person_key,
                            assignment_key=new_assign,
                            event_type=EVENT_OVERRIDE_APPLIED,
                            field_path="override.ids",
                            effective_old_value=sorted(prior_ids),
                            effective_new_value=sorted(new_ids),
                            person_id=person_id,
                            metadata={"override_ids_added": sorted(new_ids - prior_ids)},
                        )
                    )
                if prior_ids - new_ids:
                    events.append(
                        _build_personnel_event(
                            previous_snapshot_id=previous_snapshot_id,
                            snapshot_id=snapshot_id,
                            person_key=person_key,
                            assignment_key=new_assign,
                            event_type=EVENT_OVERRIDE_EXPIRED,
                            field_path="override.ids",
                            effective_old_value=sorted(prior_ids),
                            effective_new_value=sorted(new_ids),
                            person_id=person_id,
                            metadata={"override_ids_removed": sorted(prior_ids - new_ids)},
                        )
                    )
            continue

        identity_diffs = compute_field_diffs(
            canonical_payload=prior_eff,
            incoming_payload=new_eff,
            compare_fields=IDENTITY_COMPARE_FIELDS,
        )
        for fld, diff in identity_diffs.items():
            field_path = FIELD_TO_PATH.get(fld, f"identity.{fld}")
            events.append(
                _build_personnel_event(
                    previous_snapshot_id=previous_snapshot_id,
                    snapshot_id=snapshot_id,
                    person_key=person_key,
                    assignment_key=new_assign,
                    event_type=EVENT_FIELD_CHANGED,
                    field_path=field_path,
                    old_value=prior_can.get(fld),
                    new_value=new_can.get(fld),
                    effective_old_value=diff.get("canonical"),
                    effective_new_value=diff.get("incoming"),
                    person_id=person_id,
                    assignment_id=_resolve_assignment_id(
                        conn,
                        person_id=person_id,
                        assignment_key=new_assign,
                        canonical_entry_id=new_entry.get("canonical_entry_id"),
                    ),
                )
            )

        other_diffs = compute_field_diffs(
            canonical_payload=prior_eff,
            incoming_payload=new_eff,
            compare_fields=frozenset({"note_raw"}),
        )
        for fld, diff in other_diffs.items():
            field_path = FIELD_TO_PATH.get(fld, fld)
            events.append(
                _build_personnel_event(
                    previous_snapshot_id=previous_snapshot_id,
                    snapshot_id=snapshot_id,
                    person_key=person_key,
                    assignment_key=new_assign,
                    event_type=EVENT_FIELD_CHANGED,
                    field_path=field_path,
                    old_value=prior_can.get(fld),
                    new_value=new_can.get(fld),
                    effective_old_value=diff.get("canonical"),
                    effective_new_value=diff.get("incoming"),
                    person_id=person_id,
                    assignment_id=_resolve_assignment_id(
                        conn,
                        person_id=person_id,
                        assignment_key=new_assign,
                        canonical_entry_id=new_entry.get("canonical_entry_id"),
                    ),
                )
            )

        prior_override_fields = set(prior_eff.get("_override_fields") or [])
        new_override_fields = set(new_eff.get("_override_fields") or [])
        for field_path in sorted(new_override_fields - prior_override_fields):
            events.append(
                _build_personnel_event(
                    previous_snapshot_id=previous_snapshot_id,
                    snapshot_id=snapshot_id,
                    person_key=person_key,
                    assignment_key=new_assign,
                    event_type=EVENT_OVERRIDE_APPLIED,
                    field_path=field_path,
                    effective_new_value=new_eff.get(
                        field_path.split(".", 1)[1]
                        if "." in field_path
                        else field_path
                    ),
                    person_id=person_id,
                    metadata={
                        "override_ids_new": new_entry.get("override_ids"),
                        "override_ids_prior": prior_entry.get("override_ids"),
                    },
                )
            )
        for field_path in sorted(prior_override_fields - new_override_fields):
            events.append(
                _build_personnel_event(
                    previous_snapshot_id=previous_snapshot_id,
                    snapshot_id=snapshot_id,
                    person_key=person_key,
                    assignment_key=new_assign,
                    event_type=EVENT_OVERRIDE_EXPIRED,
                    field_path=field_path,
                    effective_old_value=prior_eff.get(
                        field_path.split(".", 1)[1]
                        if "." in field_path
                        else field_path
                    ),
                    person_id=person_id,
                    metadata={
                        "override_ids_new": new_entry.get("override_ids"),
                        "override_ids_prior": prior_entry.get("override_ids"),
                    },
                )
            )

        prior_ids = set(prior_entry.get("override_ids") or [])
        new_ids = set(new_entry.get("override_ids") or [])
        if prior_ids != new_ids and not (new_override_fields - prior_override_fields):
            if new_ids - prior_ids:
                events.append(
                    _build_personnel_event(
                        previous_snapshot_id=previous_snapshot_id,
                        snapshot_id=snapshot_id,
                        person_key=person_key,
                        assignment_key=new_assign,
                        event_type=EVENT_OVERRIDE_APPLIED,
                        field_path="override.ids",
                        effective_old_value=sorted(prior_ids),
                        effective_new_value=sorted(new_ids),
                        person_id=person_id,
                        metadata={"override_ids_added": sorted(new_ids - prior_ids)},
                    )
                )
            if prior_ids - new_ids:
                events.append(
                    _build_personnel_event(
                        previous_snapshot_id=previous_snapshot_id,
                        snapshot_id=snapshot_id,
                        person_key=person_key,
                        assignment_key=new_assign,
                        event_type=EVENT_OVERRIDE_EXPIRED,
                        field_path="override.ids",
                        effective_old_value=sorted(prior_ids),
                        effective_new_value=sorted(new_ids),
                        person_id=person_id,
                        metadata={"override_ids_removed": sorted(prior_ids - new_ids)},
                    )
                )

    return events


def _count_existing_event_hashes(conn: Connection, events: list[dict[str, Any]]) -> int:
    if not events:
        return 0
    hashes = [event["event_hash"] for event in events]
    row = conn.execute(
        text(
            """
            SELECT COUNT(*) AS cnt
            FROM public.hr_personnel_change_events
            WHERE event_hash = ANY(:hashes)
            """
        ),
        {"hashes": hashes},
    ).mappings().one()
    return int(row["cnt"])


def materialize_personnel_change_events(
    conn: Connection,
    events: list[dict[str, Any]],
    *,
    dry_run: bool = True,
) -> dict[str, int]:
    if dry_run:
        existing = _count_existing_event_hashes(conn, events) if personnel_events_available(conn) else 0
        return {
            "events_created": 0,
            "events_existing": existing,
            "personnel_event_ids": [],
        }

    if not personnel_events_available(conn):
        raise EffectiveMonthlyDiffError("hr_personnel_change_events is not available")

    created_ids: list[int] = []
    existing_count = 0

    for event in events:
        row = conn.execute(
            text(
                """
                INSERT INTO public.hr_personnel_change_events (
                    source_event_id,
                    previous_snapshot_id,
                    snapshot_id,
                    person_id,
                    assignment_id,
                    person_key,
                    assignment_key,
                    event_type,
                    field_path,
                    old_value,
                    new_value,
                    effective_old_value,
                    effective_new_value,
                    event_hash,
                    status,
                    metadata
                ) VALUES (
                    :source_event_id,
                    :previous_snapshot_id,
                    :snapshot_id,
                    :person_id,
                    :assignment_id,
                    :person_key,
                    :assignment_key,
                    :event_type,
                    :field_path,
                    CAST(:old_value AS jsonb),
                    CAST(:new_value AS jsonb),
                    CAST(:effective_old_value AS jsonb),
                    CAST(:effective_new_value AS jsonb),
                    :event_hash,
                    :status,
                    CAST(:metadata AS jsonb)
                )
                ON CONFLICT (event_hash) DO NOTHING
                RETURNING personnel_event_id
                """
            ),
            {
                **event,
                "old_value": _serialize_json(event["old_value"]) if event.get("old_value") is not None else None,
                "new_value": _serialize_json(event["new_value"]) if event.get("new_value") is not None else None,
                "effective_old_value": _serialize_json(event["effective_old_value"])
                if event.get("effective_old_value") is not None
                else None,
                "effective_new_value": _serialize_json(event["effective_new_value"])
                if event.get("effective_new_value") is not None
                else None,
                "metadata": _serialize_json(event.get("metadata") or {}),
            },
        ).first()
        if row:
            created_ids.append(int(row[0]))
        else:
            existing_count += 1

    return {
        "events_created": len(created_ids),
        "events_existing": existing_count,
        "personnel_event_ids": created_ids,
    }


def _build_personnel_idempotency_key(
    *,
    personnel_event_id: int,
    reason: str,
    person_id: Optional[int],
    assignment_id: Optional[int],
) -> str:
    target = assignment_id or person_id or "none"
    return f"pe:{personnel_event_id}|{reason}|{target}"


def _should_enqueue_personnel_event(event: dict[str, Any]) -> bool:
    event_type = str(event["event_type"])
    if event_type in SKIP_ENQUEUE_EVENT_TYPES:
        return False
    if event_type == EVENT_FIELD_CHANGED:
        field_path = str(event.get("field_path") or "")
        return _is_actionable_field_change(field_path)
    return event_type in AUTO_ENQUEUE_EVENT_TYPES


def enqueue_personnel_events_for_review(
    conn: Connection,
    *,
    personnel_event_ids: list[int],
    dry_run: bool = True,
) -> dict[str, Any]:
    """Create enrollment_queue rows for actionable personnel events (idempotent)."""
    if not personnel_event_ids:
        return {"enrollment_items_created": 0, "enrollment_items_existing": 0, "items": []}

    if not _table_exists(conn, "enrollment_queue"):
        raise EffectiveMonthlyDiffError("enrollment_queue is not available")

    rows = conn.execute(
        text(
            """
            SELECT
                pe.personnel_event_id,
                pe.event_type,
                pe.person_id,
                pe.assignment_id,
                pe.person_key,
                pe.assignment_key,
                pe.field_path,
                pe.snapshot_id,
                cse.canonical_entry_id
            FROM public.hr_personnel_change_events pe
            LEFT JOIN public.hr_snapshot_effective_entries cse
              ON cse.snapshot_id = pe.snapshot_id
             AND cse.match_key = pe.person_key
             AND cse.record_kind = 'roster'
            WHERE pe.personnel_event_id = ANY(:ids)
            ORDER BY pe.personnel_event_id
            """
        ),
        {"ids": personnel_event_ids},
    ).mappings().all()

    created = 0
    existing = 0
    items: list[dict[str, Any]] = []

    for row in rows:
        event = dict(row)
        if not _should_enqueue_personnel_event(
            {
                "event_type": event["event_type"],
                "field_path": event.get("field_path"),
            }
        ):
            continue

        reason = PERSONNEL_TO_ENROLLMENT_REASON.get(str(event["event_type"]))
        if not reason:
            continue

        personnel_event_id = int(event["personnel_event_id"])
        person_id = int(event["person_id"]) if event.get("person_id") is not None else None
        assignment_id = int(event["assignment_id"]) if event.get("assignment_id") is not None else None
        canonical_entry_id = (
            int(event["canonical_entry_id"]) if event.get("canonical_entry_id") is not None else None
        )
        if person_id is None and assignment_id is None and canonical_entry_id is None:
            continue
        idempotency_key = _build_personnel_idempotency_key(
            personnel_event_id=personnel_event_id,
            reason=reason,
            person_id=person_id,
            assignment_id=assignment_id,
        )

        hit = conn.execute(
            text(
                """
                SELECT queue_id, queue_status
                FROM public.enrollment_queue
                WHERE idempotency_key = :key
                   OR personnel_event_id = :peid
                LIMIT 1
                """
            ),
            {"key": idempotency_key, "peid": personnel_event_id},
        ).mappings().first()

        if hit:
            existing += 1
            items.append(
                {
                    "queue_id": int(hit["queue_id"]),
                    "personnel_event_id": personnel_event_id,
                    "idempotent_hit": True,
                }
            )
            continue

        if dry_run:
            items.append(
                {
                    "personnel_event_id": personnel_event_id,
                    "would_enqueue": True,
                    "reason": reason,
                    "idempotency_key": idempotency_key,
                }
            )
            created += 1
            continue

        queue_row = conn.execute(
            text(
                """
                INSERT INTO public.enrollment_queue (
                    person_id,
                    assignment_id,
                    personnel_event_id,
                    canonical_entry_id,
                    queue_status,
                    reason,
                    idempotency_key
                ) VALUES (
                    :person_id,
                    :assignment_id,
                    :personnel_event_id,
                    :canonical_entry_id,
                    'PENDING',
                    :reason,
                    :idempotency_key
                )
                RETURNING queue_id
                """
            ),
            {
                "person_id": person_id,
                "assignment_id": assignment_id,
                "personnel_event_id": personnel_event_id,
                "canonical_entry_id": canonical_entry_id,
                "reason": reason,
                "idempotency_key": idempotency_key,
            },
        ).first()
        queue_id = int(queue_row[0])
        if _table_exists(conn, "enrollment_history"):
            conn.execute(
                text(
                    """
                    INSERT INTO public.enrollment_history (
                        queue_id, event_type, person_id, assignment_id, metadata
                    ) VALUES (
                        :queue_id, 'DETECTED', :person_id, :assignment_id,
                        CAST(:metadata AS jsonb)
                    )
                    """
                ),
                {
                    "queue_id": queue_id,
                    "person_id": person_id,
                    "assignment_id": assignment_id,
                    "metadata": _serialize_json(
                        {"source": "enqueue_personnel_events_for_review", "personnel_event_id": personnel_event_id}
                    ),
                },
            )
        created += 1
        items.append({"queue_id": queue_id, "personnel_event_id": personnel_event_id, "idempotent_hit": False})

    return {
        "enrollment_items_created": created,
        "enrollment_items_existing": existing,
        "items": items,
        "dry_run": dry_run,
    }


def _summarize_events(events: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "persons_new": 0,
        "persons_terminated": 0,
        "assignments_new": 0,
        "assignments_closed": 0,
        "transfers": 0,
        "field_changes": 0,
        "override_events": 0,
    }
    for event in events:
        et = event["event_type"]
        if et == EVENT_NEW_PERSON:
            counts["persons_new"] += 1
        elif et == EVENT_TERMINATED_PERSON:
            counts["persons_terminated"] += 1
        elif et == EVENT_NEW_ASSIGNMENT:
            counts["assignments_new"] += 1
        elif et == EVENT_CLOSED_ASSIGNMENT:
            counts["assignments_closed"] += 1
        elif et == EVENT_TRANSFER:
            counts["transfers"] += 1
        elif et == EVENT_FIELD_CHANGED:
            counts["field_changes"] += 1
        elif et in {EVENT_OVERRIDE_APPLIED, EVENT_OVERRIDE_EXPIRED}:
            counts["override_events"] += 1
    return counts


def run_effective_monthly_diff(
    conn: Connection,
    *,
    previous_snapshot_id: int,
    snapshot_id: int,
    dry_run: bool = True,
    enqueue: bool = False,
    refresh_cache: bool = True,
) -> dict[str, Any]:
    """
    Compare effective snapshots, optionally materialize personnel events and enqueue review items.

    dry_run=True: preview only (no personnel events or enrollment writes).
    dry_run=False: insert personnel events (idempotent by event_hash).
    enqueue=True: after execute, call enqueue_personnel_events_for_review.
    """
    if not personnel_events_available(conn):
        raise EffectiveMonthlyDiffError("hr_personnel_change_events is not available")

    warnings: list[str] = []
    cache_refreshed = False

    if refresh_cache:
        ensure_effective_cache_for_snapshots(
            conn,
            previous_snapshot_id=previous_snapshot_id,
            snapshot_id=snapshot_id,
        )
        cache_refreshed = True

    prior_count = len(_load_effective_roster_entries(conn, previous_snapshot_id))
    new_count = len(_load_effective_roster_entries(conn, snapshot_id))
    if prior_count == 0:
        warnings.append(f"previous snapshot {previous_snapshot_id} has no effective roster entries")
    if new_count == 0:
        warnings.append(f"current snapshot {snapshot_id} has no effective roster entries")

    planned_events = compare_effective_snapshots(
        conn,
        previous_snapshot_id=previous_snapshot_id,
        snapshot_id=snapshot_id,
    )
    summary = _summarize_events(planned_events)

    materialize_result = materialize_personnel_change_events(conn, planned_events, dry_run=dry_run)

    personnel_event_ids = materialize_result.get("personnel_event_ids") or []
    if not dry_run and not personnel_event_ids:
        rows = conn.execute(
            text(
                """
                SELECT personnel_event_id
                FROM public.hr_personnel_change_events
                WHERE previous_snapshot_id = :prior_id
                  AND snapshot_id = :new_id
                ORDER BY personnel_event_id
                """
            ),
            {"prior_id": previous_snapshot_id, "new_id": snapshot_id},
        ).fetchall()
        personnel_event_ids = [int(r[0]) for r in rows]

    enqueue_result = {"enrollment_items_created": 0, "enrollment_items_existing": 0}
    if enqueue:
        if dry_run:
            would_enqueue = sum(
                1 for event in planned_events if _should_enqueue_personnel_event(event)
            )
            enqueue_result = {
                "enrollment_items_created": would_enqueue,
                "enrollment_items_existing": 0,
                "dry_run": True,
            }
        elif personnel_event_ids:
            enqueue_result = enqueue_personnel_events_for_review(
                conn,
                personnel_event_ids=personnel_event_ids,
                dry_run=False,
            )

    report = EffectiveMonthlyDiffReport(
        previous_snapshot_id=previous_snapshot_id,
        snapshot_id=snapshot_id,
        effective_entries_compared=prior_count + new_count,
        persons_new=summary["persons_new"],
        persons_terminated=summary["persons_terminated"],
        assignments_new=summary["assignments_new"],
        assignments_closed=summary["assignments_closed"],
        transfers=summary["transfers"],
        field_changes=summary["field_changes"],
        override_events=summary["override_events"],
        events_created=materialize_result["events_created"],
        events_existing=materialize_result["events_existing"],
        enrollment_items_created=enqueue_result.get("enrollment_items_created", 0),
        enrollment_items_existing=enqueue_result.get("enrollment_items_existing", 0),
        warnings=warnings,
        dry_run=dry_run,
        enqueue=enqueue,
        cache_refreshed=cache_refreshed,
        planned_events=planned_events,
    )
    return report.to_dict()


def run_effective_monthly_diff_tx(**kwargs: Any) -> dict[str, Any]:
    with engine.begin() as conn:
        return run_effective_monthly_diff(conn, **kwargs)
