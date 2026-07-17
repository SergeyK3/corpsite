"""Onboarding notification delivery (WP-ONBOARDING-002).

Mirrors task_events delivery pattern without coupling to tasks.task_id.
"""
from __future__ import annotations

import json
import os
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.employee_onboarding.domain.status import ONBOARDING_NOTIFICATION_TYPES


def _parse_int_set(env_name: str) -> set[int]:
    raw = (os.getenv(env_name) or "").strip()
    if not raw:
        return set()
    out: set[int] = set()
    for part in raw.split(","):
        p = part.strip()
        if not p:
            continue
        try:
            out.add(int(p))
        except Exception:
            continue
    return out


TELEGRAM_DELIVERY_ALLOW_USER_IDS = _parse_int_set("TELEGRAM_DELIVERY_ALLOW_USER_IDS")


def _uniq_user_ids(user_ids: list[int]) -> list[int]:
    out: list[int] = []
    seen: set[int] = set()
    for uid in user_ids:
        try:
            iv = int(uid)
        except Exception:
            continue
        if iv <= 0 or iv in seen:
            continue
        seen.add(iv)
        out.append(iv)
    return out


def _channels_for_event_type(event_type: str) -> list[str]:
    et = (event_type or "").upper().strip()
    if et in ONBOARDING_NOTIFICATION_TYPES:
        return ["system", "telegram"]
    return ["system"]


def create_onboarding_notification_tx(
    conn: Connection,
    *,
    onboarding_id: int,
    item_id: int | None,
    event_type: str,
    actor_user_id: int | None,
    recipient_user_ids: list[int],
    payload: dict[str, Any] | None = None,
    dedup_key: str | None = None,
) -> int | None:
    """Create notification + recipients + deliveries. Returns notification_id or None if deduped."""
    et = (event_type or "").upper().strip()
    if not et:
        raise ValueError("event_type is required")
    recipients = _uniq_user_ids(recipient_user_ids)
    if not recipients:
        return None

    if dedup_key:
        existing = conn.execute(
            text(
                """
                SELECT notification_id
                FROM public.employee_onboarding_notifications
                WHERE item_id IS NOT DISTINCT FROM :item_id
                  AND event_type = :event_type
                  AND dedup_key = :dedup_key
                LIMIT 1
                """
            ),
            {
                "item_id": int(item_id) if item_id is not None else None,
                "event_type": et,
                "dedup_key": dedup_key,
            },
        ).scalar_one_or_none()
        if existing is not None:
            return None

    payload_json = json.dumps(payload or {})
    notification_id = int(
        conn.execute(
            text(
                """
                INSERT INTO public.employee_onboarding_notifications (
                    item_id,
                    onboarding_id,
                    event_type,
                    actor_user_id,
                    payload,
                    dedup_key
                )
                VALUES (
                    :item_id,
                    :onboarding_id,
                    :event_type,
                    :actor_user_id,
                    CAST(:payload AS jsonb),
                    :dedup_key
                )
                RETURNING notification_id
                """
            ),
            {
                "item_id": int(item_id) if item_id is not None else None,
                "onboarding_id": int(onboarding_id),
                "event_type": et,
                "actor_user_id": actor_user_id,
                "payload": payload_json,
                "dedup_key": dedup_key,
            },
        ).scalar_one()
    )

    for uid in recipients:
        conn.execute(
            text(
                """
                INSERT INTO public.employee_onboarding_notification_recipients (
                    notification_id, user_id
                )
                VALUES (:notification_id, :user_id)
                ON CONFLICT DO NOTHING
                """
            ),
            {"notification_id": notification_id, "user_id": int(uid)},
        )

    channels = _channels_for_event_type(et)
    for uid in recipients:
        for channel in channels:
            if channel == "telegram" and TELEGRAM_DELIVERY_ALLOW_USER_IDS and uid not in TELEGRAM_DELIVERY_ALLOW_USER_IDS:
                continue
            status = "SENT" if channel == "system" else "PENDING"
            conn.execute(
                text(
                    """
                    INSERT INTO public.employee_onboarding_notification_deliveries (
                        notification_id, user_id, channel, status
                    )
                    VALUES (:notification_id, :user_id, :channel, :status)
                    ON CONFLICT DO NOTHING
                    """
                ),
                {
                    "notification_id": notification_id,
                    "user_id": int(uid),
                    "channel": channel,
                    "status": status,
                },
            )
    return notification_id


def list_pending_onboarding_deliveries(
    conn: Connection,
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT
                d.notification_id,
                d.user_id,
                d.channel,
                n.event_type,
                n.payload,
                n.onboarding_id,
                n.item_id
            FROM public.employee_onboarding_notification_deliveries d
            JOIN public.employee_onboarding_notifications n
                ON n.notification_id = d.notification_id
            WHERE d.status = 'PENDING'
              AND d.channel = 'telegram'
            ORDER BY d.created_at ASC, d.notification_id ASC
            LIMIT :limit
            """
        ),
        {"limit": max(1, min(int(limit), 500))},
    ).mappings().all()
    return [dict(row) for row in rows]


def ack_onboarding_delivery(
    conn: Connection,
    *,
    notification_id: int,
    user_id: int,
    channel: str,
    status: str,
    error_code: str | None = None,
) -> None:
    conn.execute(
        text(
            """
            UPDATE public.employee_onboarding_notification_deliveries
            SET status = :status,
                error_code = :error_code,
                sent_at = CASE WHEN :status = 'SENT' THEN now() ELSE sent_at END
            WHERE notification_id = :notification_id
              AND user_id = :user_id
              AND channel = :channel
            """
        ),
        {
            "notification_id": int(notification_id),
            "user_id": int(user_id),
            "channel": channel,
            "status": status,
            "error_code": error_code,
        },
    )
