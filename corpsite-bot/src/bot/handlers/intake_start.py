# corpsite-bot/src/bot/handlers/intake_start.py
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

INTAKE_START_MESSAGE = (
    "Бот заполнения личной карточки Corpsite. "
    "Для начала используйте персональную ссылку от отдела кадров."
)


async def cmd_intake_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if msg is None:
        return

    await msg.reply_text(INTAKE_START_MESSAGE)
