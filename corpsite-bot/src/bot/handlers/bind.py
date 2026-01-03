from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from ..storage.bindings import BINDINGS


def _is_admin(tg_user_id: int, admin_ids: set[int]) -> bool:
    return tg_user_id in admin_ids


async def cmd_bind(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /bind <tg_user_id> <user_id>
    Делает in-memory привязку tg_user_id -> user_id.
    Доступ только для админов (bot_data["admin_tg_ids"]).
    """
    msg = update.message
    if msg is None:
        return

    admin_ids: set[int] = context.bot_data.get("admin_tg_ids", set())
    actor_tg_id = msg.from_user.id

    if not _is_admin(actor_tg_id, admin_ids):
        await msg.reply_text("Доступ запрещён.")
        return

    args = context.args or []
    if len(args) != 2:
        await msg.reply_text("Формат: /bind <tg_user_id:int> <user_id:int>")
        return

    # Жёсткая валидация: Telegram-клиенты иногда “переиспользуют” предыдущие args.
    # Нам важно не выполнять привязку при любом сомнении.
    if not args[0].isdigit() or not args[1].isdigit():
        await msg.reply_text("Формат: /bind <tg_user_id:int> <user_id:int>")
        return

    tg_user_id = int(args[0])
    user_id = int(args[1])

    BINDINGS[tg_user_id] = user_id
    await msg.reply_text(f"Привязка установлена: tg={tg_user_id} → user_id={user_id}")
