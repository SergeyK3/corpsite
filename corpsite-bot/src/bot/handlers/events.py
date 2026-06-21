# FILE: corpsite-bot/src/bot/handlers/events.py
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from telegram import Update
from telegram.ext import ContextTypes

from ..events_renderer import render_event
from ..integrations.corpsite_api import CorpsiteAPI

log = logging.getLogger("corpsite-bot")

_MAX_MSG_LEN = 3900


def _parse_int(s: str) -> Optional[int]:
    try:
        return int(str(s).strip())
    except Exception:
        return None


def _normalize_event_type(s: str) -> Optional[str]:
    v = (s or "").strip().lower()
    if not v or v in {"all", "*"}:
        return None
    if v in {"approved", "approve"}:
        return "APPROVED"
    if v in {"rejected", "reject"}:
        return "REJECTED"
    if v in {"report", "report_submitted", "submitted"}:
        return "REPORT_SUBMITTED"
    return "__INVALID__"


def _extract_events_payload(payload: Any) -> Tuple[List[Dict[str, Any]], Optional[int]]:
    if isinstance(payload, dict):
        items = payload.get("items")
        next_cursor = _parse_int(payload.get("next_cursor"))
        if isinstance(items, list):
            out: List[Dict[str, Any]] = [x for x in items if isinstance(x, dict)]
            return out, next_cursor
        return [], next_cursor

    if isinstance(payload, list):
        out2: List[Dict[str, Any]] = [x for x in payload if isinstance(x, dict)]
        return out2, None

    return [], None


async def _safe_reply_text(msg, text: str) -> None:
    text = (text or "").strip()
    if not text:
        return
    if len(text) <= _MAX_MSG_LEN:
        await msg.reply_text(text)
        return

    parts: list[str] = []
    buf: list[str] = []
    cur_len = 0
    for line in text.splitlines():
        add = (line + "\n")
        if cur_len + len(add) > _MAX_MSG_LEN and buf:
            parts.append("".join(buf).rstrip())
            buf = []
            cur_len = 0
        buf.append(add)
        cur_len += len(add)
    if buf:
        parts.append("".join(buf).rstrip())

    for p in parts:
        await msg.reply_text(p)


async def cmd_events(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if msg is None:
        return

    actor = update.effective_user
    tg_user_id = actor.id if actor else 0
    if tg_user_id <= 0:
        await msg.reply_text("Не удалось определить пользователя Telegram.")
        return

    backend = context.bot_data.get("backend")
    if not isinstance(backend, CorpsiteAPI):
        log.error("cmd_events: backend is not configured (bot_data['backend'])")
        await msg.reply_text("Backend не настроен.")
        return

    bind_check = await backend.self_bind(telegram_user_id=int(tg_user_id))
    if bind_check.status_code == 404:
        await msg.reply_text("Вы не привязаны. Используйте /bind <code> из профиля.")
        return
    if bind_check.status_code not in (200, 201):
        await msg.reply_text("Ошибка проверки привязки.")
        return

    args = context.args or []

    event_type: Optional[str] = None
    limit = 10

    if args:
        maybe_limit = _parse_int(args[0])
        if maybe_limit is not None:
            limit = max(1, min(50, maybe_limit))
        else:
            norm = _normalize_event_type(args[0])
            if norm == "__INVALID__":
                await msg.reply_text("Неверный тип. Используйте: approved | rejected | report_submitted | all")
                return
            event_type = norm
            if len(args) >= 2:
                maybe_limit2 = _parse_int(args[1])
                if maybe_limit2 is not None:
                    limit = max(1, min(50, maybe_limit2))

    try:
        resp = await backend.get_my_events(
            telegram_user_id=int(tg_user_id),
            limit=int(limit),
        )
    except Exception:
        log.exception("cmd_events: backend call failed")
        await msg.reply_text("Ошибка обращения к backend.")
        return

    payload: Any = resp.json

    if resp.status_code != 200:
        await msg.reply_text("Ошибка получения истории событий.")
        return

    events, _next_cursor = _extract_events_payload(payload)

    if event_type:
        events = [ev for ev in events if str(ev.get("event_type") or "").upper() == event_type]

    if not events:
        await msg.reply_text("Событий нет.")
        return

    lines: list[str] = []
    for ev in events[:limit]:
        try:
            lines.append(render_event(ev))
        except Exception:
            log.exception("cmd_events: render_event failed")
            lines.append("• (не удалось отрендерить событие)")
        lines.append("")

    text = "\n".join(lines).strip()
    await _safe_reply_text(msg, text)
