"""ADR-044 R2.5e — read-only user linkage operations history queries."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.engine import engine
from app.db.user_linkage_journal_constants import (
    EVENT_USER_EMPLOYEE_LINKED,
    EVENT_USER_EMPLOYEE_LINK_ROLLED_BACK,
    EVENT_USER_EMPLOYEE_UNLINKED,
    R2_RUN_OPERATIONS,
    USER_LINKAGE_AUDIT_EVENT_TYPES,
)
from app.services.user_linkage_execute_service import execute_items_available

_RECENT_ITEMS_DEFAULT = 20
_RECENT_ITEMS_MAX = 100


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


def _parse_summary(value: Any) -> dict[str, Any]:
    parsed = _parse_json_field(value)
    return dict(parsed) if isinstance(parsed, dict) else {}


def _audit_summary_for_run(conn: Connection, run_id: int) -> dict[str, int]:
    if not _table_exists(conn, "security_audit_log"):
        return {
            "user_employee_linked": 0,
            "user_employee_unlinked": 0,
            "user_employee_link_rolled_back": 0,
        }
    rows = conn.execute(
        text(
            """
            SELECT event_type, COUNT(*) AS cnt
            FROM public.security_audit_log
            WHERE event_type = ANY(:event_types)
              AND metadata->>'run_id' = :run_id
            GROUP BY event_type
            """
        ),
        {
            "event_types": list(USER_LINKAGE_AUDIT_EVENT_TYPES),
            "run_id": str(int(run_id)),
        },
    ).mappings().all()
    counts = {str(row["event_type"]): int(row["cnt"]) for row in rows}
    return {
        "user_employee_linked": counts.get(EVENT_USER_EMPLOYEE_LINKED, 0),
        "user_employee_unlinked": counts.get(EVENT_USER_EMPLOYEE_UNLINKED, 0),
        "user_employee_link_rolled_back": counts.get(EVENT_USER_EMPLOYEE_LINK_ROLLED_BACK, 0),
    }


def _source_refs_from_summary(summary: dict[str, Any]) -> dict[str, Optional[int]]:
    source_preview_run_id = summary.get("source_preview_run_id")
    source_item_id = summary.get("source_item_id")
    return {
        "source_preview_run_id": int(source_preview_run_id)
        if source_preview_run_id is not None
        else None,
        "source_item_id": int(source_item_id) if source_item_id is not None else None,
    }


def _serialize_run_row(
    conn: Connection,
    row: dict[str, Any],
    *,
    item_count: Optional[int] = None,
) -> dict[str, Any]:
    summary = _parse_summary(row.get("summary"))
    run_id = int(row["run_id"])
    if item_count is None:
        item_count = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*) AS cnt
                    FROM public.user_linkage_execute_items
                    WHERE run_id = :run_id
                    """
                ),
                {"run_id": run_id},
            ).scalar_one()
        )
    refs = _source_refs_from_summary(summary)
    return {
        "run_id": run_id,
        "phase": str(row.get("phase") or ""),
        "operation": str(row.get("operation") or ""),
        "status": str(row.get("status") or ""),
        "dry_run": bool(row.get("dry_run")),
        "actor_user_id": int(row["actor_user_id"])
        if row.get("actor_user_id") is not None
        else None,
        "actor_login": row.get("actor_login"),
        "started_at": _serialize_dt(row.get("started_at")),
        "finished_at": _serialize_dt(row.get("finished_at")),
        "summary": summary,
        "source_preview_run_id": refs["source_preview_run_id"],
        "source_item_id": refs["source_item_id"],
        "item_count": item_count,
        "audit_summary": _audit_summary_for_run(conn, run_id),
    }


def _extract_source_item_id(
    rollback_payload: Any,
    run_summary: dict[str, Any],
) -> Optional[int]:
    payload = _parse_json_field(rollback_payload)
    if isinstance(payload, dict) and payload.get("source_item_id") is not None:
        return int(payload["source_item_id"])
    if run_summary.get("source_item_id") is not None:
        return int(run_summary["source_item_id"])
    return None


