"""ADR-043 Phase B3 — backfill legacy overrides into hr_review_overrides."""
from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.engine import engine
from app.services.hr_canonical_snapshot_service import get_active_snapshot
from app.services.hr_import_normalized_record_service import OVERRIDABLE_FIELDS_BY_KIND
from app.services.hr_override_stewardship_service import resolve_stewardship_rule
from app.services.hr_review_override_service import create_override, review_overrides_available

ROSTER_FIELD_TO_PATH: dict[str, tuple[str, str]] = {
    "full_name": ("identity.full_name", "PERSON"),
    "iin": ("identity.iin", "PERSON"),
    "birth_date": ("identity.birth_date", "PERSON"),
    "department": ("roster.department", "ASSIGNMENT"),
    "org_unit_id": ("roster.org_unit_id", "ASSIGNMENT"),
    "position_raw": ("roster.position_raw", "ASSIGNMENT"),
    "note_raw": ("note.text", "PERSON"),
}

RECORD_KIND_TO_SCOPE: dict[str, str] = {
    "training": "TRAINING",
    "certificate": "CERTIFICATE",
    "category": "CATEGORY",
    "education": "DOCUMENT",
}

RECORD_KIND_TO_PATH_PREFIX: dict[str, str] = {
    "training": "training",
    "certificate": "certificate",
    "category": "category",
    "education": "education",
}


class BackfillError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def _serialize_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _parse_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        return json.loads(value) if value.strip() else {}
    return {}


def _override_exists(conn: Connection, *, scope_key: str, field_path: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM public.hr_review_overrides
            WHERE scope_key = :scope_key
              AND field_path = :field_path
              AND status IN ('active', 'pending_approval')
            LIMIT 1
            """
        ),
        {"scope_key": scope_key, "field_path": field_path},
    ).first()
    return row is not None


def _backfill_key(source: str, *parts: str) -> str:
    return f"{source}|{'|'.join(parts)}"


def _plan_canonical_correction_backfill(
    conn: Connection,
    *,
    snapshot_id: int,
    promoted_by: int,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT entry_id, match_key, record_kind, payload, employee_id
            FROM public.hr_canonical_snapshot_entries
            WHERE snapshot_id = :snapshot_id
            """
        ),
        {"snapshot_id": snapshot_id},
    ).mappings().all()

    planned: list[dict[str, Any]] = []
    for row in rows:
        payload = _parse_payload(row["payload"])
        corrected = payload.get("_canonical_correction_fields") or []
        if not isinstance(corrected, list) or not corrected:
            continue

        match_key = str(row["match_key"])
        record_kind = str(row.get("record_kind") or "")

        for field_name in corrected:
            field_name = str(field_name)
            override_value = payload.get(field_name)
            if override_value is None:
                continue

            person_key_part = match_key
            if record_kind == "roster":
                mapping = ROSTER_FIELD_TO_PATH.get(field_name)
                if not mapping:
                    continue
                field_path, scope_type = mapping
                if scope_type == "PERSON":
                    scope_key = f"PERSON:{match_key}"
                else:
                    assignment_key = f"{match_key}|primary"
                    scope_key = f"ASSIGNMENT:{assignment_key}"
            else:
                scope_type_name = RECORD_KIND_TO_SCOPE.get(record_kind)
                prefix = RECORD_KIND_TO_PATH_PREFIX.get(record_kind)
                if not scope_type_name or not prefix:
                    continue
                parts = match_key.split("|")
                if len(parts) < 3:
                    continue
                person_key_part = parts[0]
                source_record_key = parts[2]
                field_path = f"{prefix}.{field_name}"
                scope_type = scope_type_name
                scope_key = f"{scope_type}:{person_key_part}:{source_record_key}"

            if _override_exists(conn, scope_key=scope_key, field_path=field_path):
                planned.append(
                    {
                        "action": "skip_duplicate",
                        "source": "canonical_correction_fields",
                        "scope_key": scope_key,
                        "field_path": field_path,
                        "backfill_key": _backfill_key("canonical", str(row["entry_id"]), field_path),
                    }
                )
                continue

            rule = resolve_stewardship_rule(conn, field_path=field_path, scope_type=scope_type)
            planned.append(
                {
                    "action": "create",
                    "source": "canonical_correction_fields",
                    "scope_type": scope_type,
                    "scope_key": scope_key,
                    "field_path": field_path,
                    "override_value": override_value,
                    "canonical_value": override_value,
                    "tier": int(rule["required_tier"]),
                    "owner_domain": rule["owner_domain"],
                    "person_key": person_key_part,
                    "record_kind": record_kind or None,
                    "source_snapshot_id": snapshot_id,
                    "created_by_user_id": promoted_by,
                    "justification": "Backfill from _canonical_correction_fields on active snapshot",
                    "creation_channel": "backfill",
                    "backfill_key": _backfill_key("canonical", str(row["entry_id"]), field_path),
                }
            )
    return planned


