from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if msg is None:
        return

    text = (
        "Corpsite Bot (MVP)\n\n"
        "Команды:\n"
        "/bind <tg_user_id> <user_id>  — (админ) привязка Telegram → user\n\n"
        "Работа с задачей:\n"
        "/task <id> update title=\"...\" desc=\"...\" scope=\"...\"\n"
        "/task <id> report <url>\n"
        "/task <id> approve\n\n"
        "Примечания:\n"
        "- PATCH разрешает только: title, description, assignment_scope\n"
        "- Завершение выполняется через /task <id> approve\n"
    )
    await msg.reply_text(text)