def _serialize_item_row(
    row: dict[str, Any],
    *,
    include_snapshots: bool = False,
) -> dict[str, Any]:
    reason_codes = _parse_json_field(row.get("reason_codes"))
    rollback_payload = _parse_json_field(row.get("rollback_payload"))
    run_summary = _parse_summary(row.get("run_summary"))
    out: dict[str, Any] = {
        "item_id": int(row["item_id"]),
        "run_id": int(row["run_id"]),
        "run_operation": row.get("run_operation"),
        "run_status": row.get("run_status"),
        "user_id": int(row["user_id"]),
        "login": row.get("login"),
        "proposed_employee_id": int(row["proposed_employee_id"])
        if row.get("proposed_employee_id") is not None
        else None,
        "employee_name": row.get("employee_name"),
        "action": str(row.get("action") or ""),
        "status": str(row.get("status") or ""),
        "reason_codes": list(reason_codes) if isinstance(reason_codes, list) else [],
        "created_at": _serialize_dt(row.get("created_at")),
        "source_item_id": _extract_source_item_id(rollback_payload, run_summary),
        "audit_summary": {
            "user_employee_linked": 0,
            "user_employee_unlinked": 0,
            "user_employee_link_rolled_back": 0,
        },
    }
    if include_snapshots:
        before_snapshot = _parse_json_field(row.get("before_user_snapshot"))
        after_snapshot = _parse_json_field(row.get("after_user_snapshot"))
        preview_snapshot = _parse_json_field(row.get("preview_snapshot"))
        decision_snapshot = _parse_json_field(row.get("decision_snapshot"))
        out.update(
            {
                "source_decision_id": int(row["source_decision_id"])
                if row.get("source_decision_id") is not None
                else None,
                "before_user_snapshot": before_snapshot
                if isinstance(before_snapshot, dict)
                else {},
                "after_user_snapshot": after_snapshot if isinstance(after_snapshot, dict) else {},
                "rollback_payload": rollback_payload if isinstance(rollback_payload, dict) else {},
                "preview_snapshot": preview_snapshot if isinstance(preview_snapshot, dict) else {},
                "decision_snapshot": decision_snapshot if isinstance(decision_snapshot, dict) else {},
                "run_summary": run_summary,
            }
        )
    return out


def _item_counts(conn: Connection, run_id: int) -> tuple[dict[str, int], dict[str, int]]:
    status_rows = conn.execute(
        text(
            """
            SELECT status, COUNT(*) AS cnt
            FROM public.user_linkage_execute_items
            WHERE run_id = :run_id
            GROUP BY status
            """
        ),
        {"run_id": int(run_id)},
    ).mappings().all()
    action_rows = conn.execute(
        text(
            """
            SELECT action, COUNT(*) AS cnt
            FROM public.user_linkage_execute_items
            WHERE run_id = :run_id
            GROUP BY action
            """
        ),
        {"run_id": int(run_id)},
    ).mappings().all()
    by_status = {str(row["status"]): int(row["cnt"]) for row in status_rows}
    by_action = {str(row["action"]): int(row["cnt"]) for row in action_rows}
    return by_status, by_action


def _require_history_schema(conn: Connection) -> bool:
    return execute_items_available(conn)


