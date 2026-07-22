"""ADR-040 Phase A — canonical HR snapshot materialization after import promotion."""
from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.models.hr_import import SOURCE_TYPE_HR_CONTROL_LIST
from app.services.department_recoding_service import lookup_recoding
from app.services.hr_import_analytics_service import (
    BatchNotFoundError,
    _ensure_batch_exists,
    _load_staging_rows,
    is_real_employee_row,
    load_row_payload,
)
from app.services.hr_import_education_profile_service import (
    _load_effective_profile_meta,
    _merge_profiles,
    _resolve_merged_profile,
)
from app.services.hr_import_normalized_record_service import (
    REVIEW_STATUS_APPROVED,
    REVIEW_STATUS_PROMOTED,
    _parsed_payload_from_row,
    merge_review_override,
    normalized_records_available,
    norm_title,
)

logger = logging.getLogger(__name__)

SNAPSHOT_STATUS_ACTIVE = "active"
SNAPSHOT_STATUS_SUPERSEDED = "superseded"

RECORD_KIND_ROSTER = "roster"

HASH_VERSION = "v1"

VOLATILE_PAYLOAD_KEYS = frozenset(
    {
        "batch_id",
        "row_id",
        "normalized_record_id",
        "record_id",
        "snapshot_id",
        "entry_id",
        "employee_binding",
        "parsed_values",
        "review_override",
        "review_override_updated_at",
        "review_override_updated_by",
        "reviewed_at",
        "reviewed_by",
        "review_notes",
        "promoted_document_id",
        "promoted_at",
        "promoted_by",
        "created_at",
        "updated_at",
        "imported_at",
        "metadata",
        "parse_method",
        "confidence",
        "fragment_index",
        "source_field",
        "source_text",
        "source_record_key",
        "directory_employee_name",
        "_canonical_correction_fields",
        "provenance",
    }
)

COMBINABLE_ROSTER_FIELDS = frozenset(
    {
        "training_raw",
        "certification_raw",
        "education_raw",
        "degree_raw",
        "experience_raw",
        "note_raw",
    }
)

ROSTER_IMPORT_CORRECTABLE_FIELDS = COMBINABLE_ROSTER_FIELDS | frozenset(
    {"full_name", "department", "position_raw"}
)

ROSTER_COMPARE_FIELDS = frozenset(
    {
        "full_name",
        "iin",
        "birth_date",
        "department",
        "org_unit_id",
        "position_raw",
        "training_raw",
        "certification_raw",
        "education_raw",
        "degree_raw",
        "experience_raw",
        "note_raw",
    }
)

NORMALIZED_COMPARE_FIELDS = frozenset(
    {
        "title",
        "provider",
        "hours",
        "start_date",
        "end_date",
        "issue_date",
        "expiry_date",
        "document_number",
        "specialty_text",
        "medical_specialty_id",
        "file_url",
        "record_kind",
    }
)

APPROVED_NORMALIZED_REVIEW_STATUSES = frozenset({REVIEW_STATUS_APPROVED, REVIEW_STATUS_PROMOTED})


