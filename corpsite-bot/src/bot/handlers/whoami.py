# corpsite-bot/src/bot/handlers/whoami.py
from __future__ import annotations

import time
from typing import Optional, Tuple, Any

from telegram import Update
from telegram.ext import ContextTypes

from ..integrations.corpsite_api import CorpsiteAPI


# cache: tg_user_id -> (user_id, expires_at_monotonic)
_CACHE: dict[int, Tuple[int, float]] = {}
_CACHE_TTL_S = 600.0  # 10 минут


def _get_backend(context: ContextTypes.DEFAULT_TYPE) -> Optional[CorpsiteAPI]:
    bd = context.bot_data or {}
    api = bd.get("api") or bd.get("corpsite_api") or bd.get("backend")
    return api if isinstance(api, CorpsiteAPI) else None


def _cache_get(tg_user_id: int) -> Optional[int]:
    rec = _CACHE.get(int(tg_user_id))
    if not rec:
        return None
    uid, exp = rec
    if time.monotonic() >= exp:
        _CACHE.pop(int(tg_user_id), None)
        return None
    return int(uid)


def _cache_set(tg_user_id: int, user_id: int) -> None:
    _CACHE[int(tg_user_id)] = (int(user_id), time.monotonic() + _CACHE_TTL_S)


async def _resolve_user_id_via_backend(
    *,
    backend: CorpsiteAPI,
    tg_user_id: int,
    tg_username: Optional[str],
) -> tuple[Optional[int], int, str]:
    """
    Returns: (user_id or None, status_code, detail_text)
    """
    resp = await backend.self_bind(telegram_user_id=int(tg_user_id), telegram_username=tg_username)
    sc = int(resp.status_code or 0)

    if sc in (200, 201) and isinstance(resp.json, dict):
        uid = resp.json.get("user_id")
        try:
            if uid is not None and int(uid) > 0:
                return int(uid), sc, ""
        except Exception:
            pass
        return None, sc, "Некорректный ответ backend (user_id отсутствует)."

    if sc == 404:
        return None, sc, "не привязан"

    if sc == 0:
        return None, sc, "backend недоступен"

    # прочее
    txt = (resp.text or "").strip()
    return None, sc, (txt or "ошибка backend")


async def cmd_whoami(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if msg is None:
        return

    user = update.effective_user
    if user is None:
        await msg.reply_text("Не удалось определить пользователя Telegram.")
        return

    tg_user_id = int(user.id)
    tg_username = (user.username or "").strip() or None

    backend = _get_backend(context)
    if backend is None:
        await msg.reply_text(f"tg_user_id={tg_user_id}\nuser_id: неизвестно (backend не инициализирован)")
        return

    cached = _cache_get(tg_user_id)
    if cached is not None:
        await msg.reply_text(f"tg_user_id={tg_user_id}\nuser_id={cached}")
        return

    user_id, sc, detail = await _resolve_user_id_via_backend(
        backend=backend,
        tg_user_id=tg_user_id,
        tg_username=tg_username,
    )

    if user_id is None:
        if sc == 404:
            await msg.reply_text(f"tg_user_id={tg_user_id}\nuser_id: не привязан")
            return
        if sc == 0:
            await msg.reply_text(f"tg_user_id={tg_user_id}\nuser_id: неизвестно (backend недоступен)")
            return
        await msg.reply_text(f"tg_user_id={tg_user_id}\nuser_id: неизвестно (ошибка {sc}: {detail})")
        return

    _cache_set(tg_user_id, user_id)
    await msg.reply_text(f"tg_user_id={tg_user_id}\nuser_id={user_id}")
