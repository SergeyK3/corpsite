# corpsite-bot/src/bot/handlers/bind.py
from __future__ import annotations

import logging
from telegram import Update
from telegram.ext import ContextTypes

from ..storage.bindings import set_binding

log = logging.getLogger("corpsite-bot")


def _is_admin(tg_user_id: int, admin_ids: set[int]) -> bool:
    return tg_user_id in admin_ids


async def cmd_bind(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /bind <tg_user_id> <user_id>
    Персистентная привязка tg_user_id -> user_id в bindings.json.
    Доступ только для админов (bot_data["admin_tg_ids"]).
    """
    msg = update.effective_message
    if msg is None:
        log.error("cmd_bind: effective_message is None")
        return

    actor = update.effective_user
    actor_tg_id = actor.id if actor else 0

    admin_ids_raw = context.bot_data.get("admin_tg_ids", set())
    admin_ids: set[int] = admin_ids_raw if isinstance(admin_ids_raw, set) else set(admin_ids_raw)

    if not _is_admin(actor_tg_id, admin_ids):
        await msg.reply_text("Доступ запрещён.")
        return

    args = context.args or []
    if len(args) != 2:
        await msg.reply_text("Формат: /bind <tg_user_id:int> <user_id:int>")
        return

    a0 = args[0].strip()
    a1 = args[1].strip()
    if (not a0.isdigit()) or (not a1.isdigit()):
        await msg.reply_text("Формат: /bind <tg_user_id:int> <user_id:int>")
        return

    tg_user_id = int(a0)
    user_id = int(a1)

    try:
        set_binding(tg_user_id, user_id)
        await msg.reply_text(f"Привязка установлена: tg={tg_user_id} → user_id={user_id}")
    except Exception as e:
        log.exception("Failed to set binding")
        await msg.reply_text(f"Ошибка привязки: {type(e).__name__}: {e}")
