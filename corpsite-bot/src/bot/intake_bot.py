# corpsite-bot/src/bot/intake_bot.py
"""Personnel Intake Telegram bot entrypoint (skeleton)."""
from __future__ import annotations

import logging
import os

from telegram.ext import Application, CommandHandler

from .handlers.intake_start import cmd_intake_start

log = logging.getLogger("corpsite-intake-bot")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def build_intake_application(*, token: str) -> Application:
    """Build intake bot Application with /start only (testable factory)."""
    app = (
        Application.builder()
        .token(token)
        .build()
    )
    app.add_handler(CommandHandler("start", cmd_intake_start))
    return app


def registered_command_names(application: Application) -> list[str]:
    names: list[str] = []
    for group_handlers in application.handlers.values():
        for handler in group_handlers:
            if isinstance(handler, CommandHandler):
                names.extend(handler.commands)
    return sorted(set(names))


def main() -> None:
    token = (os.getenv("INTAKE_BOT_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("INTAKE_BOT_TOKEN is not set")

    app = build_intake_application(token=token)
    log.info("Personnel Intake bot started. Polling...")
    app.run_polling(drop_pending_updates=True, close_loop=False)


if __name__ == "__main__":
    main()
