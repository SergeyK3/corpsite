# corpsite-bot/src/bot/handlers/unbind.py
from __future__ import annotations

import logging
from telegram import Update
from telegram.ext import ContextTypes

from ..storage.bindings import remove_binding

log = logging.getLogger("corpsite-bot")


def _is_admin(tg_user_id: int, admin_ids: set[int]) -> bool:
    return tg_user_id in admin_ids


async def cmd_unbind(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /unbind <tg_user_id>
    Удаляет привязку tg_user_id -> user_id из bindings.json.
    Доступ только для админов (bot_data["admin_tg_ids"]).
    """
    msg = update.effective_message
    if msg is None:
        log.error("cmd_unbind: effective_message is None")
        return

    actor = update.effective_user
    actor_tg_id = actor.id if actor else 0

    admin_ids_raw = context.bot_data.get("admin_tg_ids", set())
    admin_ids: set[int] = admin_ids_raw if isinstance(admin_ids_raw, set) else set(admin_ids_raw)

    if not _is_admin(actor_tg_id, admin_ids):
        await msg.reply_text("Доступ запрещён.")
        return

    args = context.args or []
    if len(args) != 1:
        await msg.reply_text("Формат: /unbind <tg_user_id:int>")
        return

    a0 = args[0].strip()
    if not a0.isdigit():
        await msg.reply_text("Формат: /unbind <tg_user_id:int>")
        return

    tg_user_id = int(a0)

    try:
        removed = remove_binding(tg_user_id)
        if removed:
            await msg.reply_text(f"Привязка удалена: tg={tg_user_id}")
        else:
            await msg.reply_text(f"Привязка не найдена: tg={tg_user_id}")
    except Exception as e:
        log.exception("Failed to remove binding")
        await msg.reply_text(f"Ошибка удаления привязки: {type(e).__name__}: {e}")
