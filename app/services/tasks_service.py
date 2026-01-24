# app/services/tasks_service.py
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Set

from fastapi import HTTPException
from sqlalchemy import text


def parse_int_set_env(name: str) -> Set[int]:
    raw = (os.getenv(name) or "").strip()
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
            pass
    return out


SUPERVISOR_ROLE_IDS: Set[int] = parse_int_set_env("SUPERVISOR_ROLE_IDS")
DEPUTY_ROLE_IDS: Set[int] = parse_int_set_env("DEPUTY_ROLE_IDS")
DIRECTOR_ROLE_IDS: Set[int] = parse_int_set_env("DIRECTOR_ROLE_IDS")


def is_supervisor_or_deputy(role_id: int) -> bool:
    rid = int(role_id)
    return rid in SUPERVISOR_ROLE_IDS or rid in DEPUTY_ROLE_IDS


def get_current_user_id(x_user_id: Optional[int]) -> int:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id header is required")
    return int(x_user_id)


def get_user_role_id(conn, user_id: int) -> int:
    row = conn.execute(
        text("SELECT user_id, role_id FROM users WHERE user_id = :uid"),
        {"uid": int(user_id)},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    if row["role_id"] is None:
        raise HTTPException(status_code=400, detail="User role_id is NULL")
    return int(row["role_id"])


def get_status_id_by_code(conn, code: str) -> int:
    row = conn.execute(
        text("SELECT status_id FROM task_statuses WHERE code = :code"),
        {"code": code},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=400, detail=f"Unknown status code: {code}")
    return int(row["status_id"])


def load_assignment_scope_enum_labels(conn) -> Set[str]:
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


def scope_label_or_none(allowed: Set[str], wanted_lower: str) -> Optional[str]:
    for lbl in allowed:
        if lbl.lower() == wanted_lower:
            return lbl
    return None


def _pick_default_scope(allowed: Set[str]) -> str:
    if any(lbl.lower() == "functional" for lbl in allowed):
        return next(lbl for lbl in allowed if lbl.lower() == "functional")
    return sorted(allowed)[0]


def normalize_assignment_scope(conn, value: Any) -> str:
    allowed = load_assignment_scope_enum_labels(conn)
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


def load_task_full(conn, *, task_id: int) -> Optional[Dict[str, Any]]:
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
    if is_supervisor_or_deputy(current_role_id):
        return True

    scope = str(task_row.get("assignment_scope") or "").lower()
    if scope == "functional":
        return _is_executor_role(current_role_id=current_role_id, task_row=task_row)

    return False


def ensure_task_visible_or_404(
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


def can_report_or_update(*, current_user_id: int, current_role_id: int, task_row: Dict[str, Any]) -> bool:
    if _is_initiator(current_user_id=current_user_id, task_row=task_row):
        return False
    return _is_executor_role(current_role_id=current_role_id, task_row=task_row)


def can_approve(*, current_user_id: int, current_role_id: int, task_row: Dict[str, Any]) -> bool:
    if _is_initiator(current_user_id=current_user_id, task_row=task_row):
        return True
    if is_supervisor_or_deputy(current_role_id):
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
        if can_report_or_update(current_user_id=current_user_id, current_role_id=current_role_id, task_row=task_row):
            actions.append("update")
            actions.append("report")

    elif code == "WAITING_REPORT":
        if can_report_or_update(current_user_id=current_user_id, current_role_id=current_role_id, task_row=task_row):
            actions.append("report")

    elif code == "WAITING_APPROVAL":
        if can_approve(current_user_id=current_user_id, current_role_id=current_role_id, task_row=task_row):
            actions.append("approve")
            actions.append("reject")

    return actions


def attach_allowed_actions(
    *,
    task: Dict[str, Any],
    current_user_id: int,
    current_role_id: int,
) -> Dict[str, Any]:
    t = dict(task)
    t["allowed_actions"] = _allowed_actions_for_user(
        task_row=t, current_user_id=current_user_id, current_role_id=current_role_id
    )
    return t


def write_task_audit(
    conn,
    *,
    task_id: int,
    actor_user_id: int,
    actor_role_id: Optional[int],
    action: str,
    fields_changed: Optional[Dict[str, Any]] = None,
    request_body: Optional[Dict[str, Any]] = None,
    meta: Optional[Dict[str, Any]] = None,
    event_type: Optional[str] = None,
    event_payload: Optional[Dict[str, Any]] = None,
) -> None:
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
