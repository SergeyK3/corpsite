# FILE: app/events.py
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Set

from sqlalchemy import text

from app.db.engine import engine


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


def _parse_str_set(env_name: str) -> Set[str]:
    raw = (os.getenv(env_name) or "").strip()
    if not raw:
        return set()
    out: Set[str] = set()
    for part in raw.split(","):
        p = part.strip()
        if not p:
            continue
        out.add(p.upper())
    return out


SUPERVISOR_ROLE_IDS = _parse_int_set("SUPERVISOR_ROLE_IDS")
DEPUTY_ROLE_IDS = _parse_int_set("DEPUTY_ROLE_IDS")
DIRECTOR_ROLE_IDS = _parse_int_set("DIRECTOR_ROLE_IDS")

# 🔒 allow-list Telegram (если пусто — ограничения нет)
TELEGRAM_DELIVERY_ALLOW_USER_IDS: Set[int] = _parse_int_set(
    "TELEGRAM_DELIVERY_ALLOW_USER_IDS"
)

# optional: какие события не отправлять самому актору
DROP_SELF_FOR_TYPES: Set[str] = _parse_str_set("TASK_EVENTS_DROP_SELF_TYPES")

# optional: для каких типов событий создавать non-system deliveries
TELEGRAM_FOR_TYPES: Set[str] = _parse_str_set("TASK_EVENTS_TELEGRAM_TYPES")


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
    et = (event_type or "").upper().strip()
    if DROP_SELF_FOR_TYPES:
        return et in DROP_SELF_FOR_TYPES
    return False


def _channels_for_event_type(event_type: str) -> List[str]:
    et = (event_type or "").upper().strip()

    if TELEGRAM_FOR_TYPES:
        if et in TELEGRAM_FOR_TYPES:
            return ["telegram"]
        return []

    if et in {
        "REPORT_SUBMITTED",
        "REPORT_APPROVED",
        "REPORT_REJECTED",
        "REPORT_ARCHIVED",
        "APPROVED",
        "REJECTED",
        "ARCHIVED",
    }:
        return ["telegram"]

    return []


@dataclass(frozen=True)
class TaskAudienceInput:
    task_id: int
    initiator_user_id: int
    executor_role_id: int