class CanonicalSnapshotError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def _digits_only(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _norm_name(value: str) -> str:
    text_val = (value or "").strip().lower().replace("ё", "е")
    return " ".join(text_val.split())


def _normalize_birth_date(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.date().isoformat()
    text_val = str(value).strip()
    if not text_val:
        return ""
    if re.fullmatch(r"\d{4}", text_val):
        return f"{text_val}-01-01"
    return text_val[:10] if len(text_val) >= 10 else text_val


def canonical_snapshot_available(conn: Connection) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name IN ('hr_control_list_baselines', 'hr_canonical_snapshots')
            UNION ALL
            SELECT 1
            FROM information_schema.views
            WHERE table_schema = 'public'
              AND table_name = 'hr_canonical_snapshots'
            LIMIT 1
            """
        )
    ).first()
    return row is not None


def compute_roster_match_key(
    *,
    employee_id: Optional[int],
    iin: str,
    full_name: str,
    birth_date: Any,
    row_id: Optional[int] = None,
) -> str:
    if employee_id is not None:
        return f"emp:{int(employee_id)}"
    iin_digits = _digits_only(iin)
    if len(iin_digits) == 12:
        return f"iin:{iin_digits}"
    name_norm = _norm_name(full_name)
    dob = _normalize_birth_date(birth_date)
    if name_norm and dob:
        return f"name:{name_norm}|dob:{dob}"
    if row_id is not None:
        return f"row:{int(row_id)}"
    raise CanonicalSnapshotError("cannot compute roster match_key without identity fields")


def compute_normalized_match_key(
    *,
    roster_match_key: str,
    record_kind: str,
    source_record_key: str,
) -> str:
    return f"{roster_match_key}|{record_kind}|{(source_record_key or '').strip()}"


def _normalize_hash_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float, Decimal)):
        if isinstance(value, Decimal):
            return str(value)
        return value
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return normalize_payload_for_hash(value)
    if isinstance(value, list):
        return [_normalize_hash_value(item) for item in value]
    return str(value).strip()


def normalize_payload_for_hash(payload: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key in sorted(payload.keys()):
        if key in VOLATILE_PAYLOAD_KEYS:
            continue
        normalized[key] = _normalize_hash_value(payload[key])
    return normalized


def compute_canonical_hash(*, record_kind: str, entity_scope: str, payload: dict[str, Any]) -> str:
    normalized = normalize_payload_for_hash(payload)
    canonical = "|".join(
        [
            HASH_VERSION,
            record_kind,
            entity_scope,
            json.dumps(normalized, sort_keys=True, ensure_ascii=False, separators=(",", ":")),
        ]
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _serialize_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def compute_correction_fields(
    base: dict[str, Any],
    effective: dict[str, Any],
    *,
    fields: frozenset[str],
) -> list[str]:
    corrected: list[str] = []
    for field in sorted(fields):
        base_val = _normalize_hash_value(base.get(field))
        eff_val = _normalize_hash_value(effective.get(field))
        if base_val != eff_val:
            corrected.append(field)
    return corrected


def build_roster_base_payload(
    conn: Connection,
    *,
    batch_id: int,
    row: dict[str, Any],
) -> dict[str, Any]:
    staging = load_row_payload(conn, batch_id, int(row["row_id"]))
    payload = dict(staging["payload"])
    recoding = lookup_recoding(conn, str(row.get("department") or payload.get("department") or ""))
    birth_date = payload.get("birth_date") or row.get("birth_date")
    return {
        "full_name": str(payload.get("full_name") or row.get("full_name") or "").strip(),
        "iin": _digits_only(str(payload.get("iin") or row.get("iin") or "")),
        "birth_date": _normalize_birth_date(birth_date) or None,
        "department": (
            str(recoding.get("org_unit_name") or "").strip()
            if recoding
            else str(payload.get("department") or row.get("department") or "").strip()
        ),
        "org_unit_id": int(recoding["org_unit_id"]) if recoding and recoding.get("org_unit_id") else row.get("org_unit_id"),
        "position_raw": str(payload.get("position_raw") or row.get("position_raw") or "").strip(),
        "training_raw": str(payload.get("training_raw") or row.get("training_raw") or "").strip(),
        "certification_raw": str(payload.get("certification_raw") or row.get("certification_raw") or "").strip(),
        "education_raw": str(payload.get("education_raw") or row.get("education_raw") or "").strip(),
        "degree_raw": str(payload.get("degree_raw") or row.get("degree_raw") or "").strip(),
        "experience_raw": str(payload.get("experience_raw") or row.get("experience_raw") or "").strip(),
        "note_raw": str(payload.get("note_raw") or row.get("note_raw") or "").strip(),
    }


def build_roster_effective_payload(
    conn: Connection,
    *,
    batch_id: int,
    row: dict[str, Any],
) -> tuple[dict[str, Any], Optional[int], str]:
    staging = load_row_payload(conn, batch_id, int(row["row_id"]))
    payload = dict(staging["payload"])
    metadata = dict(staging.get("metadata") or {})
    meta = _load_effective_profile_meta(
        conn,
        batch_id,
        int(row["row_id"]),
        payload=payload,
        row_employee_id=staging.get("employee_id"),
    )
    profile = _resolve_merged_profile(payload, meta)
    basic = dict(profile.get("basic") or {})
    recoding = lookup_recoding(conn, str(row.get("department") or payload.get("department") or ""))

    employee_id = staging.get("employee_id")
    if employee_id is None:
        from app.services.employee_import_profile_override_service import resolve_directory_employee_id

        employee_id = resolve_directory_employee_id(
            conn,
            row_employee_id=None,
            payload={
                "full_name": basic.get("full_name") or payload.get("full_name") or row.get("full_name"),
                "iin": basic.get("iin") or payload.get("iin") or row.get("iin"),
            },
        )

    full_name = str(basic.get("full_name") or payload.get("full_name") or row.get("full_name") or "").strip()
    iin = _digits_only(str(basic.get("iin") or payload.get("iin") or row.get("iin") or ""))
    birth_date = basic.get("birth_date") or payload.get("birth_date") or row.get("birth_date")

    effective: dict[str, Any] = {
        "full_name": full_name,
        "iin": iin,
        "birth_date": _normalize_birth_date(birth_date) or None,
        "department": (
            str(recoding.get("org_unit_name") or "").strip()
            if recoding
            else str(payload.get("department") or row.get("department") or "").strip()
        ),
        "org_unit_id": int(recoding["org_unit_id"]) if recoding and recoding.get("org_unit_id") else row.get("org_unit_id"),
        "position_raw": str(payload.get("position_raw") or row.get("position_raw") or "").strip(),
        "training_raw": str(payload.get("training_raw") or row.get("training_raw") or "").strip(),
        "certification_raw": str(payload.get("certification_raw") or row.get("certification_raw") or "").strip(),
        "education_raw": str(payload.get("education_raw") or row.get("education_raw") or "").strip(),
        "degree_raw": str(payload.get("degree_raw") or row.get("degree_raw") or "").strip(),
        "experience_raw": str(payload.get("experience_raw") or row.get("experience_raw") or "").strip(),
        "note_raw": str(profile.get("notes_raw") or payload.get("note_raw") or row.get("note_raw") or "").strip(),
        "merged_profile": profile,
    }
    row_override = metadata.get("import_review_override")
    if isinstance(row_override, dict) and row_override:
        for field, value in row_override.items():
            if field not in ROSTER_IMPORT_CORRECTABLE_FIELDS or value is None:
                continue
            effective[field] = str(value).strip()
    correction_fields = compute_correction_fields(
        build_roster_base_payload(conn, batch_id=batch_id, row=row),
        effective,
        fields=ROSTER_COMPARE_FIELDS,
    )
    if correction_fields:
        effective["_canonical_correction_fields"] = correction_fields
    match_key = compute_roster_match_key(
        employee_id=employee_id,
        iin=iin,
        full_name=full_name,
        birth_date=birth_date,
        row_id=int(row["row_id"]),
    )
    return effective, employee_id, match_key


def build_normalized_base_payload(row: dict[str, Any]) -> dict[str, Any]:
    effective = _parsed_payload_from_row(row)
    effective["record_kind"] = str(row.get("record_kind") or "").strip()
    effective["title"] = norm_title(str(effective.get("title") or ""))
    return effective


def build_normalized_effective_payload(row: dict[str, Any]) -> dict[str, Any]:
    merged = merge_review_override(row)
    effective = _parsed_payload_from_row(merged)
    effective["record_kind"] = str(merged.get("record_kind") or "").strip()
    effective["title"] = norm_title(str(effective.get("title") or ""))
    base = build_normalized_base_payload(row)
    from app.services.hr_import_normalized_record_service import OVERRIDABLE_FIELDS_BY_KIND

    record_kind = str(row.get("record_kind") or "").strip()
    allowed = OVERRIDABLE_FIELDS_BY_KIND.get(record_kind, frozenset())
    correction_fields = compute_correction_fields(base, effective, fields=allowed & NORMALIZED_COMPARE_FIELDS)
    if correction_fields:
        effective["_canonical_correction_fields"] = correction_fields
    return effective


def _merge_text_field(primary: str, secondary: str) -> str:
    left = (primary or "").strip()
    right = (secondary or "").strip()
    if not right or right == left:
        return left
    if not left:
        return right
    if right in left:
        return left
    if left in right:
        return right
    return f"{left}; {right}"


def _roster_entry_sort_key(entry: dict[str, Any]) -> tuple[Any, ...]:
    payload = entry.get("payload") or {}
    filled = sum(1 for field in ROSTER_COMPARE_FIELDS if str(payload.get(field) or "").strip())
    return (
        0 if entry.get("employee_id") is not None else 1,
        -filled,
        int(entry.get("source_row_id") or 0),
    )


def _normalized_entry_sort_key(entry: dict[str, Any]) -> tuple[Any, ...]:
    payload = entry.get("payload") or {}
    has_corrections = 1 if payload.get("_canonical_correction_fields") else 0
    filled = sum(
        1
        for field in NORMALIZED_COMPARE_FIELDS
        if payload.get(field) not in (None, "", [], {})
    )
    return (
        0 if entry.get("employee_id") is not None else 1,
        -has_corrections,
        -filled,
        int(entry.get("source_normalized_record_id") or 0),
    )


def _attach_provenance(
    payload: dict[str, Any],
    *,
    source_row_ids: list[int],
    source_normalized_record_ids: list[int],
    duplicate_match_key_merged_count: int,
) -> dict[str, Any]:
    enriched = dict(payload)
    provenance: dict[str, Any] = {
        "source_row_ids": sorted({int(value) for value in source_row_ids if value is not None}),
        "source_normalized_record_ids": sorted(
            {int(value) for value in source_normalized_record_ids if value is not None}
        ),
    }
    if duplicate_match_key_merged_count > 1:
        provenance["duplicate_match_key_merged_count"] = duplicate_match_key_merged_count
    enriched["provenance"] = provenance
    return enriched


def _merge_roster_snapshot_entries(group: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(group, key=_roster_entry_sort_key)
    primary = ordered[0]
    merged_payload = dict(primary["payload"])

    profiles = [
        dict(entry["payload"].get("merged_profile") or {})
        for entry in ordered
        if entry["payload"].get("merged_profile")
    ]
    if len(profiles) > 1:
        merged_payload["merged_profile"] = _merge_profiles(profiles)
    elif profiles:
        merged_payload["merged_profile"] = profiles[0]

    for entry in ordered[1:]:
        secondary = entry["payload"]
        for field in ROSTER_COMPARE_FIELDS:
            if field == "merged_profile":
                continue
            if field in COMBINABLE_ROSTER_FIELDS:
                merged_payload[field] = _merge_text_field(
                    str(merged_payload.get(field) or ""),
                    str(secondary.get(field) or ""),
                )
            elif not str(merged_payload.get(field) or "").strip():
                merged_payload[field] = secondary.get(field)

    source_row_ids = [int(entry["source_row_id"]) for entry in group if entry.get("source_row_id") is not None]
    merged_payload = _attach_provenance(
        merged_payload,
        source_row_ids=source_row_ids,
        source_normalized_record_ids=[],
        duplicate_match_key_merged_count=len(group),
    )

    employee_id = next((entry.get("employee_id") for entry in ordered if entry.get("employee_id") is not None), None)
    match_key = str(primary["match_key"])
    entity_scope = match_key
    return {
        "entity_scope": entity_scope,
        "record_kind": RECORD_KIND_ROSTER,
        "match_key": match_key,
        "canonical_hash": compute_canonical_hash(
            record_kind=RECORD_KIND_ROSTER,
            entity_scope=entity_scope,
            payload=merged_payload,
        ),
        "employee_id": employee_id,
        "iin": merged_payload.get("iin") or None,
        "payload": merged_payload,
        "source_row_id": int(primary["source_row_id"]) if primary.get("source_row_id") is not None else None,
        "source_normalized_record_id": None,
    }


def _merge_normalized_snapshot_entries(group: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(group, key=_normalized_entry_sort_key)
    primary = ordered[0]
    merged_payload = dict(primary["payload"])

    for entry in ordered[1:]:
        secondary = entry["payload"]
        for field in NORMALIZED_COMPARE_FIELDS:
            current = merged_payload.get(field)
            candidate = secondary.get(field)
            if current in (None, "", [], {}) and candidate not in (None, "", [], {}):
                merged_payload[field] = candidate
        correction_fields = sorted(
            set(merged_payload.get("_canonical_correction_fields") or [])
            | set(secondary.get("_canonical_correction_fields") or [])
        )
        if correction_fields:
            merged_payload["_canonical_correction_fields"] = correction_fields

    source_row_ids = [int(entry["source_row_id"]) for entry in group if entry.get("source_row_id") is not None]
    source_normalized_record_ids = [
        int(entry["source_normalized_record_id"])
        for entry in group
        if entry.get("source_normalized_record_id") is not None
    ]
    merged_payload = _attach_provenance(
        merged_payload,
        source_row_ids=source_row_ids,
        source_normalized_record_ids=source_normalized_record_ids,
        duplicate_match_key_merged_count=len(group),
    )

    record_kind = str(primary["record_kind"])
    match_key = str(primary["match_key"])
    entity_scope = str(primary["entity_scope"])
    employee_id = next((entry.get("employee_id") for entry in ordered if entry.get("employee_id") is not None), None)
    return {
        "entity_scope": entity_scope,
        "record_kind": record_kind,
        "match_key": match_key,
        "canonical_hash": compute_canonical_hash(
            record_kind=record_kind,
            entity_scope=entity_scope,
            payload=merged_payload,
        ),
        "employee_id": employee_id,
        "iin": None,
        "payload": merged_payload,
        "source_row_id": int(primary["source_row_id"]) if primary.get("source_row_id") is not None else None,
        "source_normalized_record_id": (
            int(primary["source_normalized_record_id"])
            if primary.get("source_normalized_record_id") is not None
            else None
        ),
    }


def dedupe_snapshot_entries(entries: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Collapse duplicate match_key rows into one merged canonical entry per key."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        grouped.setdefault(str(entry["match_key"]), []).append(entry)

    duplicate_groups = sum(1 for group in grouped.values() if len(group) > 1)
    duplicate_entry_count = sum(len(group) - 1 for group in grouped.values() if len(group) > 1)

    deduped: list[dict[str, Any]] = []
    for match_key in sorted(grouped.keys()):
        group = grouped[match_key]
        if len(group) == 1:
            deduped.append(group[0])
            continue
        record_kind = str(group[0]["record_kind"])
        if record_kind == RECORD_KIND_ROSTER:
            deduped.append(_merge_roster_snapshot_entries(group))
        else:
            deduped.append(_merge_normalized_snapshot_entries(group))

    if duplicate_entry_count > 0:
        logger.info(
            "canonical snapshot deduplicated duplicate match_keys: groups=%s removed=%s",
            duplicate_groups,
            duplicate_entry_count,
        )

    return deduped, duplicate_entry_count


def _build_roster_effective_payload(
    conn: Connection,
    *,
    batch_id: int,
    row: dict[str, Any],
) -> tuple[dict[str, Any], Optional[int], str]:
    return build_roster_effective_payload(conn, batch_id=batch_id, row=row)


def _build_normalized_effective_payload(row: dict[str, Any]) -> dict[str, Any]:
    return build_normalized_effective_payload(row)


def _collect_snapshot_entries(conn: Connection, batch_id: int) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    roster_rows = [r for r in _load_staging_rows(conn, batch_id) if is_real_employee_row(r)]
    for row in roster_rows:
        effective, employee_id, match_key = _build_roster_effective_payload(
            conn,
            batch_id=batch_id,
            row=row,
        )
        entity_scope = match_key
        entries.append(
            {
                "entity_scope": entity_scope,
                "record_kind": RECORD_KIND_ROSTER,
                "match_key": match_key,
                "canonical_hash": compute_canonical_hash(
                    record_kind=RECORD_KIND_ROSTER,
                    entity_scope=entity_scope,
                    payload=effective,
                ),
                "employee_id": employee_id,
                "iin": effective.get("iin") or None,
                "payload": effective,
                "source_row_id": int(row["row_id"]),
                "source_normalized_record_id": None,
            }
        )

    if not normalized_records_available(conn):
        return entries

    roster_match_keys = {
        int(entry["source_row_id"]): str(entry["match_key"])
        for entry in entries
        if entry["record_kind"] == RECORD_KIND_ROSTER and entry["source_row_id"] is not None
    }

    db_rows = conn.execute(
        text(
            """
            SELECT nr.*
            FROM public.hr_import_normalized_records nr
            WHERE nr.batch_id = :batch_id
              AND nr.review_status = ANY(:statuses)
            ORDER BY nr.normalized_record_id
            """
        ),
        {
            "batch_id": batch_id,
            "statuses": list(APPROVED_NORMALIZED_REVIEW_STATUSES),
        },
    ).mappings().all()

    for db_row in db_rows:
        row = dict(db_row)
        row_id = int(row["row_id"])
        roster_match_key = roster_match_keys.get(row_id)
        if roster_match_key is None:
            parent = conn.execute(
                text(
                    """
                    SELECT normalized_payload, employee_id
                    FROM public.hr_import_rows
                    WHERE row_id = :row_id
                    """
                ),
                {"row_id": row_id},
            ).mappings().first()
            if parent:
                payload = dict(parent["normalized_payload"] or {})
                metadata = dict(payload.get("metadata") or {})
                analytics_row = {
                    "iin": str(payload.get("iin") or "").strip(),
                    "classification": str(metadata.get("classification") or ""),
                    "row_type": str(metadata.get("row_type") or ""),
                    "is_employee_roster": bool(metadata.get("is_employee_roster")),
                }
                if is_real_employee_row(analytics_row):
                    _, _, roster_match_key = _build_roster_effective_payload(
                        conn,
                        batch_id=batch_id,
                        row={
                            "row_id": row_id,
                            "full_name": payload.get("full_name"),
                            "iin": payload.get("iin"),
                            "birth_date": payload.get("birth_date"),
                            "department": payload.get("department"),
                            "position_raw": payload.get("position_raw"),
                            "org_unit_id": None,
                        },
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
        effective = _build_normalized_effective_payload(row)
        employee_id = int(row["employee_id"]) if row.get("employee_id") is not None else None
        entity_scope = f"{roster_match_key}|{record_kind}"
        entries.append(
            {
                "entity_scope": entity_scope,
                "record_kind": record_kind,
                "match_key": match_key,
                "canonical_hash": compute_canonical_hash(
                    record_kind=record_kind,
                    entity_scope=entity_scope,
                    payload=effective,
                ),
                "employee_id": employee_id,
                "iin": None,
                "payload": effective,
                "source_row_id": row_id,
                "source_normalized_record_id": int(row["normalized_record_id"]),
            }
        )
    return entries


def _get_snapshot_by_batch(conn: Connection, batch_id: int) -> Optional[dict[str, Any]]:
    from app.services.hr_baseline_service import _get_baseline_by_batch

    baseline = _get_baseline_by_batch(conn, batch_id)
    if baseline is None:
        return None
    return {
        "snapshot_id": int(baseline["baseline_id"]),
        "source_batch_id": baseline.get("source_batch_id"),
        "entry_count": int(baseline["entry_count"]),
        "promoted_by": int(baseline.get("published_by") or baseline["promoted_by"]),
        "promoted_at": baseline.get("published_at") or baseline.get("promoted_at"),
    }


def get_active_snapshot(conn: Connection, *, source_type: str = SOURCE_TYPE_HR_CONTROL_LIST) -> Optional[dict[str, Any]]:
    from app.services.hr_baseline_service import baseline_tables_available, resolve_effective_baseline

    if not baseline_tables_available(conn):
        return None
    row = conn.execute(
        text(
            """
            SELECT report_period
            FROM public.hr_control_list_baselines
            WHERE deleted_at IS NULL
              AND source_type = :source_type
            ORDER BY report_period DESC, published_at DESC, baseline_id DESC
            LIMIT 1
            """
        ),
        {"source_type": source_type},
    ).mappings().first()
    if row is None:
        return None
    period = row["report_period"]
    if isinstance(period, datetime):
        period = period.date()
    baseline = resolve_effective_baseline(conn, period)
    if baseline is None:
        return None
    return {
        "snapshot_id": int(baseline["baseline_id"]),
        "source_batch_id": baseline.get("source_batch_id"),
        "entry_count": int(baseline["entry_count"]),
        "promoted_by": int(baseline.get("published_by") or baseline["promoted_by"]),
        "promoted_at": baseline.get("published_at") or baseline.get("promoted_at"),
    }


def build_canonical_snapshot_from_batch(
    conn: Connection,
    batch_id: int,
    *,
    promoted_by: int,
    force: bool = False,
) -> dict[str, Any]:
    from app.services.hr_baseline_service import publish_baseline_from_batch

    result = publish_baseline_from_batch(
        conn,
        batch_id,
        published_by=promoted_by,
        force=force,
    )
    if result.get("created"):
        return {
            "created": True,
            "snapshot_id": int(result["baseline_id"]),
            "source_batch_id": result.get("source_batch_id"),
            "entry_count": int(result["entry_count"]),
            "duplicate_match_keys_merged": result.get("duplicate_match_keys_merged", 0),
            "superseded_snapshot_id": result.get("superseded_snapshot_id"),
            "change_events": result.get("change_events"),
        }
    return {
        "created": False,
        "snapshot_id": int(result["baseline_id"]),
        "source_batch_id": result.get("source_batch_id"),
        "entry_count": int(result["entry_count"]),
    }


def refresh_canonical_snapshot_after_promotion(
    conn: Connection,
    batch_id: int,
    *,
    promoted_by: int,
) -> Optional[dict[str, Any]]:
    from app.services.hr_baseline_service import baseline_tables_available, publish_baseline_from_batch

    if not baseline_tables_available(conn):
        return None
    try:
        return publish_baseline_from_batch(conn, batch_id, published_by=promoted_by, force=True)
    except Exception:
        logger.exception("failed to refresh canonical snapshot for batch_id=%s", batch_id)
        raise
