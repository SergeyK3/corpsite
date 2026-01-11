# app/tasks.py
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional, Set, List

from fastapi import APIRouter, HTTPException, Query, Header, Path
from fastapi import Response
from pydantic import BaseModel
from sqlalchemy import text

from app.db.engine import engine
from app.errors import raise_error, ErrorCode

router = APIRouter(prefix="/tasks", tags=["tasks"])


# ---------------------------
# RBAC v2: supervisor/deputy (by role_id sets from env)
# ---------------------------
# Set in .env (comma-separated ints), for example:
# SUPERVISOR_ROLE_IDS=10,11
# DEPUTY_ROLE_IDS=12
# DIRECTOR_ROLE_IDS=13
def _parse_int_set(env_name: str) -> Set[int]:
    raw = (os.getenv(env_name) or "").strip()
    if not raw:
        return set()
    out: Set[int] = set()
    for part in raw.split(","):
        p = part.strip()
        if not p:
            continue
        try:
            out.add(int(p))
        except Exception:
            # ignore invalid values
            pass
    return out


SUPERVISOR_ROLE_IDS: Set[int] = _parse_int_set("SUPERVISOR_ROLE_IDS")
DEPUTY_ROLE_IDS: Set[int] = _parse_int_set("DEPUTY_ROLE_IDS")
DIRECTOR_ROLE_IDS: Set[int] = _parse_int_set("DIRECTOR_ROLE_IDS")


def _is_supervisor_or_deputy(role_id: int) -> bool:
    rid = int(role_id)
    return rid in SUPERVISOR_ROLE_IDS or rid in DEPUTY_ROLE_IDS


# ---------------------------
# Helpers: current user
# ---------------------------

def _get_current_user_id(x_user_id: Optional[int]) -> int:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id header is required")
    return int(x_user_id)


