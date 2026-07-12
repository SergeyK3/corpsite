"""Append-only lifecycle audit for personnel orders (WP-PO-LC-DEL-003)."""
from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Mapping, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.engine import engine
from app.db.models.personnel_orders import (
    LIFECYCLE_AUDIT_ACTION_ARCHIVE,
    LIFECYCLE_AUDIT_ACTION_RESTORE,
    LIFECYCLE_AUDIT_ACTIONS,
    ORDER_STATUS_DRAFT,
    ORDER_STATUS_READY_FOR_SIGNATURE,
    ORDER_STATUS_VOIDED,
    VOID_KIND_ANNUL,
    VOID_KIND_CANCEL,
)
from app.services.personnel_orders_query_service import (
    PersonnelOrderNotFoundError,
    personnel_orders_available,
)

LIFECYCLE_AUDIT_TABLE = "personnel_order_lifecycle_audit"


def personnel_order_lifecycle_audit_available(conn: Optional[Connection] = None) -> bool:
    if not personnel_orders_available():
        return False

    def _check(connection: Connection) -> bool:
        row = connection.execute(
            text(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = :table_name
                LIMIT 1
                """
            ),
            {"table_name": LIFECYCLE_AUDIT_TABLE},
        ).first()
        return row is not None

    if conn is not None:
        return _check(conn)
    with engine.begin() as own_conn:
        return _check(own_conn)


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return str(value)


def append_personnel_order_lifecycle_audit(
    conn: Connection,
    *,
    order_id: int,
    action: str,
    previous_status: Optional[str],
    new_status: Optional[str],
    previous_void_kind: Optional[str],
    new_void_kind: Optional[str],
    actor_user_id: int,
    reason_code: Optional[str] = None,
    reason_text: Optional[str] = None,
    metadata_json: Optional[Dict[str, Any]] = None,
) -> Optional[int]:
    """Insert one append-only lifecycle audit row. No-op when audit table is absent."""
    if not personnel_order_lifecycle_audit_available(conn):
        return None

    normalized_action = str(action or "").strip().upper()
    if normalized_action not in LIFECYCLE_AUDIT_ACTIONS:
        raise ValueError(f"Unsupported lifecycle audit action: {action}")

    metadata = _json_safe(metadata_json or {})
    row = conn.execute(
        text(
            """
            INSERT INTO public.personnel_order_lifecycle_audit (
                order_id,
                action,
                previous_status,
                new_status,
                previous_void_kind,
                new_void_kind,
                actor_user_id,
                reason_code,
                reason_text,
                metadata_json
            )
            VALUES (
                :order_id,
                :action,
                :previous_status,
                :new_status,
                :previous_void_kind,
                :new_void_kind,
                :actor_user_id,
                :reason_code,
                :reason_text,
                CAST(:metadata_json AS jsonb)
            )
            RETURNING id
            """
        ),
        {
            "order_id": int(order_id),
            "action": normalized_action,
            "previous_status": previous_status,
            "new_status": new_status,
            "previous_void_kind": previous_void_kind,
            "new_void_kind": new_void_kind,
            "actor_user_id": int(actor_user_id),
            "reason_code": reason_code,
            "reason_text": reason_text,
            "metadata_json": json.dumps(metadata, ensure_ascii=False),
        },
    ).one()
    return int(row[0])


def resolve_void_kind(previous_status: str) -> str:
    """Map pre-void order status to canonical void_kind (CANCEL | ANNUL)."""
    normalized = str(previous_status or "").strip().upper()
    if normalized in {ORDER_STATUS_DRAFT, ORDER_STATUS_READY_FOR_SIGNATURE}:
        return VOID_KIND_CANCEL
    return VOID_KIND_ANNUL


def void_audit_action_for_status(status: str) -> str:
    """Deprecated alias — use resolve_void_kind."""
    return resolve_void_kind(status)


def void_audit_void_kind_for_status(status: str) -> str:
    """Deprecated alias — use resolve_void_kind."""
    return resolve_void_kind(status)


def append_void_order_audit(
    conn: Connection,
    *,
    order_id: int,
    previous_status: str,
    previous_void_kind: Optional[str],
    void_kind: str,
    void_reason: str,
    actor_user_id: int,
    metadata_json: Optional[Dict[str, Any]] = None,
) -> Optional[int]:
    normalized_kind = str(void_kind or "").strip().upper()
    if normalized_kind not in {VOID_KIND_CANCEL, VOID_KIND_ANNUL}:
        raise ValueError(f"Unsupported void_kind: {void_kind}")
    return append_personnel_order_lifecycle_audit(
        conn,
        order_id=int(order_id),
        action=normalized_kind,
        previous_status=str(previous_status),
        new_status=ORDER_STATUS_VOIDED,
        previous_void_kind=previous_void_kind,
        new_void_kind=normalized_kind,
        actor_user_id=int(actor_user_id),
        reason_text=str(void_reason).strip(),
        metadata_json=metadata_json,
    )


def append_archive_order_audit(
    conn: Connection,
    *,
    order_id: int,
    previous_status: str,
    previous_void_kind: Optional[str],
    reason_code: str,
    reason_text: str,
    actor_user_id: int,
    metadata_json: Optional[Dict[str, Any]] = None,
) -> Optional[int]:
    return append_personnel_order_lifecycle_audit(
        conn,
        order_id=int(order_id),
        action=LIFECYCLE_AUDIT_ACTION_ARCHIVE,
        previous_status=str(previous_status),
        new_status=str(previous_status),
        previous_void_kind=previous_void_kind,
        new_void_kind=previous_void_kind,
        actor_user_id=int(actor_user_id),
        reason_code=str(reason_code).strip().lower(),
        reason_text=str(reason_text).strip(),
        metadata_json=metadata_json,
    )


def append_restore_order_audit(
    conn: Connection,
    *,
    order_id: int,
    previous_status: str,
    previous_void_kind: Optional[str],
    actor_user_id: int,
    metadata_json: Optional[Dict[str, Any]] = None,
) -> Optional[int]:
    return append_personnel_order_lifecycle_audit(
        conn,
        order_id=int(order_id),
        action=LIFECYCLE_AUDIT_ACTION_RESTORE,
        previous_status=str(previous_status),
        new_status=str(previous_status),
        previous_void_kind=previous_void_kind,
        new_void_kind=previous_void_kind,
        actor_user_id=int(actor_user_id),
        metadata_json=metadata_json,
    )


def append_cancel_order_audit(
    conn: Connection,
    *,
    order_id: int,
    previous_status: str,
    previous_void_kind: Optional[str],
    reason_code: str,
    reason_text: str,
    void_reason: str,
    actor_user_id: int,
    metadata_json: Optional[Dict[str, Any]] = None,
) -> Optional[int]:
    return append_personnel_order_lifecycle_audit(
        conn,
        order_id=int(order_id),
        action=VOID_KIND_CANCEL,
        previous_status=str(previous_status),
        new_status=ORDER_STATUS_VOIDED,
        previous_void_kind=previous_void_kind,
        new_void_kind=VOID_KIND_CANCEL,
        actor_user_id=int(actor_user_id),
        reason_code=str(reason_code).strip().lower(),
        reason_text=str(reason_text).strip(),
        metadata_json=metadata_json or {"void_reason": str(void_reason).strip()},
    )


def _serialize_audit_row(row: Mapping[str, Any]) -> Dict[str, Any]:
    created_at = row.get("created_at")
    return {
        "id": int(row["id"]),
        "order_id": int(row["order_id"]),
        "action": str(row["action"]),
        "previous_status": row.get("previous_status"),
        "new_status": row.get("new_status"),
        "previous_void_kind": row.get("previous_void_kind"),
        "new_void_kind": row.get("new_void_kind"),
        "actor_user_id": int(row["actor_user_id"]),
        "reason_code": row.get("reason_code"),
        "reason_text": row.get("reason_text"),
        "metadata_json": row.get("metadata_json") or {},
        "created_at": created_at.isoformat() if isinstance(created_at, datetime) else created_at,
    }


def list_personnel_order_lifecycle_audit(
    order_id: int,
    *,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    if not personnel_orders_available():
        raise PersonnelOrderNotFoundError("Personnel orders schema is not available.")
    if not personnel_order_lifecycle_audit_available():
        return {"items": [], "total": 0, "limit": int(limit), "offset": int(offset)}

    safe_limit = max(1, min(int(limit), 500))
    safe_offset = max(0, int(offset))

    with engine.begin() as conn:
        exists = conn.execute(
            text(
                """
                SELECT 1
                FROM public.personnel_orders
                WHERE order_id = :order_id
                LIMIT 1
                """
            ),
            {"order_id": int(order_id)},
        ).first()
        if exists is None:
            raise PersonnelOrderNotFoundError(f"Personnel order {order_id} not found.")

        total = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.personnel_order_lifecycle_audit
                    WHERE order_id = :order_id
                    """
                ),
                {"order_id": int(order_id)},
            ).scalar_one()
            or 0
        )

        rows = conn.execute(
            text(
                """
                SELECT
                    id,
                    order_id,
                    action,
                    previous_status,
                    new_status,
                    previous_void_kind,
                    new_void_kind,
                    actor_user_id,
                    reason_code,
                    reason_text,
                    metadata_json,
                    created_at
                FROM public.personnel_order_lifecycle_audit
                WHERE order_id = :order_id
                ORDER BY created_at DESC, id DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {
                "order_id": int(order_id),
                "limit": safe_limit,
                "offset": safe_offset,
            },
        ).mappings().all()

    return {
        "items": [_serialize_audit_row(row) for row in rows],
        "total": total,
        "limit": safe_limit,
        "offset": safe_offset,
    }
