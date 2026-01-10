# corpsite-bot/src/bot/handlers/events.py
from __future__ import annotations

import logging
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from ..integrations.corpsite_api import CorpsiteAPI
from ..events_renderer import render_event
from ..storage.bindings import get_binding

log = logging.getLogger("corpsite-bot")


def _parse_int(s: str) -> Optional[int]:
    try:
        return int(str(s).strip())
    except Exception:
        return None


def _normalize_event_type(s: str) -> Optional[str]:
    """
    allowed:
      approved | rejected | report_submitted | all
    returns backend enum string or None (for all)
    """
    v = (s or "").strip().lower()
    if not v or v in {"all", "*"}:
        return None
    if v in {"approved", "approve"}:
        return "APPROVED"
    if v in {"rejected", "reject"}:
        return "REJECTED"
    if v in {"report", "report_submitted", "submitted"}:
        return "REPORT_SUBMITTED"
    return None


async def cmd_events(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /events [approved|rejected|report_submitted|all] [limit:int]
    /events [limit:int]                   (если первый аргумент число)
    Aliases:
      /history ... (тот же handler)

    Показывает последние события пользователя (через /tasks/me/events).
    """
    msg = update.effective_message
    if msg is None:
        return

    actor = update.effective_user
    tg_user_id = actor.id if actor else 0
    if tg_user_id <= 0:
        await msg.reply_text("Не удалось определить пользователя Telegram.")
        return

    corpsite_user_id = get_binding(tg_user_id)
    if not corpsite_user_id:
        await msg.reply_text("Вы не привязаны. Используйте /bind (если вы админ) или обратитесь к администратору.")
        return

    args = context.args or []

    event_type: Optional[str] = None
    limit = 10

    if args:
        # If first arg is int -> it's limit
        maybe_limit = _parse_int(args[0])
        if maybe_limit is not None:
            limit = max(1, min(50, maybe_limit))
        else:
            event_type = _normalize_event_type(args[0])
            if len(args) >= 2:
                maybe_limit2 = _parse_int(args[1])
                if maybe_limit2 is not None:
                    limit = max(1, min(50, maybe_limit2))

    backend: CorpsiteAPI = context.bot_data["backend"]  # type: ignore[assignment]

    try:
        resp = await backend.get_my_events(
            user_id=int(corpsite_user_id),
            limit=int(limit),
            offset=0,
            since_audit_id=None,
            event_type=event_type,
        )
    except Exception:
        log.exception("cmd_events: backend call failed")
        await msg.reply_text("Ошибка обращения к backend.")
        return

    if resp.status_code != 200 or not isinstance(resp.json, list):
        await msg.reply_text("Ошибка получения истории событий.")
        return

    events = resp.json
    if not events:
        await msg.reply_text("Событий нет.")
        return

    # backend returns DESC; show newest-first but keep readable grouping
    # We'll render as a single message (compact)
    lines: list[str] = []
    for ev in events[:limit]:
        lines.append(render_event(ev))
        lines.append("")  # separator

    text = "\n".join(lines).strip()
    await msg.reply_text(text)