def _plan_review_override_json_backfill(
    conn: Connection,
    *,
    default_created_by_user_id: int,
) -> list[dict[str, Any]]:
    if not _column_exists(conn, "hr_import_normalized_records", "review_override_json"):
        return []

    rows = conn.execute(
        text(
            """
            SELECT DISTINCT ON (source_record_key, record_kind)
                normalized_record_id, record_kind, source_record_key,
                review_override_json, batch_id, employee_id,
                title, provider, hours, issue_date, expiry_date,
                document_number, specialty_text, medical_specialty_id
            FROM public.hr_import_normalized_records
            WHERE review_override_json IS NOT NULL
              AND review_status IN ('approved', 'promoted')
            ORDER BY source_record_key, record_kind, normalized_record_id DESC
            """
        )
    ).mappings().all()

    planned: list[dict[str, Any]] = []
    for row in rows:
        override = _parse_payload(row.get("review_override_json"))
        if not override:
            continue

        record_kind = str(row.get("record_kind") or "")
        scope_type = RECORD_KIND_TO_SCOPE.get(record_kind)
        prefix = RECORD_KIND_TO_PATH_PREFIX.get(record_kind)
        if not scope_type or not prefix:
            continue

        source_record_key = str(row.get("source_record_key") or "")
        person_key = ""
        if row.get("employee_id") is not None:
            person_key = f"emp:{int(row['employee_id'])}"
        if not person_key:
            continue

        scope_key = f"{scope_type}:{person_key}:{source_record_key}"

        for field_name, override_value in override.items():
            field_path = f"{prefix}.{field_name}"
            if _override_exists(conn, scope_key=scope_key, field_path=field_path):
                planned.append(
                    {
                        "action": "skip_duplicate",
                        "source": "review_override_json",
                        "scope_key": scope_key,
                        "field_path": field_path,
                        "backfill_key": _backfill_key(
                            "review_json", str(row["normalized_record_id"]), field_path
                        ),
                    }
                )
                continue

            rule = resolve_stewardship_rule(conn, field_path=field_path, scope_type=scope_type)
            planned.append(
                {
                    "action": "create",
                    "source": "review_override_json",
                    "scope_type": scope_type,
                    "scope_key": scope_key,
                    "field_path": field_path,
                    "override_value": override_value,
                    "tier": int(rule["required_tier"]),
                    "owner_domain": rule["owner_domain"],
                    "person_key": person_key,
                    "record_kind": record_kind,
                    "normalized_record_id": int(row["normalized_record_id"]),
                    "source_batch_id": row.get("batch_id"),
                    "source_normalized_record_id": int(row["normalized_record_id"]),
                    "created_by_user_id": default_created_by_user_id,
                    "justification": "Backfill from review_override_json on approved normalized record",
                    "creation_channel": "backfill",
                    "backfill_key": _backfill_key(
                        "review_json", str(row["normalized_record_id"]), field_path
                    ),
                }
            )
    return planned


def _column_exists(conn: Connection, table: str, column: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = :table
              AND column_name = :column
            LIMIT 1
            """
        ),
        {"table": table, "column": column},
    ).first()
    return row is not None


def preview_backfill(conn: Connection, *, default_created_by_user_id: int = 1) -> dict[str, Any]:
    """Dry-run preview of backfill actions without mutations."""
    if not review_overrides_available(conn):
        raise BackfillError("hr_review_overrides is not available")

    active = get_active_snapshot(conn)
    if not active:
        return {
            "snapshot_id": None,
            "planned": [],
            "create_count": 0,
            "skip_count": 0,
        }

    snapshot_id = int(active["snapshot_id"])
    promoted_by = int(active.get("promoted_by") or 1)

    planned = _plan_canonical_correction_backfill(
        conn, snapshot_id=snapshot_id, promoted_by=promoted_by
    )
    planned.extend(
        _plan_review_override_json_backfill(
            conn, default_created_by_user_id=default_created_by_user_id
        )
    )

    create_items = [item for item in planned if item["action"] == "create"]
    skip_items = [item for item in planned if item["action"] == "skip_duplicate"]

    return {
        "snapshot_id": snapshot_id,
        "planned": planned,
        "create_count": len(create_items),
        "skip_count": len(skip_items),
    }


def execute_backfill(
    conn: Connection,
    *,
    dry_run: bool = True,
    default_created_by_user_id: int = 1,
) -> dict[str, Any]:
    """
    Backfill legacy overrides into hr_review_overrides + history (CREATED).

    Idempotent: skips scope_key+field_path with existing active/pending override.
    """
    preview = preview_backfill(conn, default_created_by_user_id=default_created_by_user_id)
    if dry_run:
        return {
            **preview,
            "dry_run": True,
            "created_count": 0,
            "created_override_ids": [],
        }

    created_ids: list[int] = []
    for item in preview["planned"]:
        if item["action"] != "create":
            continue

        created_by = int(item.get("created_by_user_id") or default_created_by_user_id)
        result = create_override(
            conn,
            scope_type=item["scope_type"],
            scope_key=item["scope_key"],
            field_path=item["field_path"],
            override_value=item["override_value"],
            created_by_user_id=created_by,
            tier=int(item["tier"]),
            owner_domain=item["owner_domain"],
            creation_channel=item.get("creation_channel", "backfill"),
            canonical_value=item.get("canonical_value"),
            justification=item.get("justification"),
            person_key=item.get("person_key"),
            record_kind=item.get("record_kind"),
            normalized_record_id=item.get("normalized_record_id"),
            source_batch_id=item.get("source_batch_id"),
            source_normalized_record_id=item.get("source_normalized_record_id"),
            source_snapshot_id=item.get("source_snapshot_id"),
            metadata={"backfill_key": item["backfill_key"], "backfill_source": item["source"]},
            skip_duplicate_check=True,
        )
        created_ids.append(int(result["override_id"]))

    return {
        **preview,
        "dry_run": False,
        "created_count": len(created_ids),
        "created_override_ids": created_ids,
    }


def preview_backfill_tx() -> dict[str, Any]:
    with engine.begin() as conn:
        return preview_backfill(conn)


def execute_backfill_tx(*, dry_run: bool = True, default_created_by_user_id: int = 1) -> dict[str, Any]:
    with engine.begin() as conn:
        return execute_backfill(
            conn,
            dry_run=dry_run,
            default_created_by_user_id=default_created_by_user_id,
        )
