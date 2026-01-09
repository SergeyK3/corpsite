# corpsite-bot/src/bot/bot.py
from __future__ import annotations

import os
import logging
import asyncio
from pathlib import Path
from typing import Set, Optional, Any

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
from .handlers.events import cmd_events

from .events_poller import events_polling_loop, JsonFileStore


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
# Env (single source of truth)
# -----------------------
ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"
loaded = load_dotenv(dotenv_path=ROOT_ENV, override=True)

BOT_TOKEN = os.getenv("BOT_TOKEN")

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").strip().rstrip("/")
ADMIN_TG_IDS_RAW = (os.getenv("ADMIN_TG_IDS") or "").strip()

POLL_INTERVAL_S = float((os.getenv("EVENTS_POLL_INTERVAL_S", "5") or "5").strip())

DATA_DIR = Path(__file__).resolve().parents[3] / ".botdata"
BINDINGS_PATH = Path(os.getenv("BINDINGS_PATH", str(DATA_DIR / "bindings.json")))
EVENTS_STATE_PATH = Path(os.getenv("EVENTS_STATE_PATH", str(DATA_DIR / "events_state.json")))

EVENTS_POLL_TYPES_RAW = (os.getenv("EVENTS_POLL_TYPES") or "").strip()


def _parse_admin_ids(raw: str) -> Set[int]:
    if not raw:
        return set()
    out: Set[int] = set()
    for part in raw.split(","):
        p = part.strip()
        if p.isdigit():
            out.add(int(p))
    return out


def _parse_poll_types(raw: str) -> Set[str]:
    if not raw:
        return set()
    out: Set[str] = set()
    for part in raw.split(","):
        p = part.strip().upper()
        if p:
            out.add(p)
    return out


ADMIN_TG_IDS = _parse_admin_ids(ADMIN_TG_IDS_RAW)
ALLOWED_EVENT_TYPES = _parse_poll_types(EVENTS_POLL_TYPES_RAW)

log.info("ENV ROOT_ENV=%s (exists=%s loaded=%s)", str(ROOT_ENV), ROOT_ENV.exists(), loaded)
log.info("ADMIN_TG_IDS parsed=%s", sorted(ADMIN_TG_IDS))
log.info("EVENTS_POLL_TYPES parsed=%s", sorted(ALLOWED_EVENT_TYPES))

if not BOT_TOKEN:
    raise RuntimeError(f"BOT_TOKEN is not set. Expected in {ROOT_ENV}")


# -----------------------
# Error handler
# -----------------------
async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.exception("Unhandled error while handling update", exc_info=context.error)


# -----------------------
# Control handlers
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
            "Команда не распознана. Доступные: "
            "/start, /bind, /unbind, /whoami, /tasks, /events, /history, /ping, /whereami"
        )


# -----------------------
# Lifecycle hooks
# -----------------------
async def _post_init(application: Application) -> None:
    """
    Инициализация зависимостей и запуск poller.

    У вас нет post_startup, поэтому:
      - инициализируем backend и сторы в post_init
      - делаем 1 healthcheck backend
      - стартуем poller только если backend доступен (иначе будет бесконечный ConnectError-спам)
    """
    backend = CorpsiteAPI(base_url=API_BASE_URL, timeout_s=15.0)

    application.bot_data["backend"] = backend
    application.bot_data["admin_tg_ids"] = ADMIN_TG_IDS

    bindings_store = JsonFileStore(BINDINGS_PATH)
    state_store = JsonFileStore(EVENTS_STATE_PATH)

    application.bot_data["bindings_store"] = bindings_store
    application.bot_data["state_store"] = state_store
    application.bot_data["poll_interval_s"] = POLL_INTERVAL_S
    application.bot_data["allowed_event_types"] = ALLOWED_EVENT_TYPES

    log.info("Initialized backend client. API_BASE_URL=%s", API_BASE_URL)
    log.info(
        "Events polling configured. interval=%ss bindings=%s state=%s",
        POLL_INTERVAL_S,
        BINDINGS_PATH,
        EVENTS_STATE_PATH,
    )

    # защита от повторного запуска
    existing: Any = application.bot_data.get("events_poll_task")
    if existing is not None and getattr(existing, "done", lambda: True)() is False:
        log.info("Events polling already running; skip start")
        return

    # healthcheck backend (1 раз)
    # если backend мёртв — poller не стартуем (иначе постоянные ConnectError)
    hc = await backend.get_my_events(user_id=(next(iter(ADMIN_TG_IDS)) if ADMIN_TG_IDS else 1), limit=1, offset=0)
    if hc.status_code == 0:
        log.warning("Backend is not reachable at startup. Poller NOT started. base_url=%s", API_BASE_URL)
        return
    # 401/403 тоже означает "достучались" (ACL/заголовок), это ок для healthcheck
    log.info("Backend healthcheck ok. status=%s", hc.status_code)

    task = asyncio.create_task(
        events_polling_loop(
            application=application,
            backend=backend,
            poll_interval_s=POLL_INTERVAL_S,
            bindings_store=bindings_store,
            state_store=state_store,
            per_user_limit=200,
            allowed_types=ALLOWED_EVENT_TYPES,
        ),
        name="events-poller",
    )
    application.bot_data["events_poll_task"] = task
    log.info("Events polling started.")


async def _post_stop(application: Application) -> None:
    """
    Корректная остановка фоновых задач.
    """
    t: Any = application.bot_data.get("events_poll_task")
    if t is None:
        return

    try:
        t.cancel()
        await t
    except asyncio.CancelledError:
        pass
    except Exception:
        log.exception("Failed while stopping events poller task")


async def _post_shutdown(application: Application) -> None:
    """
    Закрытие ресурсов.
    """
    backend: Optional[CorpsiteAPI] = application.bot_data.get("backend")  # type: ignore[assignment]
    if backend is not None:
        try:
            await backend.aclose()
        except Exception:
            log.exception("Failed to close backend client")


# -----------------------
# Main
# -----------------------
def main() -> None:
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(_post_init)
        .post_stop(_post_stop)
        .post_shutdown(_post_shutdown)
        .build()
    )
    app.add_error_handler(on_error)

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("bind", cmd_bind))
    app.add_handler(CommandHandler("unbind", cmd_unbind))
    app.add_handler(CommandHandler("whoami", cmd_whoami))

    app.add_handler(CommandHandler("events", cmd_events))
    app.add_handler(CommandHandler("history", cmd_events))

    app.add_handler(CommandHandler("tasks", cmd_task))

    app.add_handler(CommandHandler("ping", cmd_ping))
    app.add_handler(CommandHandler("whereami", cmd_whereami))

    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    log.info("Bot started. Polling...")
    app.run_polling(drop_pending_updates=True, close_loop=False)


if __name__ == "__main__":
    main()
