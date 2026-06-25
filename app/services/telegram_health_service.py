"""OPS-026.2 — aggregated Telegram delivery health (backend-only, no shell)."""
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple

from sqlalchemy import text

from app.db.engine import engine

TelegramHealthStatus = Literal["GREEN", "YELLOW", "RED"]

_DEFAULT_CHANNEL = "telegram"
_WINDOW_HOURS = 24
_STALE_PENDING_SECONDS = 30 * 60
_ERROR_TEXT_MAX_LEN = 200

_TOKEN_LIKE_RE = re.compile(
    r"(?i)(token|secret|password|api[_-]?key)\s*[:=]\s*\S+|"
    r"\b\d{8,}:[A-Za-z0-9_-]{20,}\b|"  # Telegram bot token shape
    r"Bearer\s+\S+"
)

_UNAVAILABLE_METRICS: List[Dict[str, str]] = [
    {
        "metric": "bot_service_active",
        "reason": "Requires host systemd access; not available from backend API.",
    },
    {
        "metric": "bot_service_uptime",
        "reason": "Requires host systemd access; not available from backend API.",
    },
    {
        "metric": "bot_journal_errors",
        "reason": "Requires journalctl on host; not available from backend API.",
    },
    {
        "metric": "telegram_api_reachable",
        "reason": "Would require outbound probe to Telegram API (not implemented).",
    },
    {
        "metric": "delivery_queue_poll_lag",
        "reason": "Bot poll cursor is stored on host filesystem, not in database.",
    },
]


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso_dt(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    return str(value)


def _age_seconds(from_dt: Optional[datetime], *, now: datetime) -> Optional[float]:
    if from_dt is None:
        return None
    if from_dt.tzinfo is None:
        from_dt = from_dt.replace(tzinfo=timezone.utc)
    return max(0.0, (now - from_dt.astimezone(timezone.utc)).total_seconds())


def _mask_error_text(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    text_val = str(raw).strip()
    if not text_val:
        return None
    masked = _TOKEN_LIKE_RE.sub("[redacted]", text_val)
    if len(masked) <= _ERROR_TEXT_MAX_LEN:
        return masked
    return masked[: _ERROR_TEXT_MAX_LEN - 1].rstrip() + "…"


def _env_present(name: str) -> bool:
    return bool((os.getenv(name) or "").strip())


def _read_bot_configuration() -> Dict[str, Any]:
    delivery_channel = (os.getenv("EVENTS_DELIVERY_CHANNEL") or "telegram").strip() or "telegram"
    allow_list_raw = (os.getenv("TELEGRAM_DELIVERY_ALLOW_USER_IDS") or "").strip()
    return {
        "bot_token_present": _env_present("BOT_TOKEN"),
        "internal_api_token_present": _env_present("INTERNAL_API_TOKEN"),
        "bot_bind_token_present": _env_present("BOT_BIND_TOKEN"),
        "api_base_url": (os.getenv("API_BASE_URL") or "").strip() or None,
        "events_delivery_channel": delivery_channel,
        "events_internal_api_user_id": (os.getenv("EVENTS_INTERNAL_API_USER_ID") or "").strip() or None,
        "telegram_delivery_allowlist_configured": bool(allow_list_raw),
    }


def compute_health_status(
    *,
    queue: Dict[str, Any],
    delivery: Dict[str, Any],
    bindings: Dict[str, Any],
    bot_configuration: Dict[str, Any],
    now: Optional[datetime] = None,
) -> Tuple[TelegramHealthStatus, List[str]]:
    """Derive GREEN / YELLOW / RED from aggregated metrics."""
    now = now or _now_utc()
    reasons: List[str] = []

    if not bot_configuration.get("bot_token_present"):
        return "RED", ["BOT_TOKEN is not configured"]

    if not bot_configuration.get("internal_api_token_present"):
        return "RED", ["INTERNAL_API_TOKEN is not configured"]

    pending = int(queue.get("pending_count") or 0)
    sent_24h = int(queue.get("sent_24h") or 0)
    failed_24h = int(queue.get("failed_24h") or 0)
    oldest_age_sec = queue.get("oldest_pending_age_sec")

    if pending > 0 and sent_24h == 0:
        age = float(oldest_age_sec or 0)
        if age >= _STALE_PENDING_SECONDS:
            return "RED", [
                f"Pending backlog ({pending}) with no successful sends in the last {_WINDOW_HOURS}h",
            ]

    if pending > 0 and failed_24h > 0 and sent_24h == 0:
        return "RED", ["Pending telegram deliveries are failing without successful drain"]

    last_error_code = (delivery.get("last_error_code") or "").strip().upper()
    if pending > 0 and last_error_code in {"SEND_ERROR", "NAMEERROR"}:
        return "RED", [f"Recent delivery error while backlog present: {last_error_code}"]

    if pending > 0:
        reasons.append(f"{pending} pending telegram delivery row(s)")

    coverage = float(bindings.get("coverage_percent") or 0)
    if bindings.get("active_users", 0) > 0 and coverage < 100:
        reasons.append(f"Telegram binding coverage is {coverage}%")

    if failed_24h > 0:
        reasons.append(f"{failed_24h} failed delivery attempt(s) in the last {_WINDOW_HOURS}h")

    if bot_configuration.get("telegram_delivery_allowlist_configured"):
        reasons.append("TELEGRAM_DELIVERY_ALLOW_USER_IDS allow-list is active")

    last_sent_at_raw = delivery.get("last_sent_at")
    last_sent_dt: Optional[datetime] = None
    if isinstance(last_sent_at_raw, str) and last_sent_at_raw.strip():
        try:
            last_sent_dt = datetime.fromisoformat(last_sent_at_raw.replace("Z", "+00:00"))
        except ValueError:
            last_sent_dt = None
    elif isinstance(last_sent_at_raw, datetime):
        last_sent_dt = last_sent_at_raw

    last_sent_age = _age_seconds(last_sent_dt, now=now)
    users_with_tg = int(bindings.get("users_with_telegram") or 0)

    if users_with_tg > 0:
        if last_sent_dt is None:
            reasons.append("No successful telegram delivery recorded")
        elif last_sent_age is not None and last_sent_age > _WINDOW_HOURS * 3600:
            reasons.append(f"No successful telegram sends in the last {_WINDOW_HOURS}h")

    if reasons:
        return "YELLOW", reasons

    if pending == 0 and failed_24h == 0:
        if last_sent_dt is not None and last_sent_age is not None and last_sent_age <= _WINDOW_HOURS * 3600:
            return "GREEN", ["Queue empty", f"Successful delivery within {_WINDOW_HOURS}h"]
        if users_with_tg == 0:
            return "GREEN", ["Queue empty", "No active users with Telegram binding"]
        if last_sent_dt is not None:
            return "YELLOW", [f"No sends in the last {_WINDOW_HOURS}h but queue is empty"]

    return "GREEN", ["Queue healthy"]


def get_telegram_health(
    *,
    channel: str = _DEFAULT_CHANNEL,
    window_hours: int = _WINDOW_HOURS,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    now = now or _now_utc()
    since = now - timedelta(hours=max(1, int(window_hours)))
    ch = (channel or _DEFAULT_CHANNEL).strip().lower() or _DEFAULT_CHANNEL
    bot_configuration = _read_bot_configuration()

    with engine.begin() as conn:
        queue_row = conn.execute(
            text(
                """
                SELECT
                  COUNT(*) FILTER (WHERE d.status = 'PENDING')::int AS pending_count,
                  COUNT(*) FILTER (
                    WHERE d.status = 'SENT'
                      AND d.sent_at IS NOT NULL
                      AND d.sent_at >= :since
                  )::int AS sent_24h,
                  COUNT(*) FILTER (
                    WHERE d.status = 'FAILED'
                      AND COALESCE(d.sent_at, d.created_at) >= :since
                  )::int AS failed_24h,
                  MIN(d.created_at) FILTER (WHERE d.status = 'PENDING') AS oldest_pending_at
                FROM public.task_event_deliveries d
                WHERE d.channel = :channel
                """
            ),
            {"channel": ch, "since": since},
        ).mappings().first()

        delivery_row = conn.execute(
            text(
                """
                SELECT
                  MAX(d.sent_at) FILTER (WHERE d.status = 'SENT') AS last_sent_at,
                  MAX(COALESCE(d.sent_at, d.created_at)) FILTER (WHERE d.status = 'FAILED') AS last_failed_at
                FROM public.task_event_deliveries d
                WHERE d.channel = :channel
                """
            ),
            {"channel": ch},
        ).mappings().first()

        error_row = conn.execute(
            text(
                """
                SELECT
                  d.error_code,
                  d.error_text,
                  COALESCE(d.sent_at, d.created_at) AS occurred_at
                FROM public.task_event_deliveries d
                WHERE d.channel = :channel
                  AND d.status = 'FAILED'
                  AND (
                    d.error_code IS NOT NULL
                    OR d.error_text IS NOT NULL
                  )
                ORDER BY COALESCE(d.sent_at, d.created_at) DESC NULLS LAST
                LIMIT 1
                """
            ),
            {"channel": ch},
        ).mappings().first()

        bindings_row = conn.execute(
            text(
                """
                SELECT
                  COUNT(*) FILTER (WHERE COALESCE(u.is_active, TRUE) = TRUE)::int AS active_users,
                  COUNT(*) FILTER (
                    WHERE COALESCE(u.is_active, TRUE) = TRUE
                      AND u.telegram_id IS NOT NULL
                      AND trim(u.telegram_id::text) <> ''
                  )::int AS users_with_telegram
                FROM public.users u
                """
            ),
        ).mappings().first()

    oldest_pending_at = queue_row.get("oldest_pending_at") if queue_row else None
    oldest_pending_age_sec = _age_seconds(oldest_pending_at, now=now)

    active_users = int((bindings_row or {}).get("active_users") or 0)
    users_with_telegram = int((bindings_row or {}).get("users_with_telegram") or 0)
    coverage_percent = round((users_with_telegram / active_users) * 100, 2) if active_users > 0 else 0.0

    queue = {
        "pending_count": int((queue_row or {}).get("pending_count") or 0),
        "sent_24h": int((queue_row or {}).get("sent_24h") or 0),
        "failed_24h": int((queue_row or {}).get("failed_24h") or 0),
        "oldest_pending_at": _iso_dt(oldest_pending_at),
        "oldest_pending_age_sec": oldest_pending_age_sec,
    }

    delivery = {
        "last_sent_at": _iso_dt((delivery_row or {}).get("last_sent_at")),
        "last_failed_at": _iso_dt((delivery_row or {}).get("last_failed_at")),
        "last_error_code": (error_row or {}).get("error_code"),
        "last_error_text": _mask_error_text((error_row or {}).get("error_text")),
    }

    bindings = {
        "active_users": active_users,
        "users_with_telegram": users_with_telegram,
        "coverage_percent": coverage_percent,
    }

    error_summary: Optional[Dict[str, Any]] = None
    if error_row:
        error_summary = {
            "error_code": error_row.get("error_code"),
            "occurred_at": _iso_dt(error_row.get("occurred_at")),
            "message": _mask_error_text(error_row.get("error_text")),
        }

    status, status_reasons = compute_health_status(
        queue=queue,
        delivery=delivery,
        bindings=bindings,
        bot_configuration=bot_configuration,
        now=now,
    )

    return {
        "checked_at": _iso_dt(now),
        "channel": ch,
        "window_hours": int(window_hours),
        "status": status,
        "status_reasons": status_reasons,
        "queue": queue,
        "delivery": delivery,
        "bindings": bindings,
        "bot_configuration": bot_configuration,
        "error_summary": error_summary,
        "unavailable_metrics": list(_UNAVAILABLE_METRICS),
    }
