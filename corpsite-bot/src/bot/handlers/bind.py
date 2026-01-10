from __future__ import annotations

import logging
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from ..integrations.corpsite_api import CorpsiteAPI

log = logging.getLogger("corpsite-bot")


def _get_api(context: ContextTypes.DEFAULT_TYPE) -> Optional[CorpsiteAPI]:
    bd = context.bot_data or {}
    api = bd.get("backend")
    return api if isinstance(api, CorpsiteAPI) else None


def _extract_user_id_from_json(data: object) -> Optional[int]:
    if isinstance(data, dict):
        v = data.get("user_id")
        try:
            return int(v) if v is not None else None
        except Exception:
            return None
    return None


async def cmd_bind(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /bind
      Проверка статуса привязки (self-bind check): backend /auth/self-bind.

    /bind <code>
      Привязка по коду:
        1) POST /tg/bind/consume (bot-token)
        2) POST /auth/self-bind (проверка/подтверждение) -> показывает user_id
    """
    msg = update.effective_message
    if msg is None:
        return

    user = update.effective_user
    if user is None:
        await msg.reply_text("Не удалось определить пользователя Telegram.")
        return

    tg_user_id = int(user.id)
    tg_username = (user.username or "").strip() or None

    api = _get_api(context)
    if api is None:
        await msg.reply_text("Сервис временно недоступен. Попробуйте позже.")
        return

    args = context.args or []

    # -----------------------
    # /bind <code>
    # -----------------------
    if len(args) == 1:
        code = (args[0] or "").strip()
        if not code:
            await msg.reply_text("Формат: /bind <code>")
            return

        try:
            r = await api.consume_bind_code(code=code, telegram_user_id=tg_user_id)
        except Exception:
            log.exception("consume_bind_code failed")
            await msg.reply_text("Сервис временно недоступен. Попробуйте позже.")
            return

        if r.status_code == 0:
            await msg.reply_text("Сервис временно недоступен. Попробуйте позже.")
            return

        if r.status_code == 403:
            await msg.reply_text("Сервис привязки недоступен (нет прав).")
            return

        if r.status_code == 409:
            await msg.reply_text("Код недействителен или уже использован. Запросите новый код.")
            return

        if not (200 <= r.status_code < 300):
            await msg.reply_text("Не удалось выполнить привязку. Попробуйте позже.")
            return

        # consume ok -> now confirm via self_bind (and show user_id)
        try:
            s = await api.self_bind(telegram_user_id=tg_user_id, telegram_username=tg_username)
        except Exception:
            log.exception("self_bind after consume failed")
            await msg.reply_text("Привязка выполнена. Если задачи не появились — попробуйте /tasks позже.")
            return

        if s.status_code == 200:
            user_id = _extract_user_id_from_json(s.json)
            if user_id is not None:
                await msg.reply_text(f"Привязка выполнена. user_id={user_id}")
            else:
                await msg.reply_text("Привязка выполнена.")
            return

        # unexpected but safe UX
        await msg.reply_text("Привязка выполнена.")
        return

    if len(args) > 1:
        await msg.reply_text("Формат: /bind  ИЛИ  /bind <code>")
        return

    # -----------------------
    # /bind (status check)
    # -----------------------
    try:
        resp = await api.self_bind(telegram_user_id=tg_user_id, telegram_username=tg_username)
    except Exception:
        log.exception("self_bind failed")
        await msg.reply_text("Сервис временно недоступен. Попробуйте позже.")
        return

    if resp.status_code == 200:
        user_id = _extract_user_id_from_json(resp.json)
        if user_id is not None:
            await msg.reply_text(f"Вы уже привязаны. user_id={user_id}")
        else:
            await msg.reply_text("Вы уже привязаны.")
        return

    if resp.status_code == 404:
        await msg.reply_text(
            "Вы не привязаны.\n"
            "Если у вас есть код привязки — выполните: /bind <code>"
        )
        return

    if resp.status_code == 409:
        await msg.reply_text("Вы уже привязаны.")
        return

    await msg.reply_text("Не удалось выполнить привязку. Попробуйте позже.")
