"""Deliver Telegram password-recovery codes without persisting plaintext codes."""
from __future__ import annotations

import asyncio
import logging
import secrets

from telegram.ext import Application

from .integrations.corpsite_api import CorpsiteAPI

log = logging.getLogger("corpsite-bot.password-recovery")


async def password_recovery_polling_loop(*, application: Application, backend: CorpsiteAPI, service_user_id: int, interval_s: float) -> None:
    while True:
        try:
            response = await backend.claim_password_recovery(user_id=service_user_id)
            item = response.json.get("item") if response.status_code == 200 and isinstance(response.json, dict) else None
            if not isinstance(item, dict):
                await asyncio.sleep(max(1.0, interval_s))
                continue
            code = f"{secrets.randbelow(100_000_000):08d}"
            try:
                await application.bot.send_message(
                    chat_id=int(item["telegram_user_id"]),
                    text=f"Код восстановления пароля Corpsite: {code}. Он действует 15 минут.",
                )
            except Exception:
                log.exception("Password recovery Telegram delivery failed: request_id=%s", item.get("request_id"))
                await asyncio.sleep(max(1.0, interval_s))
                continue
            acknowledged = await backend.record_password_recovery_delivery(
                user_id=service_user_id, request_id=str(item["request_id"]), code=code,
            )
            if acknowledged.status_code != 200 or not isinstance(acknowledged.json, dict) or not acknowledged.json.get("accepted"):
                log.error("Password recovery delivery acknowledgement failed: request_id=%s", item.get("request_id"))
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Password recovery polling failure")
        await asyncio.sleep(max(1.0, interval_s))
