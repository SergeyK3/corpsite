# corpsite-bot/src/bot/bot.py
from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Set

from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, ContextTypes

from .integrations.corpsite_api import CorpsiteAPI
from .handlers.start import cmd_start
from .handlers.bind import cmd_bind
from .handlers.tasks import cmd_task


# -----------------------
# Env (single source of truth)
# -----------------------
# bot.py: corpsite-bot/src/bot/bot.py
# корень монорепы: .../09 Corpsite/
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
        if not part:
            continue
        if not part.isdigit():
            continue
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
# Main
# -----------------------
def main() -> None:
    log.info("Loading env from: %s", ROOT_ENV)
    log.info("API_BASE_URL=%s", API_BASE_URL)
    log.info("ADMIN_TG_IDS=%s", sorted(ADMIN_TG_IDS))

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_error_handler(on_error)

    backend = CorpsiteAPI(API_BASE_URL, timeout_s=15.0)
    app.bot_data["backend"] = backend  # handlers/tasks.py ожидает "backend"
    app.bot_data["api"] = backend      # совместимость/будущие хендлеры
    app.bot_data["admin_tg_ids"] = ADMIN_TG_IDS

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("bind", cmd_bind))
    app.add_handler(CommandHandler("task", cmd_task))

    log.info("Bot started. Polling...")
    app.run_polling(drop_pending_updates=True, close_loop=False)


if __name__ == "__main__":
    main()
