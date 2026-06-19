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
        "iin_masked",
        "directory_employee_name",
        "_canonical_correction_fields",
    }
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
    row = conn.execute(
        text(
            """
            SELECT snapshot_id, source_batch_id, version, source_type, status,
                   entry_count, promoted_by, promoted_at
            FROM public.hr_canonical_snapshots
            WHERE source_batch_id = :batch_id
            LIMIT 1
            """
        ),
        {"batch_id": batch_id},
    ).mappings().first()
    return dict(row) if row else None


def get_active_snapshot(conn: Connection, *, source_type: str = SOURCE_TYPE_HR_CONTROL_LIST) -> Optional[dict[str, Any]]:
    if not canonical_snapshot_available(conn):
        return None
    row = conn.execute(
        text(
            """
            SELECT snapshot_id, source_batch_id, version, source_type, status,
                   entry_count, promoted_by, promoted_at
            FROM public.hr_canonical_snapshots
            WHERE source_type = :source_type
              AND status = :status
            LIMIT 1
            """
        ),
        {"source_type": source_type, "status": SNAPSHOT_STATUS_ACTIVE},
    ).mappings().first()
    return dict(row) if row else None


def _next_snapshot_version(conn: Connection, source_type: str) -> int:
    row = conn.execute(
        text(
            """
            SELECT COALESCE(MAX(version), 0) + 1 AS next_version
            FROM public.hr_canonical_snapshots
            WHERE source_type = :source_type
            """
        ),
        {"source_type": source_type},
    ).mappings().first()
    return int(row["next_version"]) if row else 1


def build_canonical_snapshot_from_batch(
    conn: Connection,
    batch_id: int,
    *,
    promoted_by: int,
    force: bool = False,
) -> dict[str, Any]:
    if not canonical_snapshot_available(conn):
        raise CanonicalSnapshotError("hr_canonical_snapshots is not available")

    _ensure_batch_exists(conn, batch_id)
    existing = _get_snapshot_by_batch(conn, batch_id)
    if existing and not force:
        return {
            "created": False,
            "snapshot_id": int(existing["snapshot_id"]),
            "source_batch_id": int(existing["source_batch_id"]),
            "version": int(existing["version"]),
            "status": existing["status"],
            "entry_count": int(existing["entry_count"]),
        }

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
    entries = _collect_snapshot_entries(conn, batch_id)
    version = _next_snapshot_version(conn, source_type)

    prior_active = get_active_snapshot(conn, source_type=source_type)
    if prior_active and not (existing and force):
        conn.execute(
            text(
                """
                UPDATE public.hr_canonical_snapshots
                SET status = :superseded,
                    superseded_at = NOW()
                WHERE snapshot_id = :prior_snapshot_id
                  AND status = :active
                """
            ),
            {
                "superseded": SNAPSHOT_STATUS_SUPERSEDED,
                "prior_snapshot_id": int(prior_active["snapshot_id"]),
                "active": SNAPSHOT_STATUS_ACTIVE,
            },
        )

    snapshot_id = conn.execute(
        text(
            """
            INSERT INTO public.hr_canonical_snapshots (
                source_batch_id,
                version,
                source_type,
                status,
                entry_count,
                promoted_by,
                promoted_at
            )
            VALUES (
                :source_batch_id,
                :version,
                :source_type,
                :status,
                :entry_count,
                :promoted_by,
                NOW()
            )
            RETURNING snapshot_id
            """
        ),
        {
            "source_batch_id": batch_id,
            "version": version,
            "source_type": source_type,
            "status": SNAPSHOT_STATUS_ACTIVE,
            "entry_count": len(entries),
            "promoted_by": int(promoted_by),
        },
    ).scalar_one()

    for entry in entries:
        conn.execute(
            text(
                """
                INSERT INTO public.hr_canonical_snapshot_entries (
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
                )
                VALUES (
                    :snapshot_id,
                    :entity_scope,
                    :record_kind,
                    :match_key,
                    :canonical_hash,
                    :employee_id,
                    :iin,
                    CAST(:payload AS JSONB),
                    :source_row_id,
                    :source_normalized_record_id
                )
                """
            ),
            {
                "snapshot_id": int(snapshot_id),
                "entity_scope": entry["entity_scope"],
                "record_kind": entry["record_kind"],
                "match_key": entry["match_key"],
                "canonical_hash": entry["canonical_hash"],
                "employee_id": entry["employee_id"],
                "iin": entry["iin"],
                "payload": _serialize_json(entry["payload"]),
                "source_row_id": entry["source_row_id"],
                "source_normalized_record_id": entry["source_normalized_record_id"],
            },
        )

    if prior_active and int(prior_active["snapshot_id"]) != int(snapshot_id):
        conn.execute(
            text(
                """
                UPDATE public.hr_canonical_snapshots
                SET superseded_by_snapshot_id = :new_snapshot_id
                WHERE snapshot_id = :prior_snapshot_id
                """
            ),
            {
                "new_snapshot_id": int(snapshot_id),
                "prior_snapshot_id": int(prior_active["snapshot_id"]),
            },
        )

    result = {
        "created": True,
        "snapshot_id": int(snapshot_id),
        "source_batch_id": batch_id,
        "version": version,
        "status": SNAPSHOT_STATUS_ACTIVE,
        "entry_count": len(entries),
        "superseded_snapshot_id": int(prior_active["snapshot_id"]) if prior_active else None,
    }

    from app.services.hr_snapshot_comparison_service import maybe_materialize_change_events_after_snapshot

    change_events_result = maybe_materialize_change_events_after_snapshot(conn, result)
    if change_events_result is not None:
        result["change_events"] = change_events_result

    return result


def refresh_canonical_snapshot_after_promotion(
    conn: Connection,
    batch_id: int,
    *,
    promoted_by: int,
) -> Optional[dict[str, Any]]:
    if not canonical_snapshot_available(conn):
        return None
    try:
        return build_canonical_snapshot_from_batch(conn, batch_id, promoted_by=promoted_by)
    except Exception:
        logger.exception("failed to refresh canonical snapshot for batch_id=%s", batch_id)
        raise
