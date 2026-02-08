# FILE: app/task_events.py

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, Query
from sqlalchemy import text

from app.db.engine import engine

router = APIRouter(prefix="/tasks", tags=["tasks"])


# ---------------------------
# Utils
# ---------------------------

def _require_user_id(x_user_id: Optional[str]) -> int:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-Id header.")
    s = str(x_user_id).strip()
    if not s:
        raise HTTPException(status_code=400, detail="Invalid X-User-Id header.")
    try:
        uid = int(s)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid X-User-Id header.")
    if uid <= 0:
        raise HTTPException(status_code=400, detail="Invalid X-User-Id header.")
    return uid


def _as_dict_payload(v: Any) -> Dict[str, Any]:
    if v is None:
        return {}
    if isinstance(v, dict):
        return v
    if isinstance(v, str):
        try:
            j = json.loads(v)
            return j if isinstance(j, dict) else {"_raw": v}
        except Exception:
            return {"_raw": v}
    return {}


def _safe_int(v: Any) -> Optional[int]:
    try:
        if v is None:
            return None
        if isinstance(v, bool):
            return None
        return int(v)
    except Exception:
        return None


def _parse_dt(v: Any) -> Optional[datetime]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            return datetime.fromisoformat(s)
        except Exception:
            return None
    return None


def _norm_channel(v: Any) -> str:
    return str(v or "").strip().lower()


# ---------------------------
# Public: per-user events feed (recipients)
# ---------------------------

@router.get("/me/events")
def list_my_task_events(
    *,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    since_audit_id: int = Query(
        default=0,
        ge=0,
        description="Последний доставленный audit_id (cursor). Вернём события > since_audit_id.",
    ),
    limit: int = Query(default=50, ge=1, le=200),
) -> Dict[str, Any]:
    uid = _require_user_id(x_user_id)

    q = text(
        """
        SELECT
          e.audit_id,
          e.task_id,
          e.event_type,
          e.actor_user_id,
          e.actor_role_id,
          e.payload
        FROM public.task_event_recipients r
        JOIN public.task_events e ON e.audit_id = r.audit_id
        WHERE r.user_id = :uid
          AND e.audit_id > :cursor
        ORDER BY e.audit_id ASC
        LIMIT :limit
        """
    )

    with engine.begin() as conn:
        rows = conn.execute(
            q,
            {"uid": int(uid), "cursor": int(since_audit_id), "limit": int(limit)},
        ).mappings().all()

    items: List[Dict[str, Any]] = []
    next_cursor = int(since_audit_id)

    for r in rows:
        audit_id = int(r["audit_id"])
        next_cursor = max(next_cursor, audit_id)

        items.append(
            {
                "audit_id": audit_id,
                "task_id": int(r["task_id"]),
                "event_type": str(r["event_type"] or ""),
                "actor_user_id": int(r["actor_user_id"]) if r.get("actor_user_id") is not None else None,
                "actor_role_id": int(r["actor_role_id"]) if r.get("actor_role_id") is not None else None,
                "payload": _as_dict_payload(r.get("payload")),
            }
        )

    return {"items": items, "next_cursor": next_cursor}


# ---------------------------
# Analytics: deliveries summary
# ---------------------------

