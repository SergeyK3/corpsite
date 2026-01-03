import os
import logging
from typing import Set

from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler

from .integrations.corpsite_api import CorpsiteAPI
from .handlers.start import cmd_start
from .handlers.bind import cmd_bind
from .handlers.tasks import cmd_task


# -----------------------
# Env
# -----------------------
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
ADMIN_TG_IDS_RAW = os.getenv("ADMIN_TG_IDS", "").strip()

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set. Put BOT_TOKEN=... into corpsite-bot/.env")


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
    level=logging.ERROR,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

# подавляем шум библиотек
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("telegram").setLevel(logging.ERROR)
logging.getLogger("telegram.ext").setLevel(logging.ERROR)

log = logging.getLogger("corpsite-bot")


# -----------------------
# Main
# -----------------------
def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    # shared deps
    backend = CorpsiteAPI(API_BASE_URL, timeout_s=15.0)
    app.bot_data["backend"] = backend  # для handlers/tasks.py (cmd_task ожидает "backend")
    app.bot_data["api"] = backend      # оставляем для совместимости/будущих хендлеров
    app.bot_data["admin_tg_ids"] = ADMIN_TG_IDS

    # handlers (MVP)
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("bind", cmd_bind))
    app.add_handler(CommandHandler("task", cmd_task))

    app.run_polling(drop_pending_updates=True, close_loop=False)


if __name__ == "__main__":
    main()
