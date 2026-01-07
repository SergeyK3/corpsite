# corpsite-bot/src/bot/bot.py
from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Set, Optional

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .integrations.corpsite_api import CorpsiteAPI
from .handlers.start import cmd_start
from .handlers.bind import cmd_bind
from .handlers.tasks import cmd_task
from .handlers.whoami import cmd_whoami
from .handlers.unbind import cmd_unbind


# -----------------------
# Env (single source of truth)
# -----------------------
ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(dotenv_path=ROOT_ENV)

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
ADMIN_TG_IDS_RAW = os.getenv("ADMIN_TG_IDS", "").strip()

if not BOT_TOKEN:
    raise RuntimeError(f"BOT_TOKEN is not set. Expected in {ROOT_ENV}")


def _parse_admin_ids(raw: str) -> Set[int]:
    if not raw:
        return set()
    out: Set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            out.add(int(part))
    return out


ADMIN_TG_IDS = _parse_admin_ids(ADMIN_TG_IDS_RAW)


# -----------------------
# Logging
# -----------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logging.getLogger("httpx").setLevel(logging.ERROR)
log = logging.getLogger("corpsite-bot")


# -----------------------
# Error handler
# -----------------------
async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.exception("Unhandled error while handling update", exc_info=context.error)


# -----------------------
# Control handlers (verification only)
# -----------------------
async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if msg:
        await msg.reply_text("pong")


async def cmd_whereami(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if msg is None:
        return

    chat = update.effective_chat
    chat_type = getattr(chat, "type", None) or "unknown"
    chat_id = getattr(chat, "id", None)

    if chat_type == "private":
        await msg.reply_text(f"Личный чат. chat_id={chat_id}")
        return

    title = getattr(chat, "title", None)
    title_part = f' "{title}"' if title else ""
    await msg.reply_text(f"Групповой чат ({chat_type}){title_part}. chat_id={chat_id}")


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if msg:
        await msg.reply_text(
            "Команда не распознана. Доступные: /start, /bind, /unbind, /whoami, /tasks, /ping, /whereami"
        )


# -----------------------
# Lifecycle hooks
# -----------------------
async def _post_init(application: Application) -> None:
    """
    Called once after Application is initialized.
    We create a single API client and store it in bot_data.
    """
    backend = CorpsiteAPI(API_BASE_URL, timeout_s=15.0)
    application.bot_data["backend"] = backend          # handlers/tasks.py ожидает "backend"
    application.bot_data["admin_tg_ids"] = ADMIN_TG_IDS

    log.info("Initialized backend client. API_BASE_URL=%s", API_BASE_URL)
    log.info("ADMIN_TG_IDS=%s", sorted(ADMIN_TG_IDS))


async def _post_shutdown(application: Application) -> None:
    """
    Called once during shutdown.
    Close httpx client to avoid resource leaks.
    """
    backend: Optional[CorpsiteAPI] = application.bot_data.get("backend")  # type: ignore[assignment]
    if backend is not None:
        try:
            # Требуется метод aclose() в CorpsiteAPI (закрывает httpx.AsyncClient)
            await backend.aclose()
        except Exception:
            log.exception("Failed to close backend client")


# -----------------------
# Main
# -----------------------
def main() -> None:
    log.info("Loading env from: %s", ROOT_ENV)

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )
    app.add_error_handler(on_error)

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("bind", cmd_bind))
    app.add_handler(CommandHandler("unbind", cmd_unbind))
    app.add_handler(CommandHandler("whoami", cmd_whoami))
    app.add_handler(CommandHandler("tasks", cmd_task))
    app.add_handler(CommandHandler("ping", cmd_ping))
    app.add_handler(CommandHandler("whereami", cmd_whereami))

    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    log.info("Bot started. Polling...")
    app.run_polling(drop_pending_updates=True, close_loop=False)


if __name__ == "__main__":
    main()
