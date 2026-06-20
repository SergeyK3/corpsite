"""ADR-043 Phase B3 — Effective Canonical resolver and effective cache refresh."""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.engine import engine
from app.services.hr_canonical_snapshot_service import (
    SOURCE_TYPE_HR_CONTROL_LIST,
    compute_canonical_hash,
    get_active_snapshot,
)

COMPUTE_VERSION = 1

SCOPE_PREFIXES = frozenset(
    {"identity", "roster", "training", "certificate", "category", "education", "specialty", "note", "display"}
)

ROSTER_IDENTITY_FIELDS = frozenset({"full_name", "iin", "birth_date"})


class EffectiveCanonicalError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def _table_exists(conn: Connection, table: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = :table
            LIMIT 1
            """
        ),
        {"table": table},
    ).first()
    return row is not None


def effective_cache_available(conn: Connection) -> bool:
    return _table_exists(conn, "hr_snapshot_effective_entries")


def _serialize_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def field_path_to_payload_key(field_path: str) -> str:
    """Map stewardship field_path to flat canonical payload key."""
    parts = field_path.split(".", 1)
    if len(parts) != 2:
        return field_path
    prefix, leaf = parts
    if prefix in SCOPE_PREFIXES:
        return leaf
    return field_path


def apply_field_path(payload: dict[str, Any], field_path: str, value: Any) -> None:
    key = field_path_to_payload_key(field_path)
    payload[key] = value


def apply_overrides_to_payload(
    canonical_payload: dict[str, Any],
    overrides: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[int], list[str]]:
    """Deep-copy canonical payload and apply active overrides in stable order."""
    effective = copy.deepcopy(canonical_payload)
    applied_ids: list[int] = []
    override_fields: list[str] = []

    for override in sorted(overrides, key=lambda row: (row["field_path"], int(row["override_id"]))):
        field_path = str(override["field_path"])
        apply_field_path(effective, field_path, override["override_value"])
        applied_ids.append(int(override["override_id"]))
        override_fields.append(field_path)

    if override_fields:
        effective["_override_fields"] = sorted(set(override_fields))

    return effective, applied_ids, override_fields


def compute_payload_hash(*, record_kind: str, entity_scope: str, payload: dict[str, Any]) -> str:
    return compute_canonical_hash(record_kind=record_kind, entity_scope=entity_scope, payload=payload)


def compute_override_version_hash(overrides: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for row in sorted(overrides, key=lambda item: int(item["override_id"])):
        updated = row.get("updated_at")
        if hasattr(updated, "isoformat"):
            stamp = updated.isoformat()
        else:
            stamp = str(updated)
        parts.append(f"{int(row['override_id'])}:{stamp}")
    canonical = "|".join(parts) if parts else "none"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _load_active_overrides_for_scope_keys(
    conn: Connection,
    scope_keys: list[str],
) -> list[dict[str, Any]]:
    if not scope_keys:
        return []
    if not _table_exists(conn, "hr_review_overrides"):
        return []

    rows = conn.execute(
        text(
            """
            SELECT
                override_id, scope_key, field_path, override_value,
                tier, status, updated_at
            FROM public.hr_review_overrides
            WHERE status = 'active'
              AND scope_key = ANY(:scope_keys)
            ORDER BY field_path ASC, override_id ASC
            """
        ),
        {"scope_keys": scope_keys},
    ).mappings().all()
    return [dict(row) for row in rows]


def _resolve_snapshot_id(conn: Connection, snapshot_id: Optional[int]) -> int:
    if snapshot_id is not None:
        return int(snapshot_id)
    active = get_active_snapshot(conn, source_type=SOURCE_TYPE_HR_CONTROL_LIST)
    if not active:
        raise EffectiveCanonicalError("no active canonical snapshot")
    return int(active["snapshot_id"])


def _load_canonical_entry_by_match_key(
    conn: Connection,
    *,
    snapshot_id: int,
    match_key: str,
) -> dict[str, Any]:
    row = conn.execute(
        text(
            """
            SELECT
                entry_id, snapshot_id, entity_scope, record_kind,
                match_key, payload, employee_id, iin
            FROM public.hr_canonical_snapshot_entries
            WHERE snapshot_id = :snapshot_id
              AND match_key = :match_key
            LIMIT 1
            """
        ),
        {"snapshot_id": snapshot_id, "match_key": match_key},
    ).mappings().first()
    if not row:
        raise EffectiveCanonicalError(f"canonical entry not found for match_key={match_key!r}")
    entry = dict(row)
    payload = entry.get("payload")
    if isinstance(payload, str):
        entry["payload"] = json.loads(payload)
    elif payload is None:
        entry["payload"] = {}
    return entry


def _person_scope_key(person_key: str) -> str:
    return f"PERSON:{person_key}"


def _assignment_scope_key(assignment_key: str) -> str:
    return f"ASSIGNMENT:{assignment_key}"


def _derive_document_scope_keys(match_key: str) -> list[str]:
    """Derive override scope keys from normalized record match_key."""
    parts = match_key.split("|")
    if len(parts) < 3:
        return []
    person_key = parts[0]
    record_kind = parts[1]
    source_record_key = parts[2]
    scope_type = {
        "training": "TRAINING",
        "certificate": "CERTIFICATE",
        "category": "CATEGORY",
        "education": "DOCUMENT",
    }.get(record_kind)
    if not scope_type:
        return []
    return [f"{scope_type}:{person_key}:{source_record_key}"]


def _scope_keys_for_entry(
    entry: dict[str, Any],
    *,
    assignment_key: Optional[str] = None,
) -> list[str]:
    match_key = str(entry["match_key"])
    record_kind = str(entry.get("record_kind") or "")

    keys: list[str] = []
    if record_kind == "roster":
        keys.append(_person_scope_key(match_key))
        if assignment_key:
            keys.append(_assignment_scope_key(assignment_key))
    else:
        keys.extend(_derive_document_scope_keys(match_key))
    return keys


def resolve_effective_person(
    conn: Connection,
    *,
    person_key: str,
    assignment_key: Optional[str] = None,
    snapshot_id: Optional[int] = None,
) -> dict[str, Any]:
    """
    Resolve Effective Canonical for a person (roster entry).

    Applies PERSON-scoped overrides and optional ASSIGNMENT-scoped overrides.
    Reads only the active snapshot — never historical snapshots.
    """
    sid = _resolve_snapshot_id(conn, snapshot_id)
    entry = _load_canonical_entry_by_match_key(conn, snapshot_id=sid, match_key=person_key)

    if str(entry.get("record_kind") or "") != "roster":
        raise EffectiveCanonicalError(f"match_key {person_key!r} is not a roster entry")

    canonical_payload = copy.deepcopy(entry["payload"])
    scope_keys = [_person_scope_key(person_key)]
    if assignment_key:
        scope_keys.append(_assignment_scope_key(assignment_key))

    overrides = _load_active_overrides_for_scope_keys(conn, scope_keys)
    effective_payload, applied_ids, _ = apply_overrides_to_payload(canonical_payload, overrides)

    return {
        "snapshot_id": sid,
        "entry_id": int(entry["entry_id"]),
        "match_key": person_key,
        "person_key": person_key,
        "assignment_key": assignment_key,
        "scope_type": "PERSON",
        "record_kind": "roster",
        "entity_scope": entry.get("entity_scope"),
        "canonical_payload": canonical_payload,
        "effective_payload": effective_payload,
        "applied_override_ids": applied_ids,
    }


def resolve_effective_entry(
    conn: Connection,
    *,
    match_key: str,
    assignment_key: Optional[str] = None,
    snapshot_id: Optional[int] = None,
) -> dict[str, Any]:
    """Resolve Effective Canonical for any canonical entry by match_key."""
    sid = _resolve_snapshot_id(conn, snapshot_id)
    entry = _load_canonical_entry_by_match_key(conn, snapshot_id=sid, match_key=match_key)
    canonical_payload = copy.deepcopy(entry["payload"])
    scope_keys = _scope_keys_for_entry(entry, assignment_key=assignment_key)
    overrides = _load_active_overrides_for_scope_keys(conn, scope_keys)
    effective_payload, applied_ids, _ = apply_overrides_to_payload(canonical_payload, overrides)

    record_kind = str(entry.get("record_kind") or "")
    scope_type = "ROSTER" if record_kind == "roster" else scope_keys[0].split(":", 1)[0] if scope_keys else "PERSON"
    person_key = match_key.split("|", 1)[0] if "|" in match_key else match_key

    return {
        "snapshot_id": sid,
        "entry_id": int(entry["entry_id"]),
        "match_key": match_key,
        "person_key": person_key,
        "assignment_key": assignment_key,
        "scope_type": scope_type,
        "record_kind": record_kind,
        "entity_scope": entry.get("entity_scope"),
        "scope_keys": scope_keys,
        "canonical_payload": canonical_payload,
        "effective_payload": effective_payload,
        "applied_override_ids": applied_ids,
    }


def _upsert_effective_cache_row(
    conn: Connection,
    *,
    snapshot_id: int,
    entry: dict[str, Any],
    resolved: dict[str, Any],
    overrides: list[dict[str, Any]],
) -> dict[str, Any]:
    effective_payload = resolved["effective_payload"]
    record_kind = str(entry.get("record_kind") or "")
    entity_scope = str(entry.get("entity_scope") or "employee")
    payload_hash = compute_payload_hash(
        record_kind=record_kind,
        entity_scope=entity_scope,
        payload=effective_payload,
    )
    override_version_hash = compute_override_version_hash(overrides)
    override_ids_json = _serialize_json(resolved["applied_override_ids"])

    match_key = str(entry["match_key"])
    person_key = match_key.split("|", 1)[0] if "|" in match_key else match_key
    scope_type = resolved.get("scope_type") or ("ROSTER" if record_kind == "roster" else "PERSON")
    scope_key = resolved.get("scope_keys", [_person_scope_key(person_key)])[0]

    row = conn.execute(
        text(
            """
            INSERT INTO public.hr_snapshot_effective_entries (
                snapshot_id, canonical_entry_id, scope_type, scope_key,
                person_key, assignment_key, match_key, record_kind,
                effective_payload, payload_hash, override_ids,
                override_version_hash, compute_version, computed_at
            ) VALUES (
                :snapshot_id, :canonical_entry_id, :scope_type, :scope_key,
                :person_key, :assignment_key, :match_key, :record_kind,
                CAST(:effective_payload AS jsonb), :payload_hash, CAST(:override_ids AS jsonb),
                :override_version_hash, :compute_version, now()
            )
            ON CONFLICT (snapshot_id, match_key) DO UPDATE SET
                canonical_entry_id = EXCLUDED.canonical_entry_id,
                scope_type = EXCLUDED.scope_type,
                scope_key = EXCLUDED.scope_key,
                person_key = EXCLUDED.person_key,
                assignment_key = EXCLUDED.assignment_key,
                record_kind = EXCLUDED.record_kind,
                effective_payload = EXCLUDED.effective_payload,
                payload_hash = EXCLUDED.payload_hash,
                override_ids = EXCLUDED.override_ids,
                override_version_hash = EXCLUDED.override_version_hash,
                compute_version = EXCLUDED.compute_version,
                computed_at = now()
            RETURNING effective_entry_id, payload_hash, override_version_hash, computed_at
            """
        ),
        {
            "snapshot_id": snapshot_id,
            "canonical_entry_id": int(entry["entry_id"]),
            "scope_type": scope_type,
            "scope_key": scope_key,
            "person_key": person_key,
            "assignment_key": resolved.get("assignment_key"),
            "match_key": match_key,
            "record_kind": record_kind,
            "effective_payload": _serialize_json(effective_payload),
            "payload_hash": payload_hash,
            "override_ids": override_ids_json,
            "override_version_hash": override_version_hash,
            "compute_version": COMPUTE_VERSION,
        },
    ).mappings().one()

    return {
        "effective_entry_id": int(row["effective_entry_id"]),
        "payload_hash": row["payload_hash"],
        "override_version_hash": row["override_version_hash"],
        "computed_at": row["computed_at"],
        "applied_override_ids": resolved["applied_override_ids"],
        "match_key": match_key,
    }


def refresh_person_effective_entry(
    conn: Connection,
    *,
    person_key: str,
    assignment_key: Optional[str] = None,
    snapshot_id: Optional[int] = None,
) -> dict[str, Any]:
    """Recompute and upsert effective cache row for a person roster entry."""
    if not effective_cache_available(conn):
        raise EffectiveCanonicalError("hr_snapshot_effective_entries is not available")

    resolved = resolve_effective_person(
        conn,
        person_key=person_key,
        assignment_key=assignment_key,
        snapshot_id=snapshot_id,
    )
    sid = int(resolved["snapshot_id"])
    entry = _load_canonical_entry_by_match_key(conn, snapshot_id=sid, match_key=person_key)
    scope_keys = [_person_scope_key(person_key)]
    if assignment_key:
        scope_keys.append(_assignment_scope_key(assignment_key))
    overrides = _load_active_overrides_for_scope_keys(conn, scope_keys)
    return _upsert_effective_cache_row(conn, snapshot_id=sid, entry=entry, resolved=resolved, overrides=overrides)


def refresh_assignment_effective_entry(
    conn: Connection,
    *,
    person_key: str,
    assignment_key: str,
    snapshot_id: Optional[int] = None,
) -> dict[str, Any]:
    """Refresh roster effective entry including assignment-scoped overrides."""
    return refresh_person_effective_entry(
        conn,
        person_key=person_key,
        assignment_key=assignment_key,
        snapshot_id=snapshot_id,
    )


def refresh_snapshot_effective_entries(
    conn: Connection,
    *,
    snapshot_id: Optional[int] = None,
    limit: Optional[int] = None,
) -> dict[str, Any]:
    """Rebuild effective cache for all entries in the active snapshot (idempotent)."""
    if not effective_cache_available(conn):
        raise EffectiveCanonicalError("hr_snapshot_effective_entries is not available")

    sid = _resolve_snapshot_id(conn, snapshot_id)
    sql = """
        SELECT entry_id, snapshot_id, entity_scope, record_kind, match_key, payload
        FROM public.hr_canonical_snapshot_entries
        WHERE snapshot_id = :snapshot_id
        ORDER BY entry_id ASC
    """
    params: dict[str, Any] = {"snapshot_id": sid}
    if limit is not None:
        sql += " LIMIT :limit"
        params["limit"] = int(limit)

    rows = conn.execute(text(sql), params).mappings().all()
    refreshed = 0
    for row in rows:
        entry = dict(row)
        payload = entry.get("payload")
        if isinstance(payload, str):
            entry["payload"] = json.loads(payload)
        elif payload is None:
            entry["payload"] = {}

        resolved = resolve_effective_entry(conn, match_key=str(entry["match_key"]), snapshot_id=sid)
        scope_keys = resolved.get("scope_keys") or []
        overrides = _load_active_overrides_for_scope_keys(conn, scope_keys)
        _upsert_effective_cache_row(conn, snapshot_id=sid, entry=entry, resolved=resolved, overrides=overrides)
        refreshed += 1

    return {"snapshot_id": sid, "refreshed_count": refreshed}


def refresh_person_effective_entry_tx(**kwargs: Any) -> dict[str, Any]:
    with engine.begin() as conn:
        return refresh_person_effective_entry(conn, **kwargs)


def refresh_assignment_effective_entry_tx(**kwargs: Any) -> dict[str, Any]:
    with engine.begin() as conn:
        return refresh_assignment_effective_entry(conn, **kwargs)


def refresh_snapshot_effective_entries_tx(**kwargs: Any) -> dict[str, Any]:
    with engine.begin() as conn:
        return refresh_snapshot_effective_entries(conn, **kwargs)


def resolve_effective_person_tx(**kwargs: Any) -> dict[str, Any]:
    with engine.begin() as conn:
        return resolve_effective_person(conn, **kwargs)
