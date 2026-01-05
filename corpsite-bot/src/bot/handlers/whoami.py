# corpsite-bot/src/bot/handlers/whoami.py
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from ..storage.bindings import get_binding


async def cmd_whoami(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if msg is None:
        return

    user = update.effective_user
    if user is None:
        await msg.reply_text("Не удалось определить пользователя Telegram.")
        return

    tg_user_id = user.id
    bound = get_binding(tg_user_id)

    if bound is None:
        await msg.reply_text(
            f"tg_user_id={tg_user_id}\nuser_id: не привязан"
        )
        return

    await msg.reply_text(
        f"tg_user_id={tg_user_id}\nuser_id={bound}"
    )
