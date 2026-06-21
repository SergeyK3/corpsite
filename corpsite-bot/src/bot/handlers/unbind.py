# corpsite-bot/src/bot/handlers/unbind.py
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from ..integrations.corpsite_api import CorpsiteAPI

log = logging.getLogger("corpsite-bot")


def _is_admin(tg_user_id: int, admin_ids: set[int]) -> bool:
    return tg_user_id in admin_ids


def _get_api(context: ContextTypes.DEFAULT_TYPE) -> CorpsiteAPI | None:
    api = context.bot_data.get("backend")
    return api if isinstance(api, CorpsiteAPI) else None


async def cmd_unbind(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /unbind
      Self-unbind: clears users.telegram_id via backend internal API.

    /unbind <tg_user_id>
      Admin-only: clears target Telegram binding (DB).
    """
    msg = update.effective_message
    if msg is None:
        log.error("cmd_unbind: effective_message is None")
        return

    actor = update.effective_user
    actor_tg_id = actor.id if actor else 0
    if actor_tg_id <= 0:
        await msg.reply_text("Не удалось определить пользователя Telegram.")
        return

    api = _get_api(context)
    if api is None:
        await msg.reply_text("Сервис временно недоступен.")
        return

    args = context.args or []

    try:
        if not args:
            resp = await api.unbind_telegram(telegram_user_id=int(actor_tg_id))
        else:
            if len(args) != 1 or not args[0].strip().isdigit():
                await msg.reply_text("Формат: /unbind или /unbind <tg_user_id>")
                return

            admin_ids_raw = context.bot_data.get("admin_tg_ids", set())
            admin_ids: set[int] = admin_ids_raw if isinstance(admin_ids_raw, set) else set(admin_ids_raw)
            if not _is_admin(actor_tg_id, admin_ids):
                await msg.reply_text("Доступ запрещён.")
                return

            target_tg_id = int(args[0].strip())
            resp = await api.unbind_telegram_target(
                actor_telegram_user_id=int(actor_tg_id),
                target_telegram_user_id=int(target_tg_id),
            )
    except Exception:
        log.exception("unbind failed")
        await msg.reply_text("Ошибка отвязки.")
        return

    if resp.status_code == 403:
        await msg.reply_text("Отвязка запрещена.")
        return
    if resp.status_code not in (200, 201):
        await msg.reply_text("Не удалось выполнить отвязку.")
        return

    body = resp.json if isinstance(resp.json, dict) else {}
    applied = bool(body.get("applied"))
    if not args:
        if applied:
            await msg.reply_text("Telegram отвязан от профиля.")
        else:
            await msg.reply_text("Telegram уже не привязан.")
        return

    target_tg_id = int(args[0].strip())
    if applied:
        await msg.reply_text(f"Привязка удалена в БД: tg={target_tg_id}")
    else:
        await msg.reply_text(f"Привязка не найдена или уже снята: tg={target_tg_id}")
