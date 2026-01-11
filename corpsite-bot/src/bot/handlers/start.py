# corpsite-bot/src/bot/handlers/start.py
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if msg is None:
        return

    text = (
        "Corpsite Bot\n\n"
        "Быстрый старт:\n"
        "1) /bind — привязать этот Telegram к профилю\n"
        "2) /tasks — список задач\n\n"
        "Команды:\n"
        "/bind\n"
        "/tasks\n"
        "/tasks help\n"
    )

    await msg.reply_text(text)