def list_user_linkage_operations_runs(
    *,
    operation: Optional[str] = None,
    status: Optional[str] = None,
    actor_user_id: Optional[int] = None,
    created_from: Optional[datetime] = None,
    created_to: Optional[datetime] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))

    with engine.connect() as conn:
        if not _require_history_schema(conn):
            return {"items": [], "total": 0, "limit": limit, "offset": offset}

        filters = ["r.phase = 'R2'", "r.operation IS NOT NULL"]
        params: dict[str, Any] = {"limit": limit, "offset": offset}

        if operation:
            normalized_operation = operation.strip().upper()
            if normalized_operation not in R2_RUN_OPERATIONS:
                return {"items": [], "total": 0, "limit": limit, "offset": offset}
            filters.append("r.operation = :operation")
            params["operation"] = normalized_operation
        if status:
            filters.append("r.status = :status")
            params["status"] = status.strip().lower()
        if actor_user_id is not None:
            filters.append("r.actor_user_id = :actor_user_id")
            params["actor_user_id"] = int(actor_user_id)
        if created_from is not None:
            filters.append("r.started_at >= :created_from")
            params["created_from"] = created_from
        if created_to is not None:
            filters.append("r.started_at <= :created_to")
            params["created_to"] = created_to

        where_sql = " AND ".join(filters)
        total = int(
            conn.execute(
                text(
                    f"""
                    SELECT COUNT(*) AS cnt
                    FROM public.identity_reconciliation_runs r
                    WHERE {where_sql}
                    """
                ),
                params,
            ).scalar_one()
        )
        rows = conn.execute(
            text(
                f"""
                SELECT
                    r.run_id,
                    r.phase,
                    r.operation,
                    r.status,
                    r.dry_run,
                    r.actor_user_id,
                    r.started_at,
                    r.finished_at,
                    r.summary,
                    actor_u.login AS actor_login,
                    COUNT(i.item_id) AS item_count
                FROM public.identity_reconciliation_runs r
                LEFT JOIN public.users actor_u ON actor_u.user_id = r.actor_user_id
                LEFT JOIN public.user_linkage_execute_items i ON i.run_id = r.run_id
                WHERE {where_sql}
                GROUP BY
                    r.run_id,
                    r.phase,
                    r.operation,
                    r.status,
                    r.dry_run,
                    r.actor_user_id,
                    r.started_at,
                    r.finished_at,
                    r.summary,
                    actor_u.login
                ORDER BY r.started_at DESC, r.run_id DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        ).mappings().all()

        items = [
            _serialize_run_row(
                conn,
                dict(row),
                item_count=int(row.get("item_count") or 0),
            )
            for row in rows
        ]

    return {"items": items, "total": total, "limit": limit, "offset": offset}


def get_user_linkage_operations_run(
    run_id: int,
    *,
    recent_items_limit: int = _RECENT_ITEMS_DEFAULT,
) -> dict[str, Any]:
    recent_items_limit = max(1, min(int(recent_items_limit), _RECENT_ITEMS_MAX))

    with engine.connect() as conn:
        if not _require_history_schema(conn):
            raise ValueError(f"User linkage operations run not found: {run_id}")

        row = conn.execute(
            text(
                """
                SELECT
                    r.run_id,
                    r.phase,
                    r.operation,
                    r.status,
                    r.dry_run,
                    r.actor_user_id,
                    r.started_at,
                    r.finished_at,
                    r.summary,
                    actor_u.login AS actor_login
                FROM public.identity_reconciliation_runs r
                LEFT JOIN public.users actor_u ON actor_u.user_id = r.actor_user_id
                WHERE r.run_id = :run_id
                  AND r.phase = 'R2'
                  AND r.operation IS NOT NULL
                LIMIT 1
                """
            ),
            {"run_id": int(run_id)},
        ).mappings().first()
        if row is None:
            raise ValueError(f"User linkage operations run not found: {run_id}")

        detail = _serialize_run_row(conn, dict(row))
        by_status, by_action = _item_counts(conn, int(run_id))
        detail["item_counts_by_status"] = by_status
        detail["item_counts_by_action"] = by_action

        item_rows = conn.execute(
            text(
                """
                SELECT
                    i.item_id,
                    i.run_id,
                    r.operation AS run_operation,
                    r.status AS run_status,
                    r.summary AS run_summary,
                    i.user_id,
                    u.login,
                    i.proposed_employee_id,
                    e.full_name AS employee_name,
                    i.action,
                    i.status,
                    i.reason_codes,
                    i.created_at,
                    i.rollback_payload
                FROM public.user_linkage_execute_items i
                JOIN public.identity_reconciliation_runs r ON r.run_id = i.run_id
                LEFT JOIN public.users u ON u.user_id = i.user_id
                LEFT JOIN public.employees e ON e.employee_id = i.proposed_employee_id
                WHERE i.run_id = :run_id
                ORDER BY i.item_id DESC
                LIMIT :limit
                """
            ),
            {"run_id": int(run_id), "limit": recent_items_limit},
        ).mappings().all()

        recent_items = []
        for item_row in item_rows:
            serialized = _serialize_item_row(dict(item_row))
            serialized["audit_summary"] = detail["audit_summary"]
            recent_items.append(serialized)
        detail["recent_items"] = recent_items

    return detail


def list_user_linkage_operations_items(
    *,
    run_id: Optional[int] = None,
    action: Optional[str] = None,
    status: Optional[str] = None,
    user_id: Optional[int] = None,
    employee_id: Optional[int] = None,
    source_item_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))

    with engine.connect() as conn:
        if not _require_history_schema(conn):
            return {"items": [], "total": 0, "limit": limit, "offset": offset}

        filters = ["r.phase = 'R2'", "r.operation IS NOT NULL"]
        params: dict[str, Any] = {"limit": limit, "offset": offset}

        if run_id is not None:
            filters.append("i.run_id = :run_id")
            params["run_id"] = int(run_id)
        if action:
            filters.append("i.action = :action")
            params["action"] = action.strip().upper()
        if status:
            filters.append("i.status = :status")
            params["status"] = status.strip().upper()
        if user_id is not None:
            filters.append("i.user_id = :user_id")
            params["user_id"] = int(user_id)
        if employee_id is not None:
            filters.append("i.proposed_employee_id = :employee_id")
            params["employee_id"] = int(employee_id)
        if source_item_id is not None:
            filters.append(
                """
                (
                    i.rollback_payload->>'source_item_id' = :source_item_id
                    OR r.summary->>'source_item_id' = :source_item_id
                )
                """
            )
            params["source_item_id"] = str(int(source_item_id))

        where_sql = " AND ".join(filters)
        total = int(
            conn.execute(
                text(
                    f"""
                    SELECT COUNT(*) AS cnt
                    FROM public.user_linkage_execute_items i
                    JOIN public.identity_reconciliation_runs r ON r.run_id = i.run_id
                    WHERE {where_sql}
                    """
                ),
                params,
            ).scalar_one()
        )
        rows = conn.execute(
            text(
                f"""
                SELECT
                    i.item_id,
                    i.run_id,
                    r.operation AS run_operation,
                    r.status AS run_status,
                    r.summary AS run_summary,
                    i.user_id,
                    u.login,
                    i.proposed_employee_id,
                    e.full_name AS employee_name,
                    i.action,
                    i.status,
                    i.reason_codes,
                    i.created_at,
                    i.rollback_payload
                FROM public.user_linkage_execute_items i
                JOIN public.identity_reconciliation_runs r ON r.run_id = i.run_id
                LEFT JOIN public.users u ON u.user_id = i.user_id
                LEFT JOIN public.employees e ON e.employee_id = i.proposed_employee_id
                WHERE {where_sql}
                ORDER BY i.created_at DESC, i.item_id DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        ).mappings().all()

        items = []
        for row in rows:
            serialized = _serialize_item_row(dict(row))
            serialized["audit_summary"] = _audit_summary_for_run(
                conn,
                int(row["run_id"]),
            )
            items.append(serialized)

    return {"items": items, "total": total, "limit": limit, "offset": offset}


def get_user_linkage_operations_item(item_id: int) -> dict[str, Any]:
    with engine.connect() as conn:
        if not _require_history_schema(conn):
            raise ValueError(f"User linkage operations item not found: {item_id}")

        row = conn.execute(
            text(
                """
                SELECT
                    i.item_id,
                    i.run_id,
                    r.operation AS run_operation,
                    r.status AS run_status,
                    r.summary AS run_summary,
                    i.user_id,
                    u.login,
                    i.proposed_employee_id,
                    e.full_name AS employee_name,
                    i.source_decision_id,
                    i.action,
                    i.status,
                    i.reason_codes,
                    i.created_at,
                    i.before_user_snapshot,
                    i.after_user_snapshot,
                    i.rollback_payload,
                    i.preview_snapshot,
                    i.decision_snapshot
                FROM public.user_linkage_execute_items i
                JOIN public.identity_reconciliation_runs r ON r.run_id = i.run_id
                LEFT JOIN public.users u ON u.user_id = i.user_id
                LEFT JOIN public.employees e ON e.employee_id = i.proposed_employee_id
                WHERE i.item_id = :item_id
                  AND r.phase = 'R2'
                  AND r.operation IS NOT NULL
                LIMIT 1
                """
            ),
            {"item_id": int(item_id)},
        ).mappings().first()
        if row is None:
            raise ValueError(f"User linkage operations item not found: {item_id}")

        detail = _serialize_item_row(dict(row), include_snapshots=True)
        detail["audit_summary"] = _audit_summary_for_run(conn, int(row["run_id"]))
        return detail
