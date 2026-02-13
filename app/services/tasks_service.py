# FILE: app/services/tasks_service.py
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
            # ignore invalid pieces
            pass
    return out


SUPERVISOR_ROLE_IDS: Set[int] = parse_int_set_env("SUPERVISOR_ROLE_IDS")
DEPUTY_ROLE_IDS: Set[int] = parse_int_set_env("DEPUTY_ROLE_IDS")
DIRECTOR_ROLE_IDS: Set[int] = parse_int_set_env("DIRECTOR_ROLE_IDS")


def is_supervisor_or_deputy(role_id: Any) -> bool:
    try:
        rid = int(role_id)
    except Exception:
        return False
    return rid in SUPERVISOR_ROLE_IDS or rid in DEPUTY_ROLE_IDS


def get_current_user_id(x_user_id: Optional[int]) -> int:
    # do not treat 0/"" as "missing" silently; validate explicitly
    if x_user_id is None:
        raise HTTPException(status_code=401, detail="X-User-Id header is required")
    try:
        uid = int(x_user_id)
    except Exception:
        raise HTTPException(status_code=401, detail="X-User-Id header must be an integer")
    if uid <= 0:
        raise HTTPException(status_code=401, detail="X-User-Id header must be a positive integer")
    return uid


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
    # Prefer functional if present; otherwise first stable label
    for lbl in allowed:
        if lbl.lower() == "functional":
            return lbl
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

    # legacy aliases
    legacy_map = {
        "role": "functional",
        "any": "functional",
        "user": "admin",
    }
    if raw_l in legacy_map:
        target_l = legacy_map[raw_l].lower()
        mapped = scope_label_or_none(allowed, target_l)
        if mapped:
            return mapped

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
    # Initiator sees own tasks
    if _is_initiator(current_user_id=current_user_id, task_row=task_row):
        return True

    # Global privileged view (current behavior)
    if is_supervisor_or_deputy(current_role_id):
        return True

    scope = str(task_row.get("assignment_scope") or "").lower()
    if scope == "functional":
        return _is_executor_role(current_role_id=current_role_id, task_row=task_row)

    # Other scopes currently not viewable unless initiator/supervisor/deputy
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
    """
    Кто может отправлять/обновлять отчёт.

    Ранее: инициатор всегда запрещён.
    Проблема: тестовый пайплайн, когда инициатор = исполнитель по роли (executor_role_id),
    нельзя было сдать отчёт.

    Новое правило:
      - если пользователь является исполнителем по роли (executor_role_id == current_role_id) -> можно
      - иначе (в т.ч. инициатор без роли исполнителя) -> нельзя
    """
    if _is_executor_role(current_role_id=current_role_id, task_row=task_row):
        return True
    return False


def can_approve(*, current_user_id: int, current_role_id: int, task_row: Dict[str, Any]) -> bool:
    if _is_initiator(current_user_id=current_user_id, task_row=task_row):
        return True
    if is_supervisor_or_deputy(current_role_id):
        return True
    return False


def can_reject_task(*, current_user_id: int, current_role_id: int, task_row: Dict[str, Any]) -> bool:
    """
    Кто может делать reject задачи (не review-reject отчёта, а task-level reject из IN_PROGRESS/WAITING_REPORT).

    Политика (минимальная, практичная):
      - инициатор может отклонить задачу
      - supervisor/deputy может отклонить задачу
      - исполнитель по роли может отклонить (если это нужно как "отказ исполнителя")
    """
    if _is_initiator(current_user_id=current_user_id, task_row=task_row):
        return True
    if is_supervisor_or_deputy(current_role_id):
        return True
    if _is_executor_role(current_role_id=current_role_id, task_row=task_row):
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

    if code in ("IN_PROGRESS", "WAITING_REPORT"):
        if can_report_or_update(
            current_user_id=current_user_id,
            current_role_id=current_role_id,
            task_row=task_row,
        ):
            actions.append("report")

        # NEW: task-level reject из IN_PROGRESS/WAITING_REPORT
        if can_reject_task(
            current_user_id=current_user_id,
            current_role_id=current_role_id,
            task_row=task_row,
        ):
            actions.append("reject")

    if code == "WAITING_APPROVAL":
        if can_approve(
            current_user_id=current_user_id,
            current_role_id=current_role_id,
            task_row=task_row,
        ):
            actions.append("approve")
            # review-reject: WAITING_APPROVAL -> WAITING_REPORT (отклонить отчёт)
            actions.append("reject")

    if _is_initiator(current_user_id=current_user_id, task_row=task_row) and code != "ARCHIVED":
        actions.append("archive")

    # стабильный порядок для UI/тестов (необязательно, но удобно)
    # убираем дубли на всякий случай
    seen: Set[str] = set()
    out: List[str] = []
    for a in actions:
        if a in seen:
            continue
        seen.add(a)
        out.append(a)
    return out


def attach_allowed_actions(
    *,
    task: Dict[str, Any],
    current_user_id: int,
    current_role_id: int,
) -> Dict[str, Any]:
    t = dict(task)
    t["allowed_actions"] = _allowed_actions_for_user(
        task_row=t,
        current_user_id=current_user_id,
        current_role_id=current_role_id,
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
            "payload": json.dumps(event_payload or {}) if event_type is not None else json.dumps({}),
        },
    )
