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
        "Задачи:\n"
        "/tasks                     — список задач\n"
        "/tasks <id>                — показать задачу\n"
        "/tasks <id> history        — история событий\n"
        "/tasks <id> update title=\"...\" desc=\"...\" scope=\"functional|admin\"\n"
        "/tasks <id> report <url> [comment]\n"
        "/tasks <id> approve [comment]\n"
        "/tasks <id> reject [comment]\n\n"
        "Примечания:\n"
        "- PATCH разрешает только: title, description, assignment_scope\n"
    )
    await msg.reply_text(text)