@router.get("/analytics/task-events/summary")
def analytics_task_events_summary(
    *,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    from_ts: Optional[datetime] = Query(default=None, description="Начало окна (inclusive), task_events.created_at >= from_ts"),
    to_ts: Optional[datetime] = Query(default=None, description="Конец окна (exclusive), task_events.created_at < to_ts"),
    event_type: Optional[str] = Query(default=None, description="Фильтр по task_events.event_type"),
    task_id: Optional[int] = Query(default=None, ge=1, description="Фильтр по task_id"),
    cursor_from: Optional[int] = Query(default=None, ge=0, description="Фильтр по audit_id >= cursor_from"),
    cursor_to: Optional[int] = Query(default=None, ge=0, description="Фильтр по audit_id <= cursor_to"),
    channel: Optional[str] = Query(
        default=None,
        description="Канал фактической доставки (telegram/ui/email/...). Если NULL — combined (все кроме system). Если system — считаем system.",
    ),
    only_with_deliveries: bool = Query(
        default=False,
        description="Если true — учитываем только события, у которых есть baseline deliveries (system).",
    ),
) -> Dict[str, Any]:
    _ = _require_user_id(x_user_id)

    ch_raw = (channel or "").strip()
    ch = ch_raw.lower() if ch_raw else None
    et = (event_type or "").strip() or None

    # facts/latency выбор канала:
    # - channel is NULL  => combined: d.channel <> 'system'
    # - channel == system => d.channel = 'system'
    # - else => d.channel = :channel AND d.channel <> 'system' (по сути просто d.channel=:channel)
    q = text(
        """
        WITH base_events AS (
          SELECT
            e.audit_id,
            e.task_id,
            e.event_type,
            e.created_at
          FROM public.task_events e
          WHERE
            (:from_ts IS NULL OR e.created_at >= :from_ts)
            AND (:to_ts IS NULL OR e.created_at <  :to_ts)
            AND (:event_type IS NULL OR e.event_type = :event_type)
            AND (:task_id IS NULL OR e.task_id = :task_id)
            AND (:cursor_from IS NULL OR e.audit_id >= :cursor_from)
            AND (:cursor_to IS NULL OR e.audit_id <= :cursor_to)
        ),
        expected_per_audit AS (
          SELECT
            d.audit_id,
            COUNT(*)::int AS expected
          FROM public.task_event_deliveries d
          JOIN base_events e ON e.audit_id = d.audit_id
          WHERE d.channel = 'system'
          GROUP BY d.audit_id
        ),
        facts_per_audit AS (
          SELECT
            d.audit_id,
            SUM(CASE WHEN d.status = 'SENT'   THEN 1 ELSE 0 END)::int AS done,
            SUM(CASE WHEN d.status = 'FAILED' THEN 1 ELSE 0 END)::int AS failed
          FROM public.task_event_deliveries d
          JOIN base_events e ON e.audit_id = d.audit_id
          WHERE
            (
              (:channel IS NULL AND d.channel <> 'system')
              OR (:channel = 'system' AND d.channel = 'system')
              OR (:channel IS NOT NULL AND :channel <> 'system' AND d.channel = :channel)
            )
          GROUP BY d.audit_id
        ),
        per_event AS (
          SELECT
            e.audit_id,
            e.event_type,
            COALESCE(x.expected, 0)::int AS expected,
            COALESCE(f.done, 0)::int     AS done,
            COALESCE(f.failed, 0)::int   AS failed,
            GREATEST(COALESCE(x.expected,0) - COALESCE(f.done,0) - COALESCE(f.failed,0), 0)::int AS pending
          FROM base_events e
          LEFT JOIN expected_per_audit x ON x.audit_id = e.audit_id
          LEFT JOIN facts_per_audit f ON f.audit_id = e.audit_id
          WHERE (:only_with_deliveries = false OR COALESCE(x.expected,0) > 0)
        ),
        latencies AS (
          SELECT
            e.event_type,
            EXTRACT(EPOCH FROM (d.sent_at - d.created_at))::numeric AS sec
          FROM public.task_event_deliveries d
          JOIN base_events e ON e.audit_id = d.audit_id
          WHERE
            (
              (:channel IS NULL AND d.channel <> 'system')
              OR (:channel = 'system' AND d.channel = 'system')
              OR (:channel IS NOT NULL AND :channel <> 'system' AND d.channel = :channel)
            )
            AND d.sent_at IS NOT NULL
            AND d.status IN ('SENT','FAILED')
        ),
        totals AS (
          SELECT
            COUNT(*)::int AS events,
            COALESCE(SUM(expected),0)::int AS deliveries_expected,
            COALESCE(SUM(done),0)::int     AS deliveries_done,
            COALESCE(SUM(failed),0)::int   AS deliveries_failed,
            COALESCE(SUM(pending),0)::int  AS deliveries_pending,
            CASE WHEN COALESCE(SUM(expected),0) > 0
              THEN ROUND((COALESCE(SUM(done),0)::numeric / SUM(expected)::numeric), 6)
              ELSE 0
            END AS delivery_rate
          FROM per_event
        ),
        latency_totals AS (
          SELECT
            COALESCE(ROUND(AVG(sec)::numeric, 0), 0) AS avg,
            COALESCE(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY sec), 0) AS p50,
            COALESCE(PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY sec), 0) AS p90,
            COALESCE(PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY sec), 0) AS p99
          FROM latencies
        ),
        per_type AS (
          SELECT
            p.event_type,
            COUNT(*)::int AS events,
            COALESCE(SUM(p.expected),0)::int AS expected,
            COALESCE(SUM(p.done),0)::int     AS done,
            COALESCE(SUM(p.failed),0)::int   AS failed,
            COALESCE(SUM(p.pending),0)::int  AS pending
          FROM per_event p
          GROUP BY p.event_type
        ),
        latency_by_type AS (
          SELECT
            l.event_type,
            COALESCE(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY l.sec), 0) AS p50,
            COALESCE(PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY l.sec), 0) AS p90
          FROM latencies l
          GROUP BY l.event_type
        ),
        by_type_json AS (
          SELECT COALESCE(
            jsonb_agg(
              jsonb_build_object(
                'event_type', t.event_type,
                'events', t.events,
                'expected', t.expected,
                'done', t.done,
                'failed', t.failed,
                'pending', t.pending,
                'p50', COALESCE(lb.p50, 0),
                'p90', COALESCE(lb.p90, 0)
              )
              ORDER BY t.event_type
            ),
            '[]'::jsonb
          ) AS by_type
          FROM per_type t
          LEFT JOIN latency_by_type lb ON lb.event_type = t.event_type
        ),
        by_channel_json AS (
          SELECT jsonb_build_array(
            jsonb_build_object(
              'channel', COALESCE(:channel, 'combined'),
              'expected', COALESCE(SUM(expected),0)::int,
              'done', COALESCE(SUM(done),0)::int,
              'failed', COALESCE(SUM(failed),0)::int,
              'pending', COALESCE(SUM(pending),0)::int
            )
          ) AS by_channel
          FROM per_event
        )
        SELECT
          jsonb_build_object(
            'events', (SELECT events FROM totals),
            'delivery_rate', (SELECT delivery_rate FROM totals),
            'deliveries_done', (SELECT deliveries_done FROM totals),
            'deliveries_failed', (SELECT deliveries_failed FROM totals),
            'deliveries_pending', (SELECT deliveries_pending FROM totals),
            'deliveries_expected', (SELECT deliveries_expected FROM totals)
          ) AS totals,
          jsonb_build_object(
            'avg', (SELECT avg FROM latency_totals),
            'p50', (SELECT p50 FROM latency_totals),
            'p90', (SELECT p90 FROM latency_totals),
            'p99', (SELECT p99 FROM latency_totals)
          ) AS latency_sec,
          (SELECT by_type FROM by_type_json) AS by_type,
          (SELECT by_channel FROM by_channel_json) AS by_channel
        ;
        """
    )

    params = {
        "from_ts": from_ts,
        "to_ts": to_ts,
        "event_type": et,
        "task_id": int(task_id) if task_id is not None else None,
        "cursor_from": int(cursor_from) if cursor_from is not None else None,
        "cursor_to": int(cursor_to) if cursor_to is not None else None,
        "channel": ch,
        "only_with_deliveries": bool(only_with_deliveries),
    }

    with engine.begin() as conn:
        row = conn.execute(q, params).mappings().first()

    if not row:
        return {
            "totals": {
                "events": 0,
                "deliveries_expected": 0,
                "deliveries_done": 0,
                "deliveries_failed": 0,
                "deliveries_pending": 0,
                "delivery_rate": 0,
            },
            "latency_sec": {"avg": 0, "p50": 0, "p90": 0, "p99": 0},
            "by_type": [],
            "by_channel": [],
        }

    return {
        "totals": row.get("totals") or {},
        "latency_sec": row.get("latency_sec") or {"avg": 0, "p50": 0, "p90": 0, "p99": 0},
        "by_type": row.get("by_type") or [],
        "by_channel": row.get("by_channel") or [],
    }


