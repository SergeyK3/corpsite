from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Set

from sqlalchemy import text

from app.db.engine import engine


# ---------------------------
# env helpers
# ---------------------------

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
            continue
    return out


SUPERVISOR_ROLE_IDS = _parse_int_set("SUPERVISOR_ROLE_IDS")
DEPUTY_ROLE_IDS = _parse_int_set("DEPUTY_ROLE_IDS")
DIRECTOR_ROLE_IDS = _parse_int_set("DIRECTOR_ROLE_IDS")  # добавьте в .env при необходимости


def _uniq_ints(xs: Iterable[Optional[int]]) -> List[int]:
    out: List[int] = []
    seen: Set[int] = set()
    for x in xs:
        if x is None:
            continue
        try:
            ix = int(x)
        except Exception:
            continue
        if ix <= 0 or ix in seen:
            continue
        seen.add(ix)
        out.append(ix)
    return out


def _should_drop_self(event_type: str) -> bool:
    """
    Backend policy для self-echo. По умолчанию выключено.
    Включите нужные типы, если решите.
    """
    DROP_SELF_FOR_TYPES: Set[str] = set()  # например {"REPORT_SUBMITTED"}
    return event_type in DROP_SELF_FOR_TYPES


# ---------------------------
# Audience Resolver (role-based)
# ---------------------------

@dataclass(frozen=True)
class TaskAudienceInput:
    task_id: int
    initiator_user_id: int
    executor_role_id: int


def resolve_recipients_for_task_event(
    *,
    task: TaskAudienceInput,
    event_type: str,
    actor_user_id: int,
) -> List[int]:
    """
    Возвращает список user_id, которым видно событие.

    Логика:
      - initiator всегда
      - все пользователи роли executor_role_id
      - все supervisors/deputies/directors по env-наборам role_id
    """
    et = (event_type or "").upper().strip()

    with engine.begin() as conn:
        # 1) Исполнители: все пользователи с role_id = executor_role_id
        executor_users = conn.execute(
            text("""
                SELECT u.user_id
                FROM public.users u
                WHERE u.role_id = :rid
            """),
            {"rid": int(task.executor_role_id)},
        ).scalars().all()

        # 2) Руководители/замы/директора: все пользователи с role_id в наборах
        mgmt_role_ids = sorted(set(SUPERVISOR_ROLE_IDS) | set(DEPUTY_ROLE_IDS) | set(DIRECTOR_ROLE_IDS))
        mgmt_users: List[int] = []
        if mgmt_role_ids:
            mgmt_users = conn.execute(
                text("""
                    SELECT u.user_id
                    FROM public.users u
                    WHERE u.role_id = ANY(CAST(:rids AS bigint[]))
                """),
                {"rids": [int(x) for x in mgmt_role_ids]},
            ).scalars().all()

    recipients = _uniq_ints(
        [int(task.initiator_user_id)] + [int(x) for x in executor_users] + [int(x) for x in mgmt_users]
    )

    # (опционально) self-echo policy на backend
    if _should_drop_self(et):
        recipients = [uid for uid in recipients if uid != int(actor_user_id)]

    return recipients


# ---------------------------
# Event creation (event + recipients in one tx)
# ---------------------------

def create_task_event(
    *,
    task_id: int,
    event_type: str,
    actor_user_id: int,
    actor_role_id: Optional[int],
    payload: Optional[Dict[str, Any]] = None,
) -> int:
    """
    Пишет:
      - task_events
      - task_event_recipients (денормализованная аудитория)
    Возвращает audit_id (cursor).
    """
    et = (event_type or "").upper().strip()
    if not et:
        raise ValueError("event_type is required")

    payload = payload or {}

    with engine.begin() as conn:
        # Берём минимально нужные поля из tasks
        row = conn.execute(
            text("""
                SELECT task_id, initiator_user_id, executor_role_id
                FROM public.tasks
                WHERE task_id = :tid
            """),
            {"tid": int(task_id)},
        ).mappings().first()

        if not row:
            raise ValueError(f"Task not found: {task_id}")

        task = TaskAudienceInput(
            task_id=int(row["task_id"]),
            initiator_user_id=int(row["initiator_user_id"]),
            executor_role_id=int(row["executor_role_id"]),
        )

        recipients = resolve_recipients_for_task_event(
            task=task,
            event_type=et,
            actor_user_id=int(actor_user_id),
        )

        audit_id = conn.execute(
            text("""
                INSERT INTO public.task_events (task_id, event_type, actor_user_id, actor_role_id, payload)
                VALUES (:task_id, :event_type, :actor_user_id, :actor_role_id, CAST(:payload AS jsonb))
                RETURNING audit_id
            """),
            {
                "task_id": int(task_id),
                "event_type": et,
                "actor_user_id": int(actor_user_id),
                "actor_role_id": int(actor_role_id) if actor_role_id is not None else None,
                "payload": json.dumps(payload, ensure_ascii=False),
            },
        ).scalar_one()

        if recipients:
            conn.execute(
                text("""
                    INSERT INTO public.task_event_recipients (audit_id, user_id)
                    SELECT :audit_id, x.user_id
                    FROM (
                        SELECT UNNEST(CAST(:uids AS bigint[])) AS user_id
                    ) x
                    ON CONFLICT DO NOTHING
                """),
                {"audit_id": int(audit_id), "uids": [int(x) for x in recipients]},
            )

        return int(audit_id)