def _get_user_role_id(conn, user_id: int) -> int:
    row = conn.execute(
        text("SELECT user_id, role_id FROM users WHERE user_id = :uid"),
        {"uid": user_id},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    if row["role_id"] is None:
        raise HTTPException(status_code=400, detail="User role_id is NULL")
    return int(row["role_id"])


# ---------------------------
# Helpers: statuses & enums
# ---------------------------

def _get_status_id_by_code(conn, code: str) -> int:
    row = conn.execute(
        text("SELECT status_id FROM task_statuses WHERE code = :code"),
        {"code": code},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=400, detail=f"Unknown status code: {code}")
    return int(row["status_id"])


def _load_assignment_scope_enum_labels(conn) -> Set[str]:
    rows = conn.execute(
        text(
            """
            SELECT e.enumlabel
            FROM pg_enum e
            JOIN pg_type t ON t.oid = e.enumtypid
            WHERE t.typname = 'assignment_scope_t'
            ORDER BY e.enumsortorder
            """
        )
    ).all()
    return {r[0] for r in rows}


def _pick_default_scope(allowed: Set[str]) -> str:
    if any(lbl.lower() == "functional" for lbl in allowed):
        return next(lbl for lbl in allowed if lbl.lower() == "functional")
    return sorted(allowed)[0]


def _normalize_assignment_scope(conn, value: Any) -> str:
    allowed = _load_assignment_scope_enum_labels(conn)
    if not allowed:
        raise HTTPException(status_code=500, detail="assignment_scope_t enum not found in DB")

    if value is None or (isinstance(value, str) and not value.strip()):
        return _pick_default_scope(allowed)

    raw = str(value).strip()

    if raw in allowed:
        return raw

    raw_l = raw.lower()
    for lbl in allowed:
        if lbl.lower() == raw_l:
            return lbl

    legacy_map = {"role": "functional", "any": "functional", "user": "admin"}
    if raw_l in legacy_map:
        target = legacy_map[raw_l]
        for lbl in allowed:
            if lbl.lower() == target:
                return lbl

    raise HTTPException(
        status_code=422,
        detail=f"assignment_scope must be one of: {', '.join(sorted(allowed))}",
    )


def _scope_label_or_none(allowed: Set[str], wanted_lower: str) -> Optional[str]:
    for lbl in allowed:
        if lbl.lower() == wanted_lower:
            return lbl
    return None


# ---------------------------
# Audit (with events columns)
# ---------------------------

def _write_task_audit(
    conn,
    *,
    task_id: int,
    actor_user_id: int,
    actor_role_id: Optional[int],
    action: str,
    fields_changed: Optional[Dict[str, Any]] = None,
    request_body: Optional[Dict[str, Any]] = None,
    meta: Optional[Dict[str, Any]] = None,
    # events columns
    event_type: Optional[str] = None,               # REPORT_SUBMITTED / APPROVED / REJECTED
    event_payload: Optional[Dict[str, Any]] = None, # stored in task_audit_log.payload
) -> None:
    """
    Writes a single audit row. If event_type is provided, the same row becomes an "event" too.
    actor_user_id/action are NOT NULL by schema.
    """
    conn.execute(
        text(
            """
            INSERT INTO task_audit_log (
                task_id,
                actor_user_id,
                action,
                fields_changed,
                request_body,
                meta,
                event_type,
                actor_id,
                actor_role,
                payload
            )
            VALUES (
                :task_id,
                :actor_user_id,
                :action,
                CAST(:fields_changed AS jsonb),
                CAST(:request_body AS jsonb),
                CAST(:meta AS jsonb),
                CASE WHEN :event_type IS NULL THEN NULL ELSE (:event_type)::task_event_type END,
                :actor_id,
                :actor_role,
                CAST(:payload AS jsonb)
            )
            """
        ),
        {
            "task_id": int(task_id),
            "actor_user_id": int(actor_user_id),
            "action": action,
            "fields_changed": json.dumps(fields_changed) if fields_changed is not None else None,
            "request_body": json.dumps(request_body) if request_body is not None else None,
            "meta": json.dumps(meta) if meta is not None else None,
            "event_type": event_type,
            "actor_id": int(actor_user_id),
            "actor_role": str(actor_role_id) if actor_role_id is not None else None,
            "payload": json.dumps(event_payload or {}) if (event_type is not None) else json.dumps({}),
        },
    )


# ---------------------------
# Helper: force event fields on last audit row
# ---------------------------

def _set_last_audit_event(
    conn,
    *,
    task_id: int,
    actor_user_id: int,
    actor_role_id: Optional[int],
    event_type: str,                   # REPORT_SUBMITTED / APPROVED / REJECTED
    event_payload: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Гарантирует заполнение event-полей в последней audit-записи (task_id, actor_user_id).
    Использовать сразу после INSERT, если нужно "догарантировать" event_type/payload.
    """
    conn.execute(
        text(
            """
            UPDATE task_audit_log
            SET
                event_type = (:event_type)::task_event_type,
                actor_id = :actor_id,
                actor_role = :actor_role,
                payload = CAST(:payload AS jsonb)
            WHERE audit_id = (
                SELECT audit_id
                FROM task_audit_log
                WHERE task_id = :task_id
                  AND actor_user_id = :actor_user_id
                ORDER BY audit_id DESC
                LIMIT 1
            )
            """
        ),
        {
            "task_id": int(task_id),
            "actor_user_id": int(actor_user_id),
            "event_type": event_type,
            "actor_id": int(actor_user_id),
            "actor_role": str(actor_role_id) if actor_role_id is not None else None,
            "payload": json.dumps(event_payload or {}),
        },
    )


# ---------------------------
# Events delivery persistence (Variant A): task_events + task_event_recipients
# ---------------------------

def _safe_int(v: Any) -> Optional[int]:
    try:
        if v is None:
            return None
        return int(v)
    except Exception:
        return None


def _uniq_positive_ints(items: List[Any]) -> List[int]:
    out: List[int] = []
    seen: Set[int] = set()
    for x in items:
        ix = _safe_int(x)
        if ix is None or ix <= 0:
            continue
        if ix in seen:
            continue
        seen.add(ix)
        out.append(ix)
    return out


def _resolve_event_recipients_for_task(
    conn,
    *,
    task_row: Dict[str, Any],
) -> List[int]:
    """
    Audience policy (server-side):
      - initiator always
      - all users with role_id == executor_role_id
      - all supervisors/deputies/directors (by env role_id sets)

    NOTE: If later you introduce hierarchy logic, update only this function.
    """
    initiator_user_id = _safe_int(task_row.get("initiator_user_id")) or 0
    executor_role_id = _safe_int(task_row.get("executor_role_id")) or 0

    executor_users: List[int] = []
    if executor_role_id > 0:
        executor_users = conn.execute(
            text("SELECT user_id FROM users WHERE role_id = :rid"),
            {"rid": int(executor_role_id)},
        ).scalars().all()

    mgmt_role_ids = sorted(set(SUPERVISOR_ROLE_IDS) | set(DEPUTY_ROLE_IDS) | set(DIRECTOR_ROLE_IDS))
    mgmt_users: List[int] = []
    if mgmt_role_ids:
        mgmt_users = conn.execute(
            text(
                """
                SELECT user_id
                FROM users
                WHERE role_id = ANY(CAST(:rids AS bigint[]))
                """
            ),
            {"rids": [int(x) for x in mgmt_role_ids]},
        ).scalars().all()

    return _uniq_positive_ints([initiator_user_id] + list(executor_users) + list(mgmt_users))


def _insert_task_event_for_delivery(
    conn,
    *,
    task_id: int,
    event_type: str,
    actor_user_id: int,
    actor_role_id: Optional[int],
    payload: Dict[str, Any],
) -> int:
    """
    Atomic within текущей транзакции:
      - вставляет task_events (returns audit_id)
      - вставляет task_event_recipients (denormalized audience)
    """
    et = (event_type or "").upper().strip()
    if not et:
        raise HTTPException(status_code=500, detail="event_type is required for task_events")

    task_row = conn.execute(
        text("SELECT task_id, initiator_user_id, executor_role_id FROM tasks WHERE task_id = :tid"),
        {"tid": int(task_id)},
    ).mappings().first()
    if not task_row:
        raise HTTPException(status_code=404, detail="Task not found")

    recipients = _resolve_event_recipients_for_task(conn, task_row=dict(task_row))

    audit_id = conn.execute(
        text(
            """
            INSERT INTO task_events (task_id, event_type, actor_user_id, actor_role_id, payload)
            VALUES (:task_id, :event_type, :actor_user_id, :actor_role_id, CAST(:payload AS jsonb))
            RETURNING audit_id
            """
        ),
        {
            "task_id": int(task_id),
            "event_type": et,
            "actor_user_id": int(actor_user_id),
            "actor_role_id": int(actor_role_id) if actor_role_id is not None else None,
            "payload": json.dumps(payload or {}, ensure_ascii=False),
        },
    ).scalar_one()

    if recipients:
        conn.execute(
            text(
                """
                INSERT INTO task_event_recipients (audit_id, user_id)
                SELECT :audit_id, x.user_id
                FROM (
                    SELECT UNNEST(CAST(:uids AS bigint[])) AS user_id
                ) x
                ON CONFLICT DO NOTHING
                """
            ),
            {"audit_id": int(audit_id), "uids": [int(x) for x in recipients]},
        )

    return int(audit_id)


# ---------------------------
# Events API models
# ---------------------------

class TaskEventOut(BaseModel):
    event_type: str
    actor_user_id: Optional[int] = None
    actor_role_id: Optional[int] = None
    created_at: str
    payload: Dict[str, Any] = {}


class MeEventOut(BaseModel):
    audit_id: int
    event_id: int
    task_id: int
    event_type: str
    actor_user_id: Optional[int] = None
    actor_role_id: Optional[int] = None
    created_at: str
    payload: Dict[str, Any] = {}


# ---------------------------
# ACL core
# ---------------------------

def _is_initiator(*, current_user_id: int, task_row: Dict[str, Any]) -> bool:
    try:
        return int(task_row["initiator_user_id"]) == int(current_user_id)
    except Exception:
        return False


def _is_executor_role(*, current_role_id: int, task_row: Dict[str, Any]) -> bool:
    try:
        return int(task_row["executor_role_id"]) == int(current_role_id)
    except Exception:
        return False


def _can_view(*, current_user_id: int, current_role_id: int, task_row: Dict[str, Any]) -> bool:
    if _is_initiator(current_user_id=current_user_id, task_row=task_row):
        return True

    if _is_supervisor_or_deputy(current_role_id):
        return True

    scope = str(task_row.get("assignment_scope") or "").lower()
    if scope == "functional":
        return _is_executor_role(current_role_id=current_role_id, task_row=task_row)

    return False


def _ensure_task_visible_or_404(
    *,
    current_user_id: int,
    current_role_id: int,
    task_row: Optional[Dict[str, Any]],
    include_archived: bool,
) -> Dict[str, Any]:
    if not task_row:
        raise HTTPException(status_code=404, detail="Task not found")

    if not _can_view(current_user_id=current_user_id, current_role_id=current_role_id, task_row=task_row):
        raise HTTPException(status_code=404, detail="Task not found")

    if (not include_archived) and (str(task_row.get("status_code") or "") == "ARCHIVED"):
        raise HTTPException(status_code=404, detail="Task not found")

    return task_row


def _can_report_or_update(*, current_user_id: int, current_role_id: int, task_row: Dict[str, Any]) -> bool:
    if _is_initiator(current_user_id=current_user_id, task_row=task_row):
        return False
    return _is_executor_role(current_role_id=current_role_id, task_row=task_row)


def _can_approve(*, current_user_id: int, current_role_id: int, task_row: Dict[str, Any]) -> bool:
    if _is_initiator(current_user_id=current_user_id, task_row=task_row):
        return True
    if _is_supervisor_or_deputy(current_role_id):
        return True
    return False


def _allowed_actions_for_user(
    *,
    task_row: Dict[str, Any],
    current_user_id: int,
    current_role_id: int,
) -> List[str]:
    code = str(task_row.get("status_code") or "")
    actions: List[str] = []

    if code == "IN_PROGRESS":
        if _can_report_or_update(current_user_id=current_user_id, current_role_id=current_role_id, task_row=task_row):
            actions.append("update")
            actions.append("report")

    elif code == "WAITING_REPORT":
        if _can_report_or_update(current_user_id=current_user_id, current_role_id=current_role_id, task_row=task_row):
            actions.append("report")

    elif code == "WAITING_APPROVAL":
        if _can_approve(current_user_id=current_user_id, current_role_id=current_role_id, task_row=task_row):
            actions.append("approve")
            actions.append("reject")

    return actions


# ---------------------------
# DB loaders
# ---------------------------

def _load_task_full(conn, *, task_id: int) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        text(
            """
            SELECT
                t.task_id,
                t.period_id,
                t.regular_task_id,
                t.title,
                t.description,
                t.initiator_user_id,
                t.executor_role_id,
                t.assignment_scope,
                t.status_id,
                ts.code AS status_code,
                ts.name_ru AS status_name_ru
            FROM tasks t
            LEFT JOIN task_statuses ts ON ts.status_id = t.status_id
            WHERE t.task_id = :task_id
            """
        ),
        {"task_id": int(task_id)},
    ).mappings().first()
    return dict(row) if row else None


def _attach_allowed_actions(
    *,
    task: Dict[str, Any],
    current_user_id: int,
    current_role_id: int,
) -> Dict[str, Any]:
    task = dict(task)
    task["allowed_actions"] = _allowed_actions_for_user(
        task_row=task, current_user_id=current_user_id, current_role_id=current_role_id
    )
    return task


# ---------------------------
# Endpoints
# ---------------------------

@router.get("")
def list_tasks(
    period_id: Optional[int] = Query(None, ge=1),
    status_code: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    include_archived: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    x_user_id: Optional[int] = Header(default=None, alias="X-User-Id"),
) -> Dict[str, Any]:
    current_user_id = _get_current_user_id(x_user_id)
    params: Dict[str, Any] = {"limit": limit, "offset": offset}

    with engine.begin() as conn:
        role_id = _get_user_role_id(conn, current_user_id)
        params["role_id"] = role_id
        params["current_user_id"] = current_user_id

        allowed = _load_assignment_scope_enum_labels(conn)
        if not allowed:
            raise HTTPException(status_code=500, detail="assignment_scope_t enum not found in DB")

        functional_lbl = _scope_label_or_none(allowed, "functional")
        admin_lbl = _scope_label_or_none(allowed, "admin")

        where: List[str] = []

        if _is_supervisor_or_deputy(role_id):
            where.append("1=1")
        else:
            # IMPORTANT ACL FIX:
            # Initiator must always see their tasks (any assignment_scope).
            # Executor can see functional tasks by role_id; admin tasks only if initiator (covered by OR initiator).
            params["functional_scope"] = functional_lbl
            params["admin_scope"] = admin_lbl

            if functional_lbl and admin_lbl:
                where.append(
                    "("
                    "(t.executor_role_id = :role_id AND t.assignment_scope = :functional_scope) "
                    "OR (t.initiator_user_id = :current_user_id)"
                    ")"
                )
            else:
                # fallback if enum labels not detected properly
                where.append(
                    "("
                    "(t.executor_role_id = :role_id) "
                    "OR (t.initiator_user_id = :current_user_id)"
                    ")"
                )

        if period_id is not None:
            where.append("t.period_id = :period_id")
            params["period_id"] = period_id

        if status_code:
            where.append("ts.code = :status_code")
            params["status_code"] = status_code.strip()

        if (not status_code) and (not include_archived):
            where.append("COALESCE(ts.code,'') <> 'ARCHIVED'")

        if search:
            where.append("(t.title ILIKE :q OR COALESCE(t.description,'') ILIKE :q)")
            params["q"] = f"%{search}%"

        where_sql = " AND ".join(where) if where else "1=1"

        total = conn.execute(
            text(
                f"""
                SELECT COUNT(1)
                FROM tasks t
                LEFT JOIN task_statuses ts ON ts.status_id = t.status_id
                WHERE {where_sql}
                """
            ),
            params,
        ).scalar() or 0

        rows = conn.execute(
            text(
                f"""
                SELECT
                    t.task_id,
                    t.period_id,
                    t.regular_task_id,
                    t.title,
                    t.description,
                    t.initiator_user_id,
                    t.executor_role_id,
                    t.assignment_scope,
                    t.status_id,
                    ts.code AS status_code,
                    ts.name_ru AS status_name_ru
                FROM tasks t
                LEFT JOIN task_statuses ts ON ts.status_id = t.status_id
                WHERE {where_sql}
                ORDER BY t.task_id DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        ).mappings().all()

        items: List[Dict[str, Any]] = []
        for r in rows:
            t = dict(r)
            t = _attach_allowed_actions(task=t, current_user_id=current_user_id, current_role_id=role_id)
            items.append(t)

    return {"total": int(total), "limit": limit, "offset": offset, "items": items}


# ---------------------------
# IMPORTANT: /me/events MUST be defined before "/{task_id}" routes
# ---------------------------

@router.get("/me/events", response_model=List[MeEventOut])
def get_my_events(
    x_user_id: Optional[int] = Header(default=None, alias="X-User-Id"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    since_audit_id: Optional[int] = Query(None, ge=1),
    after_id: Optional[int] = Query(None, ge=1),
    event_type: Optional[str] = Query(None),
) -> List[Dict[str, Any]]:
    """
    Лента событий, РЕЛЕВАНТНЫХ пользователю по аудитории (server-side),
    из task_event_recipients + task_events.

    Cursor:
      - since_audit_id (preferred) or after_id (alias). strict ">".
    Ordering:
      - ASC by audit_id for stable cursor consumption.
    """
    current_user_id = _get_current_user_id(x_user_id)
    cursor = since_audit_id if since_audit_id is not None else after_id

    et = (event_type or "").strip()
    et = et.upper() if et else ""

    with engine.begin() as conn:
        params: Dict[str, Any] = {
            "uid": int(current_user_id),
            "limit": int(limit),
            "offset": int(offset),
            "cursor": int(cursor) if cursor is not None else None,
            "event_type": et if et else None,
        }

        rows = conn.execute(
            text(
                """
                SELECT
                    e.audit_id,
                    e.audit_id AS event_id,
                    e.task_id,
                    e.event_type,
                    e.actor_user_id,
                    e.actor_role_id,
                    e.created_at,
                    e.payload::text AS payload_text
                FROM task_event_recipients r
                JOIN task_events e ON e.audit_id = r.audit_id
                JOIN tasks t ON t.task_id = e.task_id
                LEFT JOIN task_statuses ts ON ts.status_id = t.status_id
                WHERE r.user_id = :uid
                  AND (:event_type IS NULL OR e.event_type = :event_type)
                  AND (:cursor IS NULL OR e.audit_id > :cursor)
                  AND COALESCE(ts.code,'') <> 'ARCHIVED'
                ORDER BY e.audit_id ASC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        ).mappings().all()

    out: List[Dict[str, Any]] = []
    for r in rows:
        payload: Dict[str, Any] = {}
        try:
            if r.get("payload_text"):
                payload = json.loads(r["payload_text"])
        except Exception:
            payload = {}

        created_at = r.get("created_at")
        out.append(
            {
                "audit_id": int(r.get("audit_id") or 0),
                "event_id": int(r.get("event_id") or 0),
                "task_id": int(r.get("task_id") or 0),
                "event_type": r.get("event_type"),
                "actor_user_id": r.get("actor_user_id"),
                "actor_role_id": r.get("actor_role_id"),
                "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at),
                "payload": payload,
            }
        )

    return out


@router.get("/{task_id}")
def get_task(
    task_id: int = Path(..., ge=1),
    include_archived: bool = Query(False),
    x_user_id: Optional[int] = Header(default=None, alias="X-User-Id"),
) -> Dict[str, Any]:
    current_user_id = _get_current_user_id(x_user_id)

    with engine.begin() as conn:
        role_id = _get_user_role_id(conn, current_user_id)

        task = _load_task_full(conn, task_id=int(task_id))
        task = _ensure_task_visible_or_404(
            current_user_id=current_user_id,
            current_role_id=role_id,
            task_row=task,
            include_archived=include_archived,
        )

        task = _attach_allowed_actions(task=task, current_user_id=current_user_id, current_role_id=role_id)

    return dict(task)


@router.post("")
def create_task(
    payload: Dict[str, Any],
    x_user_id: Optional[int] = Header(default=None, alias="X-User-Id"),
) -> Dict[str, Any]:
    current_user_id = _get_current_user_id(x_user_id)

    title = (payload.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=422, detail="title is required")

    executor_role_id = payload.get("executor_role_id")
    if not isinstance(executor_role_id, int) or executor_role_id < 1:
        raise HTTPException(status_code=422, detail="executor_role_id is required")

    period_id = payload.get("period_id")
    if not isinstance(period_id, int) or period_id < 1:
        raise HTTPException(status_code=422, detail="period_id is required")

    status_code = (payload.get("status_code") or "IN_PROGRESS").strip()

    with engine.begin() as conn:
        assignment_scope = _normalize_assignment_scope(conn, payload.get("assignment_scope"))
        status_id = _get_status_id_by_code(conn, status_code)

        row = conn.execute(
            text(
                """
                INSERT INTO tasks (
                    period_id,
                    regular_task_id,
                    title,
                    description,
                    initiator_user_id,
                    executor_role_id,
                    assignment_scope,
                    status_id
                )
                VALUES (
                    :period_id,
                    :regular_task_id,
                    :title,
                    :description,
                    :initiator_user_id,
                    :executor_role_id,
                    :assignment_scope,
                    :status_id
                )
                RETURNING task_id
                """
            ),
            {
                "period_id": int(period_id),
                "regular_task_id": payload.get("regular_task_id"),
                "title": title,
                "description": payload.get("description"),
                "initiator_user_id": current_user_id,
                "executor_role_id": int(executor_role_id),
                "assignment_scope": assignment_scope,
                "status_id": status_id,
            },
        ).mappings().first()

        if not row or row.get("task_id") is None:
            raise HTTPException(status_code=500, detail="Failed to create task")

        task_id = int(row["task_id"])

        task = _load_task_full(conn, task_id=task_id)
        if not task:
            raise HTTPException(status_code=500, detail="Task created but not found")

        role_id = _get_user_role_id(conn, current_user_id)
        _write_task_audit(
            conn,
            task_id=int(task_id),
            actor_user_id=int(current_user_id),
            actor_role_id=int(role_id),
            action="CREATE",
            fields_changed=None,
            request_body=payload,
        )

        task = _attach_allowed_actions(task=task, current_user_id=current_user_id, current_role_id=role_id)

    return dict(task)


@router.patch("/{task_id}")
def patch_task(
    payload: Dict[str, Any],
    task_id: int = Path(..., ge=1),
    x_user_id: Optional[int] = Header(default=None, alias="X-User-Id"),
) -> Dict[str, Any]:
    current_user_id = _get_current_user_id(x_user_id)

    allowed_fields = {"title", "description", "assignment_scope"}
    incoming_keys = [k for k in payload.keys() if k in allowed_fields]
    if not incoming_keys:
        raise HTTPException(status_code=422, detail="Nothing to update")

    with engine.begin() as conn:
        role_id = _get_user_role_id(conn, current_user_id)

        task = _load_task_full(conn, task_id=int(task_id))
        task = _ensure_task_visible_or_404(
            current_user_id=current_user_id,
            current_role_id=role_id,
            task_row=task,
            include_archived=False,
        )

        if not _can_report_or_update(current_user_id=current_user_id, current_role_id=role_id, task_row=task):
            raise_error(
                ErrorCode.TASK_FORBIDDEN_PATCH,
                extra={"task_id": int(task_id)},
            )

        status_code = str(task.get("status_code") or "")
        if status_code != "IN_PROGRESS":
            raise_error(
                ErrorCode.TASK_CONFLICT_PATCH_STATUS,
                extra={"task_id": int(task_id), "current_status": status_code or "UNKNOWN"},
            )

        before = {
            "title": task.get("title"),
            "description": task.get("description"),
            "assignment_scope": task.get("assignment_scope"),
        }

        set_parts: List[str] = []
        params: Dict[str, Any] = {"tid": int(task_id)}

        if "title" in payload:
            title = (payload.get("title") or "").strip()
            if not title:
                raise HTTPException(status_code=422, detail="title cannot be empty")
            set_parts.append("title = :title")
            params["title"] = title

        if "description" in payload:
            desc = payload.get("description")
            params["description"] = None if desc is None else str(desc).strip()
            set_parts.append("description = :description")

        if "assignment_scope" in payload:
            scope = _normalize_assignment_scope(conn, payload.get("assignment_scope"))
            set_parts.append("assignment_scope = :assignment_scope")
            params["assignment_scope"] = scope

        if not set_parts:
            raise HTTPException(status_code=422, detail="Nothing to update")

        conn.execute(
            text(
                f"""
                UPDATE tasks
                SET {", ".join(set_parts)}
                WHERE task_id = :tid
                """
            ),
            params,
        )

        after_task = _load_task_full(conn, task_id=int(task_id))
        if not after_task:
            raise HTTPException(status_code=500, detail="Task updated but not found")

        after = {
            "title": after_task.get("title"),
            "description": after_task.get("description"),
            "assignment_scope": after_task.get("assignment_scope"),
        }

        fields_changed: Dict[str, Any] = {}
        for k in ("title", "description", "assignment_scope"):
            if before.get(k) != after.get(k):
                fields_changed[k] = {"from": before.get(k), "to": after.get(k)}

        _write_task_audit(
            conn,
            task_id=int(task_id),
            actor_user_id=int(current_user_id),
            actor_role_id=int(role_id),
            action="PATCH",
            fields_changed=fields_changed,
            request_body=payload,
        )

        after_task = _attach_allowed_actions(task=after_task, current_user_id=current_user_id, current_role_id=role_id)

    return dict(after_task)


# ---------------------------
# Unified actions endpoint (new)
# ---------------------------

@router.post("/{task_id}/actions/{action}")
def task_action(
    payload: Dict[str, Any],
    task_id: int = Path(..., ge=1),
    action: str = Path(..., min_length=1),
    x_user_id: Optional[int] = Header(default=None, alias="X-User-Id"),
) -> Dict[str, Any]:
    action_l = (action or "").strip().lower()

    if action_l == "report":
        return submit_report(payload=payload, task_id=task_id, x_user_id=x_user_id)

    if action_l == "approve":
        p = dict(payload)
        p["approve"] = True
        return approve_report(payload=p, task_id=task_id, x_user_id=x_user_id)

    if action_l == "reject":
        p = dict(payload)
        p["approve"] = False
        return approve_report(payload=p, task_id=task_id, x_user_id=x_user_id)

    raise HTTPException(status_code=422, detail="Unknown action")


@router.post("/{task_id}/report")
def submit_report(
    payload: Dict[str, Any],
    task_id: int = Path(..., ge=1),
    x_user_id: Optional[int] = Header(default=None, alias="X-User-Id"),
) -> Dict[str, Any]:
    current_user_id = _get_current_user_id(x_user_id)

    report_link = (payload.get("report_link") or "").strip()
    if not report_link:
        raise HTTPException(status_code=422, detail="report_link is required")

    current_comment = (payload.get("current_comment") or "").strip()

    with engine.begin() as conn:
        role_id = _get_user_role_id(conn, current_user_id)

        task = _load_task_full(conn, task_id=int(task_id))
        task = _ensure_task_visible_or_404(
            current_user_id=current_user_id,
            current_role_id=role_id,
            task_row=task,
            include_archived=False,
        )

        if not _can_report_or_update(current_user_id=current_user_id, current_role_id=role_id, task_row=task):
            raise_error(
                ErrorCode.TASK_FORBIDDEN_REPORT,
                extra={"task_id": int(task_id)},
            )

        status_code = str(task.get("status_code") or "")
        if status_code not in {"WAITING_REPORT", "IN_PROGRESS"}:
            if status_code in {"WAITING_APPROVAL", "DONE", "ARCHIVED"}:
                raise_error(
                    ErrorCode.TASK_CONFLICT_REPORT_ALREADY_SENT,
                    extra={"task_id": int(task_id), "current_status": status_code},
                )
            raise_error(
                ErrorCode.TASK_CONFLICT_ACTION_STATUS,
                extra={"task_id": int(task_id), "action": "report", "current_status": status_code or "UNKNOWN"},
            )

        from_status = status_code or "UNKNOWN"
        waiting_approval_id = _get_status_id_by_code(conn, "WAITING_APPROVAL")

        conn.execute(
            text(
                """
                INSERT INTO task_reports (task_id, submitted_by, report_link, current_comment, submitted_at, approved_at, approved_by)
                VALUES (:task_id, :submitted_by, :report_link, :current_comment, now(), NULL, NULL)
                ON CONFLICT (task_id)
                DO UPDATE SET
                    submitted_by = EXCLUDED.submitted_by,
                    report_link = EXCLUDED.report_link,
                    current_comment = EXCLUDED.current_comment,
                    submitted_at = now(),
                    approved_at = NULL,
                    approved_by = NULL
                """
            ),
            {
                "task_id": int(task_id),
                "submitted_by": int(current_user_id),
                "report_link": report_link,
                "current_comment": current_comment,
            },
        )

        conn.execute(
            text(
                """
                UPDATE tasks
                SET status_id = :new_status_id
                WHERE task_id = :task_id
                """
            ),
            {"new_status_id": int(waiting_approval_id), "task_id": int(task_id)},
        )

        payload_event = {
            "report_link": report_link,
            "current_comment": current_comment,
            "status_to": "WAITING_APPROVAL",
        }

        _write_task_audit(
            conn,
            task_id=int(task_id),
            actor_user_id=int(current_user_id),
            actor_role_id=int(role_id),
            action="REPORT_SUBMIT",
            fields_changed={"status_code": {"from": from_status, "to": "WAITING_APPROVAL"}},
            request_body=payload,
            event_type="REPORT_SUBMITTED",
            event_payload=payload_event,
        )

        _set_last_audit_event(
            conn,
            task_id=int(task_id),
            actor_user_id=int(current_user_id),
            actor_role_id=int(role_id),
            event_type="REPORT_SUBMITTED",
            event_payload=payload_event,
        )

        # Delivery audience is server-side (Variant A)
        _insert_task_event_for_delivery(
            conn,
            task_id=int(task_id),
            event_type="REPORT_SUBMITTED",
            actor_user_id=int(current_user_id),
            actor_role_id=int(role_id),
            payload=payload_event,
        )

        updated = _load_task_full(conn, task_id=int(task_id))
        if not updated:
            raise HTTPException(status_code=500, detail="Task updated but not found")

        updated = _attach_allowed_actions(task=updated, current_user_id=current_user_id, current_role_id=role_id)

    return dict(updated)


@router.post("/{task_id}/approve")
def approve_report(
    payload: Dict[str, Any],
    task_id: int = Path(..., ge=1),
    x_user_id: Optional[int] = Header(default=None, alias="X-User-Id"),
) -> Dict[str, Any]:
    current_user_id = _get_current_user_id(x_user_id)

    approve = payload.get("approve", True)
    if not isinstance(approve, bool):
        raise HTTPException(status_code=422, detail="approve must be boolean")

    current_comment = (payload.get("current_comment") or "").strip()

    with engine.begin() as conn:
        role_id = _get_user_role_id(conn, current_user_id)

        task = _load_task_full(conn, task_id=int(task_id))
        task = _ensure_task_visible_or_404(
            current_user_id=current_user_id,
            current_role_id=role_id,
            task_row=task,
            include_archived=False,
        )

        if not _can_approve(current_user_id=current_user_id, current_role_id=role_id, task_row=task):
            raise_error(
                ErrorCode.TASK_FORBIDDEN_APPROVE,
                extra={"task_id": int(task_id), "action": "approve" if approve else "reject"},
            )

        status_code = str(task.get("status_code") or "")
        if status_code != "WAITING_APPROVAL":
            raise_error(
                ErrorCode.TASK_CONFLICT_APPROVE_NO_REPORT,
                extra={"task_id": int(task_id), "current_status": status_code or "UNKNOWN"},
            )

        rep = conn.execute(
            text("SELECT task_id FROM task_reports WHERE task_id = :tid"),
            {"tid": int(task_id)},
        ).mappings().first()
        if not rep:
            raise_error(
                ErrorCode.TASK_CONFLICT_APPROVE_NO_REPORT,
                extra={"task_id": int(task_id), "current_status": status_code or "UNKNOWN"},
            )

        if approve:
            done_id = _get_status_id_by_code(conn, "DONE")

            conn.execute(
                text(
                    """
                    UPDATE task_reports
                    SET approved_at = now(),
                        approved_by = :by,
                        current_comment = CASE
                            WHEN :comment = '' THEN current_comment
                            ELSE :comment
                        END
                    WHERE task_id = :tid
                    """
                ),
                {"by": int(current_user_id), "tid": int(task_id), "comment": current_comment},
            )

            conn.execute(
                text("UPDATE tasks SET status_id = :sid WHERE task_id = :tid"),
                {"sid": int(done_id), "tid": int(task_id)},
            )

            payload_event = {"current_comment": current_comment, "status_to": "DONE"}

            _write_task_audit(
                conn,
                task_id=int(task_id),
                actor_user_id=int(current_user_id),
                actor_role_id=int(role_id),
                action="APPROVE",
                fields_changed={"status_code": {"from": "WAITING_APPROVAL", "to": "DONE"}},
                request_body={"approve": True, "current_comment": current_comment},
                event_type="APPROVED",
                event_payload=payload_event,
            )

            _set_last_audit_event(
                conn,
                task_id=int(task_id),
                actor_user_id=int(current_user_id),
                actor_role_id=int(role_id),
                event_type="APPROVED",
                event_payload=payload_event,
            )

            _insert_task_event_for_delivery(
                conn,
                task_id=int(task_id),
                event_type="APPROVED",
                actor_user_id=int(current_user_id),
                actor_role_id=int(role_id),
                payload=payload_event,
            )

        else:
            waiting_report_id = _get_status_id_by_code(conn, "WAITING_REPORT")

            conn.execute(
                text(
                    """
                    UPDATE task_reports
                    SET approved_at = NULL,
                        approved_by = NULL,
                        current_comment = CASE
                            WHEN :comment = '' THEN current_comment
                            ELSE :comment
                        END
                    WHERE task_id = :tid
                    """
                ),
                {"tid": int(task_id), "comment": current_comment},
            )

            conn.execute(
                text("UPDATE tasks SET status_id = :sid WHERE task_id = :tid"),
                {"sid": int(waiting_report_id), "tid": int(task_id)},
            )

            payload_event = {"current_comment": current_comment, "status_to": "WAITING_REPORT"}

            _write_task_audit(
                conn,
                task_id=int(task_id),
                actor_user_id=int(current_user_id),
                actor_role_id=int(role_id),
                action="REJECT",
                fields_changed={"status_code": {"from": "WAITING_APPROVAL", "to": "WAITING_REPORT"}},
                request_body={"approve": False, "current_comment": current_comment},
                event_type="REJECTED",
                event_payload=payload_event,
            )

            _set_last_audit_event(
                conn,
                task_id=int(task_id),
                actor_user_id=int(current_user_id),
                actor_role_id=int(role_id),
                event_type="REJECTED",
                event_payload=payload_event,
            )

            _insert_task_event_for_delivery(
                conn,
                task_id=int(task_id),
                event_type="REJECTED",
                actor_user_id=int(current_user_id),
                actor_role_id=int(role_id),
                payload=payload_event,
            )

        updated = _load_task_full(conn, task_id=int(task_id))
        if not updated:
            raise HTTPException(status_code=500, detail="Task updated but not found")

        updated = _attach_allowed_actions(task=updated, current_user_id=current_user_id, current_role_id=role_id)

    return dict(updated)


# ---------------------------
# Events endpoint (per-task)
# ---------------------------

@router.get("/{task_id}/events", response_model=List[TaskEventOut])
def get_task_events(
    task_id: int = Path(..., ge=1),
    include_archived: bool = Query(False),
    x_user_id: Optional[int] = Header(default=None, alias="X-User-Id"),
    since_audit_id: Optional[int] = Query(None, ge=1),
    after_id: Optional[int] = Query(None, ge=1),
    limit: int = Query(200, ge=1, le=500),
) -> List[Dict[str, Any]]:
    """
    Возвращает только event-записи (event_type IS NOT NULL) из task_audit_log.
    Для polling используйте /tasks/me/events.
    """
    current_user_id = _get_current_user_id(x_user_id)

    cursor = since_audit_id if since_audit_id is not None else after_id

    with engine.begin() as conn:
        role_id = _get_user_role_id(conn, current_user_id)

        task = _load_task_full(conn, task_id=int(task_id))
        _ensure_task_visible_or_404(
            current_user_id=current_user_id,
            current_role_id=role_id,
            task_row=task,
            include_archived=include_archived,
        )

        rows = conn.execute(
            text(
                """
                SELECT
                    audit_id,
                    event_type::text AS event_type,
                    actor_user_id,
                    created_at,
                    actor_role,
                    payload::text AS payload_text
                FROM task_audit_log
                WHERE task_id = :tid
                  AND event_type IS NOT NULL
                  AND (:cursor IS NULL OR audit_id > :cursor)
                ORDER BY audit_id ASC
                LIMIT :limit
                """
            ),
            {"tid": int(task_id), "cursor": cursor, "limit": int(limit)},
        ).mappings().all()

    out: List[Dict[str, Any]] = []
    for r in rows:
        payload: Dict[str, Any] = {}
        try:
            if r.get("payload_text"):
                payload = json.loads(r["payload_text"])
        except Exception:
            payload = {}

        actor_role_id: Optional[int] = None
        try:
            if r.get("actor_role") is not None:
                actor_role_id = int(str(r["actor_role"]))
        except Exception:
            actor_role_id = None

        created_at = r.get("created_at")
        out.append(
            {
                "event_type": r.get("event_type"),
                "actor_user_id": r.get("actor_user_id"),
                "actor_role_id": actor_role_id,
                "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at),
                "payload": payload,
            }
        )

    return out


@router.delete("/{task_id}", status_code=204)
def delete_task(
    task_id: int = Path(..., ge=1),
    x_user_id: Optional[int] = Header(default=None, alias="X-User-Id"),
) -> Response:
    current_user_id = _get_current_user_id(x_user_id)

    with engine.begin() as conn:
        role_id = _get_user_role_id(conn, current_user_id)

        task = _load_task_full(conn, task_id=int(task_id))
        task = _ensure_task_visible_or_404(
            current_user_id=current_user_id,
            current_role_id=role_id,
            task_row=task,
            include_archived=True,
        )

        # intentionally "hide" if not initiator (behavior unchanged)
        if not _is_initiator(current_user_id=current_user_id, task_row=task):
            raise HTTPException(status_code=404, detail="Task not found")

        archived_status_id = _get_status_id_by_code(conn, "ARCHIVED")
        before_status = task.get("status_code")

        updated = conn.execute(
            text(
                """
                UPDATE tasks
                SET status_id = :archived_status_id
                WHERE task_id = :tid
                RETURNING task_id
                """
            ),
            {"archived_status_id": int(archived_status_id), "tid": int(task_id)},
        ).mappings().first()

        if not updated:
            raise HTTPException(status_code=500, detail="Failed to archive task")

        _write_task_audit(
            conn,
            task_id=int(task_id),
            actor_user_id=int(current_user_id),
            actor_role_id=int(role_id),
            action="ARCHIVE",
            fields_changed={"status_code": {"from": before_status, "to": "ARCHIVED"}},
            request_body=None,
        )

    return Response(status_code=204)
