# tests/test_intake_bot_entrypoint.py
"""Minimal checks for Personnel Intake bot entrypoint skeleton."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram.ext import CommandHandler

ROOT = Path(__file__).resolve().parents[1]
BOT_SRC = ROOT / "corpsite-bot" / "src"

OPERATIONAL_SECRET_ENV_VARS = (
    "INTERNAL_API_TOKEN",
    "BOT_BIND_TOKEN",
    "BOT_TOKEN",
)


def _import_intake_bot():
    bot_src = str(BOT_SRC)
    if bot_src not in sys.path:
        sys.path.insert(0, bot_src)
    import bot.intake_bot as intake_bot  # noqa: WPS433

    return intake_bot


@pytest.fixture
def intake_bot_module(monkeypatch: pytest.MonkeyPatch):
    for name in OPERATIONAL_SECRET_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("INTAKE_BOT_TOKEN", "test-intake-bot-token")
    return _import_intake_bot()


def test_build_intake_application_without_operational_secrets(intake_bot_module) -> None:
    mod = intake_bot_module
    app = mod.build_intake_application(token="dummy-intake-token-for-test")
    assert mod.registered_command_names(app) == ["start"]


def test_intake_entrypoint_registers_only_start_handler(intake_bot_module) -> None:
    mod = intake_bot_module
    app = mod.build_intake_application(token="dummy-intake-token-for-test")

    command_handlers = [
        handler
        for group_handlers in app.handlers.values()
        for handler in group_handlers
        if isinstance(handler, CommandHandler)
    ]
    assert len(command_handlers) == 1
    assert command_handlers[0].commands == frozenset({"start"})


def test_intake_start_message(intake_bot_module) -> None:
    from bot.handlers.intake_start import INTAKE_START_MESSAGE, cmd_intake_start  # noqa: WPS433

    msg = MagicMock()
    msg.reply_text = AsyncMock()
    update = MagicMock()
    update.effective_message = msg

    asyncio.run(cmd_intake_start(update, MagicMock()))

    msg.reply_text.assert_called_once_with(INTAKE_START_MESSAGE)