# ---------------------------
# Internal: pending deliveries queue + ack (worker result)
# ---------------------------

@router.get("/internal/task-event-deliveries/pending")
def list_pending_deliveries(
    *,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    channel: str = Query(default="telegram", description="Канал очереди (например telegram)."),
    cursor_from: int = Query(default=0, ge=0, description="Вернём записи с audit_id > cursor_from."),
    limit: int = Query(default=200, ge=1, le=1000),
) -> Dict[str, Any]:
    _ = _require_user_id(x_user_id)

    ch = _norm_channel(channel)
    if not ch:
        raise HTTPException(status_code=422, detail="channel is required")

    q = text(
        """
        SELECT
          d.audit_id,
          d.user_id,
          d.channel,
          d.status,
          d.created_at AS delivery_created_at,
          e.task_id,
          e.event_type,
          e.payload,
          e.created_at AS event_created_at,
          u.telegram_id AS telegram_chat_id
        FROM public.task_event_deliveries d
        JOIN public.task_events e ON e.audit_id = d.audit_id
        LEFT JOIN public.users u ON u.user_id = d.user_id
        WHERE d.channel = :channel
          AND d.status = 'PENDING'
          AND d.audit_id > :cursor_from
        ORDER BY d.audit_id ASC, d.user_id ASC
        LIMIT :limit
        """
    )

    with engine.begin() as conn:
        rows = conn.execute(
            q,
            {"channel": ch, "cursor_from": int(cursor_from), "limit": int(limit)},
        ).mappings().all()

    items: List[Dict[str, Any]] = []
    next_cursor = int(cursor_from)

    for r in rows:
        audit_id = int(r["audit_id"])
        next_cursor = max(next_cursor, audit_id)

        tg = _safe_int(r.get("telegram_chat_id"))
        has_db_binding = tg is not None

        items.append(
            {
                "audit_id": audit_id,
                "user_id": int(r["user_id"]),
                "task_id": int(r["task_id"]),
                "event_type": str(r["event_type"] or ""),
                "payload": _as_dict_payload(r.get("payload")),
                "created_at": (r.get("event_created_at") or r.get("delivery_created_at")),
                "channel": str(r.get("channel") or ch),
                "status": str(r.get("status") or "PENDING"),
                "telegram_chat_id": tg,
                "has_db_binding": bool(has_db_binding),
                "needs_local_binding": bool((ch == "telegram") and (not has_db_binding)),
            }
        )

    return {"items": items, "next_cursor": next_cursor}


