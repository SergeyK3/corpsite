"""WP-TD-005 stage 2 tombstone writer; intentionally not wired to execution."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Iterable, Mapping
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.services.test_personnel_deletion_service import TestPersonnelDeletionError


TOMBSTONE_SCHEMA_VERSION = "WP-TD-TOMBSTONE/v1"
EARLY_LIFECYCLE_ACTIONS = frozenset({
    "registered",
    "intake_link_issued",
    "intake_opened",
    "intake_submitted",
    "intake_edited_on_behalf",
})
_POSITIVE_INTEGER = re.compile(r"^[1-9][0-9]{0,18}$")


def _canonical_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _canonical_value(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    if isinstance(value, datetime):
        aware = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        return aware.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (Decimal, UUID)):
        return str(value)
    return value


def canonical_digest(value: Any) -> str:
    payload = json.dumps(
        _canonical_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _technical_actor_id(value: Any) -> int | None:
    if isinstance(value, int) and value > 0:
        return value
    candidate = str(value or "").strip()
    return int(candidate) if _POSITIVE_INTEGER.fullmatch(candidate) else None


def _insert_idempotent(
    conn: Connection,
    *,
    table: str,
    source_column: str,
    values: Mapping[str, Any],
) -> dict[str, Any]:
    columns = tuple(values)
    returned = conn.execute(text(f"""INSERT INTO public.{table}({','.join(columns)})
        VALUES({','.join(':' + column for column in columns)})
        ON CONFLICT ({source_column}) DO NOTHING
        RETURNING *"""), dict(values)).mappings().one_or_none()
    if returned is not None:
        return dict(returned)
    existing = conn.execute(text(f"""SELECT * FROM public.{table}
        WHERE {source_column}=:{source_column}"""), {
            source_column: values[source_column],
        }).mappings().one()
    if any(_canonical_value(existing[column]) != _canonical_value(value) for column, value in values.items()):
        raise TestPersonnelDeletionError(
            "TD_TOMBSTONE_SOURCE_CONFLICT",
            "Source was already tombstoned with different request or digest data.",
            409,
        )
    return dict(existing)


def capture_record_event_tombstone(
    conn: Connection, *, request_id: UUID | str, source_event_id: int,
) -> dict[str, Any]:
    row = conn.execute(text("""SELECT event.*
        FROM public.personnel_record_events event
        WHERE event.event_id=:source_id
          AND EXISTS (
              SELECT 1 FROM public.test_personnel_deletion_manifest_v2_targets target
              WHERE target.request_id=:request_id AND target.person_id=event.person_id
          )
        FOR SHARE OF event"""), {
            "source_id": int(source_event_id), "request_id": request_id,
        }).mappings().one_or_none()
    if row is None:
        raise TestPersonnelDeletionError(
            "TD_TOMBSTONE_SOURCE_NOT_IN_MANIFEST",
            "Personnel record event is missing or outside the request manifest.",
            409,
        )
    payload_digest = canonical_digest(row["event_payload"])
    actor_technical_id = _technical_actor_id(row["actor_id"])
    digest = canonical_digest({
        "schema": TOMBSTONE_SCHEMA_VERSION,
        "source": "personnel_record_events",
        "source_event_id": int(row["event_id"]),
        "event_type": str(row["event_type"]),
        "source_occurred_at": row["event_at"],
        "actor_technical_id": actor_technical_id,
        "domain_code": row["domain_code"],
        "record_table_name": row["record_table_name"],
        "record_id": int(row["record_id"]),
        "migration_run_id": row["migration_run_id"],
        "migration_item_id": row["migration_item_id"],
        "event_payload_digest": payload_digest,
    })
    return _insert_idempotent(
        conn,
        table="test_personnel_deletion_record_event_tombstones",
        source_column="source_event_id",
        values={
            "request_id": request_id,
            "source_event_id": int(row["event_id"]),
            "event_type": str(row["event_type"]),
            "source_occurred_at": row["event_at"],
            "actor_technical_id": actor_technical_id,
            "event_payload_digest": payload_digest,
            "canonical_digest": digest,
        },
    )


def capture_command_tombstone(
    conn: Connection, *, request_id: UUID | str,
    source_command_execution_id: int | None = None,
    source_command_id: str | None = None,
) -> dict[str, Any]:
    has_technical_id = bool(conn.execute(text("""SELECT EXISTS(
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='public' AND table_name='ppr_command_executions'
          AND column_name='command_execution_id')""")).scalar_one())
    if has_technical_id and source_command_execution_id is None:
        raise TestPersonnelDeletionError(
            "TD_TOMBSTONE_TECHNICAL_SOURCE_REQUIRED",
            "A server-generated command execution identity is required.", 409,
        )
    source_predicate = (
        "command.command_execution_id=:source_id" if has_technical_id
        else "command.command_id=:source_id"
    )
    source_value: Any = (
        int(source_command_execution_id) if has_technical_id else str(source_command_id or "")
    )
    row = conn.execute(text("""SELECT command.*
        FROM public.ppr_command_executions command
        WHERE """ + source_predicate + """
          AND EXISTS (
              SELECT 1 FROM public.test_personnel_deletion_manifest_v2_targets target
              WHERE target.request_id=:request_id AND target.person_id=command.person_id
          )
        FOR SHARE OF command"""), {
            "source_id": source_value, "request_id": request_id,
        }).mappings().one_or_none()
    if row is None:
        raise TestPersonnelDeletionError(
            "TD_TOMBSTONE_SOURCE_NOT_IN_MANIFEST",
            "PPR command is missing or outside the request manifest.",
            409,
        )
    request_digest = canonical_digest(row["request_fingerprint"])
    result_digest = canonical_digest(row["result_payload"])
    source_reference_digest = hashlib.sha256(str(row["command_id"]).encode("utf-8")).hexdigest()
    if not has_technical_id:
        # Compatibility for tests pinned to the historical stage-2 schema.
        digest = canonical_digest({
            "schema": TOMBSTONE_SCHEMA_VERSION, "source": "ppr_command_executions",
            "source_command_id": str(row["command_id"]), "command_type": str(row["command_type"]),
            "command_status": str(row["status"]), "source_created_at": row["created_at"],
            "source_completed_at": row["completed_at"], "request_digest": request_digest,
            "result_digest": result_digest,
        })
        return _insert_idempotent(
            conn, table="test_personnel_deletion_command_tombstones",
            source_column="source_command_id", values={
                "request_id": request_id, "source_command_id": str(row["command_id"]),
                "command_type": str(row["command_type"]), "command_status": str(row["status"]),
                "source_created_at": row["created_at"], "source_completed_at": row["completed_at"],
                "request_digest": request_digest, "result_digest": result_digest,
                "canonical_digest": digest,
            },
        )
    digest = canonical_digest({
        "schema": TOMBSTONE_SCHEMA_VERSION,
        "source": "ppr_command_executions",
        "source_command_execution_id": int(row["command_execution_id"]),
        "source_reference_digest": source_reference_digest,
        "command_type": str(row["command_type"]),
        "command_status": str(row["status"]),
        "source_created_at": row["created_at"],
        "source_completed_at": row["completed_at"],
        "request_digest": request_digest,
        "result_digest": result_digest,
    })
    return _insert_idempotent(
        conn,
        table="test_personnel_deletion_command_tombstones",
        source_column="source_command_execution_id",
        values={
            "request_id": request_id,
            "source_command_execution_id": int(row["command_execution_id"]),
            "source_reference_digest": source_reference_digest,
            "command_type": str(row["command_type"]),
            "command_status": str(row["status"]),
            "source_created_at": row["created_at"],
            "source_completed_at": row["completed_at"],
            "request_digest": request_digest,
            "result_digest": result_digest,
            "canonical_digest": digest,
        },
    )


def capture_lifecycle_tombstone(
    conn: Connection, *, request_id: UUID | str, source_audit_id: int,
) -> dict[str, Any]:
    row = conn.execute(text("""SELECT audit.*
        FROM public.personnel_application_lifecycle_audit audit
        WHERE audit.audit_id=:source_id
          AND EXISTS (
              SELECT 1 FROM public.test_personnel_deletion_manifest_v2_targets target
              WHERE target.request_id=:request_id
                AND audit.application_id=ANY(target.application_ids)
          )
        FOR SHARE OF audit"""), {
            "source_id": int(source_audit_id), "request_id": request_id,
        }).mappings().one_or_none()
    if row is None:
        raise TestPersonnelDeletionError(
            "TD_TOMBSTONE_SOURCE_NOT_IN_MANIFEST",
            "Lifecycle event is missing or outside the request manifest.",
            409,
        )
    action = str(row["action"])
    if action not in EARLY_LIFECYCLE_ACTIONS:
        raise TestPersonnelDeletionError(
            "TD_TOMBSTONE_LIFECYCLE_ACTION_FORBIDDEN",
            "Only approved early lifecycle actions may be tombstoned.",
            409,
        )
    metadata_digest = canonical_digest(row["metadata"])
    digest = canonical_digest({
        "schema": TOMBSTONE_SCHEMA_VERSION,
        "source": "personnel_application_lifecycle_audit",
        "source_audit_id": int(row["audit_id"]),
        "source_application_id": int(row["application_id"]),
        "lifecycle_action": action,
        "previous_status": row["previous_status"],
        "new_status": row["new_status"],
        "source_occurred_at": row["created_at"],
        "actor_technical_id": row["actor_user_id"],
        "comment_digest": canonical_digest(row["comment"]),
        "metadata_digest": metadata_digest,
    })
    return _insert_idempotent(
        conn,
        table="test_personnel_deletion_lifecycle_tombstones",
        source_column="source_audit_id",
        values={
            "request_id": request_id,
            "source_audit_id": int(row["audit_id"]),
            "source_application_id": int(row["application_id"]),
            "lifecycle_action": action,
            "previous_status": row["previous_status"],
            "new_status": row["new_status"],
            "source_occurred_at": row["created_at"],
            "actor_technical_id": row["actor_user_id"],
            "metadata_digest": metadata_digest,
            "canonical_digest": digest,
        },
    )


def capture_tombstones(
    conn: Connection,
    *,
    request_id: UUID | str,
    record_event_ids: Iterable[int] = (),
    command_execution_ids: Iterable[int] = (),
    command_ids: Iterable[str] = (),
    lifecycle_audit_ids: Iterable[int] = (),
) -> dict[str, list[dict[str, Any]]]:
    """Capture exact source sets in the caller-owned transaction; never commits."""
    technical_command_ids = sorted(set(map(int, command_execution_ids)))
    legacy_command_ids = sorted(set(map(str, command_ids)))
    return {
        "record_events": [
            capture_record_event_tombstone(conn, request_id=request_id, source_event_id=source_id)
            for source_id in sorted(set(map(int, record_event_ids)))
        ],
        "commands": [
            capture_command_tombstone(
                conn, request_id=request_id, source_command_execution_id=source_id,
            )
            for source_id in technical_command_ids
        ] if technical_command_ids else [
            capture_command_tombstone(conn, request_id=request_id, source_command_id=source_id)
            for source_id in legacy_command_ids
        ],
        "lifecycle": [
            capture_lifecycle_tombstone(conn, request_id=request_id, source_audit_id=source_id)
            for source_id in sorted(set(map(int, lifecycle_audit_ids)))
        ],
    }
