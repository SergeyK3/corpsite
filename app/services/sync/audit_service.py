"""ADR-038 Phase D.3 — HR sync audit log (export / preview / apply history)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

SyncAuditOperation = Literal["export", "preview", "apply"]


@dataclass
class SyncAuditLogEntry:
    sync_audit_id: int
    happened_at: datetime
    actor_user_id: Optional[int]
    actor_login: Optional[str]
    operation: SyncAuditOperation
    dry_run: bool
    package_name: Optional[str]
    validation_ok: Optional[bool]
    notes: Optional[str]
    summary: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def sync_audit_log_available(conn: Connection) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = 'hr_sync_audit_log'
            LIMIT 1
            """
        )
    ).first()
    return row is not None


def _parse_jsonb(value: Any, *, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, str):
        return json.loads(value)
    return value


def _iso_datetime(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def insert_sync_audit_log(
    conn: Connection,
    *,
    operation: SyncAuditOperation,
    actor_user_id: Optional[int],
    actor_login: Optional[str],
    dry_run: bool = False,
    package_name: Optional[str] = None,
    validation_ok: Optional[bool] = None,
    notes: Optional[str] = None,
    summary: Optional[dict[str, Any]] = None,
    context: Optional[dict[str, Any]] = None,
    warnings: Optional[list[str]] = None,
    errors: Optional[list[str]] = None,
) -> Optional[int]:
    """Persist sync admin operation. Returns sync_audit_id or None if table unavailable."""
    if not sync_audit_log_available(conn):
        return None

    row = conn.execute(
        text(
            """
            INSERT INTO public.hr_sync_audit_log (
                actor_user_id,
                actor_login,
                operation,
                dry_run,
                package_name,
                validation_ok,
                notes,
                summary,
                context,
                warnings,
                errors
            )
            VALUES (
                :actor_user_id,
                :actor_login,
                :operation,
                :dry_run,
                :package_name,
                :validation_ok,
                :notes,
                CAST(:summary AS JSONB),
                CAST(:context AS JSONB),
                CAST(:warnings AS JSONB),
                CAST(:errors AS JSONB)
            )
            RETURNING sync_audit_id
            """
        ),
        {
            "actor_user_id": actor_user_id,
            "actor_login": actor_login,
            "operation": operation,
            "dry_run": dry_run,
            "package_name": package_name,
            "validation_ok": validation_ok,
            "notes": notes,
            "summary": json.dumps(summary or {}, ensure_ascii=False),
            "context": json.dumps(context or {}, ensure_ascii=False),
            "warnings": json.dumps(warnings or [], ensure_ascii=False),
            "errors": json.dumps(errors or [], ensure_ascii=False),
        },
    ).first()
    if not row:
        return None
    return int(row[0])


def _row_to_entry(row: Any) -> SyncAuditLogEntry:
    mapping = row._mapping if hasattr(row, "_mapping") else row
    return SyncAuditLogEntry(
        sync_audit_id=int(mapping["sync_audit_id"]),
        happened_at=mapping["happened_at"],
        actor_user_id=int(mapping["actor_user_id"]) if mapping.get("actor_user_id") is not None else None,
        actor_login=str(mapping["actor_login"]).strip() if mapping.get("actor_login") else None,
        operation=str(mapping["operation"]),
        dry_run=bool(mapping["dry_run"]),
        package_name=str(mapping["package_name"]).strip() if mapping.get("package_name") else None,
        validation_ok=bool(mapping["validation_ok"]) if mapping.get("validation_ok") is not None else None,
        notes=str(mapping["notes"]).strip() if mapping.get("notes") else None,
        summary=_parse_jsonb(mapping.get("summary"), default={}),
        context=_parse_jsonb(mapping.get("context"), default={}),
        warnings=_parse_jsonb(mapping.get("warnings"), default=[]),
        errors=_parse_jsonb(mapping.get("errors"), default=[]),
    )


def list_sync_audit_log(
    conn: Connection,
    *,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[SyncAuditLogEntry], int]:
    if not sync_audit_log_available(conn):
        return [], 0

    safe_limit = max(1, min(limit, 100))
    safe_offset = max(0, offset)

    total_row = conn.execute(text("SELECT COUNT(*) FROM public.hr_sync_audit_log")).first()
    total = int(total_row[0]) if total_row else 0

    rows = conn.execute(
        text(
            """
            SELECT
                sync_audit_id,
                happened_at,
                actor_user_id,
                actor_login,
                operation,
                dry_run,
                package_name,
                validation_ok,
                notes,
                summary,
                context,
                warnings,
                errors
            FROM public.hr_sync_audit_log
            ORDER BY happened_at DESC, sync_audit_id DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {"limit": safe_limit, "offset": safe_offset},
    ).fetchall()

    return [_row_to_entry(row) for row in rows], total


def get_sync_audit_log(conn: Connection, sync_audit_id: int) -> Optional[SyncAuditLogEntry]:
    if not sync_audit_log_available(conn):
        return None

    row = conn.execute(
        text(
            """
            SELECT
                sync_audit_id,
                happened_at,
                actor_user_id,
                actor_login,
                operation,
                dry_run,
                package_name,
                validation_ok,
                notes,
                summary,
                context,
                warnings,
                errors
            FROM public.hr_sync_audit_log
            WHERE sync_audit_id = :sync_audit_id
            LIMIT 1
            """
        ),
        {"sync_audit_id": sync_audit_id},
    ).first()
    if not row:
        return None
    return _row_to_entry(row)


def sync_audit_entry_to_api_dict(
    entry: SyncAuditLogEntry,
    *,
    include_messages: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "sync_audit_id": entry.sync_audit_id,
        "happened_at": _iso_datetime(entry.happened_at),
        "actor_user_id": entry.actor_user_id,
        "actor_login": entry.actor_login,
        "operation": entry.operation,
        "dry_run": entry.dry_run,
        "package_name": entry.package_name,
        "validation_ok": entry.validation_ok,
        "notes": entry.notes,
        "summary": entry.summary,
        "context": entry.context,
        "warnings_count": len(entry.warnings),
        "errors_count": len(entry.errors),
    }
    if include_messages:
        payload["warnings"] = entry.warnings
        payload["errors"] = entry.errors
    return payload
