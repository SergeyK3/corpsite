# FILE: app/services/regular_task_run_outcome.py
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple, Union

from sqlalchemy import text
from sqlalchemy.engine import Connection

ACTIVE_TASK_STATUS_CODES = frozenset({"IN_PROGRESS", "WAITING_REPORT", "WAITING_APPROVAL"})


def _isoformat_or_none(value: Union[datetime, date, str, None]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        trimmed = value.strip()
        return trimmed or None
    iso = getattr(value, "isoformat", None)
    if callable(iso):
        return iso()
    return str(value)


def _build_group_filter_sql(org_group_id: Optional[int]) -> Tuple[str, Dict[str, Any]]:
    if org_group_id is None:
        return "", {}
    return (
        """
          AND EXISTS (
              SELECT 1
              FROM public.users ux
              JOIN public.org_units oux
                ON oux.unit_id = ux.unit_id
              WHERE ux.role_id = i.executor_role_id
                AND COALESCE(ux.is_active, TRUE) = TRUE
                AND COALESCE(oux.is_active, TRUE) = TRUE
                AND oux.group_id = :org_group_id
          )
        """,
        {"org_group_id": int(org_group_id)},
    )


def _linked_task_id_sql() -> str:
    return """
        CASE
            WHEN COALESCE(i.meta->>'task_id', '') ~ '^[0-9]+$'
                THEN (i.meta->>'task_id')::bigint
            ELSE NULL
        END
    """.strip()


def _resolve_lifecycle_bucket(
    *,
    status_code: Optional[str],
    due_date: Optional[date],
    today: date,
) -> Optional[str]:
    code = str(status_code or "").strip().upper()
    if not code:
        return None
    if code == "DONE":
        return "done"
    if code == "ARCHIVED":
        return "archived"
    if code in ACTIVE_TASK_STATUS_CODES:
        if due_date is not None and due_date < today:
            return "overdue"
        return "in_progress"
    return "other"


def _resolve_period_label(rows: List[Dict[str, Any]]) -> Optional[str]:
    for row in rows:
        meta = row.get("meta") or {}
        if not isinstance(meta, dict):
            continue
        start = str(meta.get("period_start") or "").strip()
        end = str(meta.get("period_end") or "").strip()
        if start and end:
            return f"{start}–{end}"
        suffix = str(meta.get("title_suffix") or "").strip()
        if suffix:
            return suffix
    return None


def _compute_outcome_counts(rows: List[Dict[str, Any]], *, today: date) -> Dict[str, int]:
    linked = done = in_progress = overdue = archived = unlinked = other = 0

    for row in rows:
        meta_task_id = row.get("linked_task_id")
        if meta_task_id is None:
            continue

        resolved_task_id = row.get("resolved_task_id")
        status_code = row.get("task_status_code")
        due_date = row.get("task_due_date")
        if isinstance(due_date, datetime):
            due_date = due_date.date()

        if resolved_task_id is None:
            unlinked += 1
            continue

        linked += 1
        code = str(status_code or "").strip().upper()

        if code == "DONE":
            done += 1
        elif code == "ARCHIVED":
            archived += 1
        elif code in ACTIVE_TASK_STATUS_CODES:
            in_progress += 1
            if due_date is not None and due_date < today:
                overdue += 1
        else:
            other += 1

    return {
        "linked": linked,
        "done": done,
        "in_progress": in_progress,
        "overdue": overdue,
        "archived": archived,
        "unlinked": unlinked,
        "other": other,
    }


def load_regular_task_run_items_with_outcome(
    conn: Connection,
    *,
    run_id: int,
    org_group_id: Optional[int] = None,
    today: Optional[date] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Load run items with optional task lifecycle join and aggregate outcome counts.

    Single SQL round-trip; no per-item queries (no N+1).
    """
    effective_today = today or date.today()
    params: Dict[str, Any] = {"run_id": int(run_id)}
    group_filter_sql, group_params = _build_group_filter_sql(org_group_id)
    params.update(group_params)
    linked_task_id_sql = _linked_task_id_sql()

    sql = text(
        f"""
        SELECT
            i.item_id,
            i.run_id,
            i.regular_task_id,
            i.status,
            i.started_at,
            i.finished_at,
            i.period_id,
            i.executor_role_id,
            rol.name AS executor_role_name,
            rol.code AS executor_role_code,
            i.is_due,
            i.created_tasks,
            i.error,
            i.meta,
            {linked_task_id_sql} AS linked_task_id,
            t.task_id AS resolved_task_id,
            ts.code AS task_status_code,
            ts.name_ru AS task_status_name_ru,
            t.due_date AS task_due_date
        FROM public.regular_task_run_items i
        LEFT JOIN public.roles rol
          ON rol.role_id = i.executor_role_id
        LEFT JOIN public.tasks t
          ON t.task_id = {linked_task_id_sql}
        LEFT JOIN public.task_statuses ts
          ON ts.status_id = t.status_id
        WHERE i.run_id = :run_id
        {group_filter_sql}
        ORDER BY i.item_id
        """
    )

    rows = [dict(r) for r in conn.execute(sql, params).mappings().all()]
    counts = _compute_outcome_counts(rows, today=effective_today)
    outcome = {
        "run_id": int(run_id),
        "period_label": _resolve_period_label(rows),
        "counts": counts,
    }
    return rows, outcome


def build_item_task_payload(row: Dict[str, Any], *, today: date) -> Optional[Dict[str, Any]]:
    linked_task_id = row.get("linked_task_id")
    if linked_task_id is None:
        return None

    resolved_task_id = row.get("resolved_task_id")
    status_code = row.get("task_status_code")
    due_date = row.get("task_due_date")
    if isinstance(due_date, datetime):
        due_date = due_date.date()

    is_overdue = False
    if resolved_task_id is not None:
        code = str(status_code or "").strip().upper()
        if code in ACTIVE_TASK_STATUS_CODES and due_date is not None and due_date < today:
            is_overdue = True

    return {
        "task_id": int(resolved_task_id) if resolved_task_id is not None else int(linked_task_id),
        "resolved": resolved_task_id is not None,
        "status_code": status_code,
        "status_name_ru": row.get("task_status_name_ru"),
        "due_date": _isoformat_or_none(due_date),
        "is_overdue": is_overdue,
        "lifecycle": _resolve_lifecycle_bucket(
            status_code=status_code,
            due_date=due_date,
            today=today,
        ),
    }