def _extract_bindings(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not payload:
        return []
    b = payload.get("bindings")
    if not isinstance(b, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in b:
        if not isinstance(item, dict):
            continue
        t = str(item.get("type") or "").strip().lower()
        rid = item.get("id")
        try:
            iid = int(rid)
        except Exception:
            continue
        if iid <= 0:
            continue
        if t not in ("user", "role"):
            continue
        out.append({"type": t, "id": iid})
    return out


def _resolve_bindings_to_user_ids_tx(conn, bindings: List[Dict[str, Any]]) -> List[int]:
    user_ids: List[int] = []
    role_ids: List[int] = []

    for b in bindings:
        t = b["type"]
        iid = int(b["id"])
        if t == "user":
            user_ids.append(iid)
        elif t == "role":
            role_ids.append(iid)

    out = _uniq_ints(user_ids)

    if role_ids:
        rows = conn.execute(
            text(
                """
                SELECT u.user_id
                FROM public.users u
                WHERE u.role_id = ANY(:rids)
                  AND COALESCE(u.is_active, true) = true
                """
            ),
            {"rids": sorted(set(role_ids))},
        ).scalars().all()
        out = _uniq_ints(out + [int(x) for x in rows])

    return out


def resolve_recipients_for_task_event_tx(
    conn,
    *,
    task: TaskAudienceInput,
    event_type: str,
    actor_user_id: int,
    payload: Optional[Dict[str, Any]] = None,
) -> List[int]:
    et = (event_type or "").upper().strip()
    payload = payload or {}

    bindings = _extract_bindings(payload)
    if bindings:
        recipients = _resolve_bindings_to_user_ids_tx(conn, bindings)
    else:
        executor_users = conn.execute(
            text(
                """
                SELECT u.user_id
                FROM public.users u
                WHERE u.role_id = :rid
                  AND COALESCE(u.is_active, true) = true
                """
            ),
            {"rid": int(task.executor_role_id)},
        ).scalars().all()

        mgmt_role_ids = sorted(
            set(SUPERVISOR_ROLE_IDS) | set(DEPUTY_ROLE_IDS) | set(DIRECTOR_ROLE_IDS)
        )
        mgmt_users: List[int] = []
        if mgmt_role_ids:
            mgmt_users = conn.execute(
                text(
                    """
                    SELECT u.user_id
                    FROM public.users u
                    WHERE u.role_id = ANY(:rids)
                      AND COALESCE(u.is_active, true) = true
                    """
                ),
                {"rids": mgmt_role_ids},
            ).scalars().all()

        recipients = _uniq_ints(
            [task.initiator_user_id]
            + [int(x) for x in executor_users]
            + [int(x) for x in mgmt_users]
        )

    if _should_drop_self(et):
        recipients = [uid for uid in recipients if uid != int(actor_user_id)]

    return recipients


def create_task_event_tx(
    conn,
    *,
    task_id: int,
    event_type: str,
    actor_user_id: int,
    actor_role_id: Optional[int],
    payload: Optional[Dict[str, Any]] = None,
) -> int:
    et = (event_type or "").upper().strip()
    if not et:
        raise ValueError("event_type is required")

    payload = payload or {}

    row = conn.execute(
        text(
            """
            SELECT task_id, initiator_user_id, executor_role_id
            FROM public.tasks
            WHERE task_id = :tid
            """
        ),
        {"tid": int(task_id)},
    ).mappings().first()
    if not row:
        raise ValueError(f"Task not found: {task_id}")

    task = TaskAudienceInput(
        task_id=int(row["task_id"]),
        initiator_user_id=int(row["initiator_user_id"]),
        executor_role_id=int(row["executor_role_id"]),
    )

    recipients = resolve_recipients_for_task_event_tx(
        conn,
        task=task,
        event_type=et,
        actor_user_id=int(actor_user_id),
        payload=payload,
    )

    audit_id = conn.execute(
        text(
            """
            INSERT INTO public.task_events
              (task_id, event_type, actor_user_id, actor_role_id, payload)
            VALUES
              (:task_id, :event_type, :actor_user_id, :actor_role_id, CAST(:payload AS jsonb))
            RETURNING audit_id
            """
        ),
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
            text(
                """
                INSERT INTO public.task_event_recipients (audit_id, user_id)
                SELECT :audit_id, x.user_id
                FROM (
                    SELECT UNNEST(CAST(:uids AS bigint[])) AS user_id
                ) x
                ON CONFLICT DO NOTHING
                """
            ),
            {"audit_id": int(audit_id), "uids": recipients},
        )

        # system — всегда SENT
        conn.execute(
            text(
                """
                INSERT INTO public.task_event_deliveries
                  (audit_id, user_id, channel, status)
                SELECT :audit_id, x.user_id, 'system', 'SENT'
                FROM (
                    SELECT UNNEST(CAST(:uids AS bigint[])) AS user_id
                ) x
                ON CONFLICT (audit_id, user_id, channel) DO NOTHING
                """
            ),
            {"audit_id": int(audit_id), "uids": recipients},
        )

        channels = _channels_for_event_type(et)
        if channels:
            filtered_uids = recipients
            if "telegram" in channels and TELEGRAM_DELIVERY_ALLOW_USER_IDS:
                filtered_uids = [
                    uid for uid in recipients if uid in TELEGRAM_DELIVERY_ALLOW_USER_IDS
                ]

            if filtered_uids:
                conn.execute(
                    text(
                        """
                        INSERT INTO public.task_event_deliveries
                          (audit_id, user_id, channel, status)
                        SELECT :audit_id, x.user_id, x.channel, 'PENDING'
                        FROM (
                            SELECT
                              u.user_id,
                              c.channel
                            FROM UNNEST(CAST(:uids AS bigint[])) AS u(user_id)
                            CROSS JOIN UNNEST(CAST(:channels AS text[])) AS c(channel)
                        ) x
                        ON CONFLICT (audit_id, user_id, channel) DO NOTHING
                        """
                    ),
                    {
                        "audit_id": int(audit_id),
                        "uids": filtered_uids,
                        "channels": channels,
                    },
                )

            skipped_uids = [uid for uid in recipients if uid not in filtered_uids]
            if skipped_uids:
                conn.execute(
                    text(
                        """
                        INSERT INTO public.task_event_deliveries
                          (audit_id, user_id, channel, status, error_code, error_text, sent_at)
                        SELECT :audit_id, x.user_id, 'telegram', 'FAILED',
                               'NO_BINDING',
                               'Telegram delivery skipped by policy',
                               now()
                        FROM (
                            SELECT UNNEST(CAST(:uids AS bigint[])) AS user_id
                        ) x
                        ON CONFLICT (audit_id, user_id, channel) DO NOTHING
                        """
                    ),
                    {"audit_id": int(audit_id), "uids": skipped_uids},
                )

    return int(audit_id)


def create_task_event(
    *,
    task_id: int,
    event_type: str,
    actor_user_id: int,
    actor_role_id: Optional[int],
    payload: Optional[Dict[str, Any]] = None,
) -> int:
    with engine.begin() as conn:
        return create_task_event_tx(
            conn,
            task_id=task_id,
            event_type=event_type,
            actor_user_id=actor_user_id,
            actor_role_id=actor_role_id,
            payload=payload,
        )