@router.post("/internal/task-event-deliveries/ack")
def ack_delivery(
    payload: Dict[str, Any],
    *,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
) -> Dict[str, Any]:
    """
    ACK ВОРКЕРА (результат отправки), а не ACK пользователя.

    Инварианты:
      - запрещаем регресс статусов (SENT не возвращаем в PENDING)
      - допускаем FAILED -> SENT (ретрай)
      - PENDING через этот endpoint не выставляем
      - если итоговый статус = SENT, то error_code/error_text должны быть NULL
    """
    _ = _require_user_id(x_user_id)

    audit_id = _safe_int(payload.get("audit_id"))
    user_id = _safe_int(payload.get("user_id"))
    ch = _norm_channel(payload.get("channel"))
    status = (payload.get("status") or "").strip().upper()

    if not audit_id or audit_id <= 0:
        raise HTTPException(status_code=422, detail="audit_id is required (positive int)")
    if not user_id or user_id <= 0:
        raise HTTPException(status_code=422, detail="user_id is required (positive int)")
    if not ch:
        raise HTTPException(status_code=422, detail="channel is required")
    if status not in ("SENT", "FAILED"):
        raise HTTPException(status_code=422, detail="status must be one of: SENT, FAILED")

    sent_at = _parse_dt(payload.get("sent_at"))
    error_code = payload.get("error_code")
    error_text = payload.get("error_text")

    # ВАЖНО: "NO_BINDING" не является ошибкой доставки (это policy-skip).
    # Поэтому переводим в SENT и ОБНУЛЯЕМ ошибку, иначе получаем неконсистентность SENT+NO_BINDING.
    if ch == "telegram" and status == "FAILED":
        ec = (str(error_code).strip().upper() if error_code is not None else "")
        if ec == "NO_BINDING":
            status = "SENT"
            error_code = None
            error_text = None

    # Нормализация ошибок: для SENT — всегда NULL
    if status == "SENT":
        error_code = None
        error_text = None

    q = text(
        """
        INSERT INTO public.task_event_deliveries (
          audit_id, user_id, channel, status, error_code, error_text, sent_at
        )
        VALUES (
          :audit_id, :user_id, :channel, :status, :error_code, :error_text,
          COALESCE(:sent_at, now())
        )
        ON CONFLICT (audit_id, user_id, channel)
        DO UPDATE SET
          status = CASE
            WHEN public.task_event_deliveries.status = 'SENT' THEN 'SENT'
            WHEN public.task_event_deliveries.status = 'FAILED' AND EXCLUDED.status = 'SENT' THEN 'SENT'
            WHEN public.task_event_deliveries.status = 'FAILED' AND EXCLUDED.status = 'FAILED' THEN 'FAILED'
            WHEN public.task_event_deliveries.status = 'PENDING' THEN EXCLUDED.status
            ELSE public.task_event_deliveries.status
          END,

          -- Если финально SENT — ошибка должна быть NULL.
          error_code = CASE
            WHEN public.task_event_deliveries.status = 'SENT' THEN NULL
            WHEN EXCLUDED.status = 'SENT' THEN NULL
            ELSE EXCLUDED.error_code
          END,
          error_text = CASE
            WHEN public.task_event_deliveries.status = 'SENT' THEN NULL
            WHEN EXCLUDED.status = 'SENT' THEN NULL
            ELSE EXCLUDED.error_text
          END,

          -- sent_at фиксируем на первом "не-pending" результате,
          -- но если стало SENT после FAILED — обновляем на ack-время.
          sent_at = CASE
            WHEN public.task_event_deliveries.status = 'SENT' THEN public.task_event_deliveries.sent_at
            WHEN EXCLUDED.status IN ('SENT','FAILED') THEN COALESCE(EXCLUDED.sent_at, now())
            ELSE public.task_event_deliveries.sent_at
          END
        RETURNING audit_id, user_id, channel, status, created_at, sent_at, error_code, error_text
        """
    )

    with engine.begin() as conn:
        row = conn.execute(
            q,
            {
                "audit_id": int(audit_id),
                "user_id": int(user_id),
                "channel": ch,
                "status": status,
                "error_code": str(error_code).strip() if error_code is not None and str(error_code).strip() else None,
                "error_text": str(error_text).strip() if error_text is not None and str(error_text).strip() else None,
                "sent_at": sent_at,
            },
        ).mappings().first()

    if not row:
        raise HTTPException(status_code=500, detail="ack failed")

    return {
        "ok": True,
        "delivery": {
            "audit_id": int(row["audit_id"]),
            "user_id": int(row["user_id"]),
            "channel": str(row["channel"]),
            "status": str(row["status"]),
            "created_at": row.get("created_at"),
            "sent_at": row.get("sent_at"),
            "error_code": row.get("error_code"),
            "error_text": row.get("error_text"),
        },
    }
