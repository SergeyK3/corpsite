from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from ..storage.bindings import BINDINGS
from ..ux import map_http_to_ux  # если у вас ux.py в другом месте — поправьте импорт

log = logging.getLogger("corpsite-bot")


@dataclass(frozen=True)
class CommandParseError(Exception):
    message: str


def _get_bound_user_id(tg_user_id: int) -> Optional[int]:
    return BINDINGS.get(tg_user_id)


_TITLE_RE = re.compile(r'^title="(.+)"$')
_DESC_RE = re.compile(r'^desc="(.+)"$')
_SCOPE_RE = re.compile(r'^scope="(.+)"$')


def _parse_task_command(args: list[str]) -> tuple[int, str, list[str]]:
    # /task <id> <action> ...
    if len(args) < 2:
        raise CommandParseError(
            "Формат:\n"
            "/task <id> update title=\"...\" desc=\"...\" scope=\"...\"\n"
            "/task <id> report <url>\n"
            "/task <id> approve"
        )

    try:
        task_id = int(args[0])
    except ValueError:
        raise CommandParseError("task_id должен быть числом. Пример: /task 123 approve")

    action = args[1].lower()
    rest = args[2:]
    if action not in ("update", "report", "approve"):
        raise CommandParseError("Неизвестное действие. Допустимо: update/report/approve")

    return task_id, action, rest


def _parse_update_payload(rest: list[str]) -> dict[str, str]:
    # update title="..." desc="..." scope="..."
    payload: dict[str, str] = {}
    for token in rest:
        m = _TITLE_RE.match(token)
        if m:
            payload["title"] = m.group(1)
            continue

        m = _DESC_RE.match(token)
        if m:
            payload["description"] = m.group(1)
            continue

        m = _SCOPE_RE.match(token)
        if m:
            payload["assignment_scope"] = m.group(1)
            continue

        raise CommandParseError('update принимает только title="..." и/или desc="..." и/или scope="..."')

    if not payload:
        raise CommandParseError('update требует хотя бы одно поле: title="..." или desc="..." или scope="..."')

    return payload


async def cmd_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if msg is None:
        return

    tg_user_id = msg.from_user.id
    user_id = _get_bound_user_id(tg_user_id)
    if user_id is None:
        await msg.reply_text("Пользователь не привязан. Обратитесь к администратору.")
        return

    try:
        task_id, action, rest = _parse_task_command(context.args)
    except CommandParseError as e:
        await msg.reply_text(e.message)
        return

    backend = context.bot_data.get("backend")
    if backend is None:
        # логи только при ошибке
        log.error('backend dependency is missing in bot_data (expected key "backend")')
        await msg.reply_text("Ошибка конфигурации бота: backend не инициализирован.")
        return

    if action == "update":
        try:
            payload = _parse_update_payload(rest)
        except CommandParseError as e:
            await msg.reply_text(e.message)
            return

        try:
            resp = await backend.patch_task(task_id=task_id, user_id=user_id, payload=payload)
        except Exception:
            log.exception("PATCH /tasks/{id} failed")
            await msg.reply_text(
                "Ошибка запроса к backend (PATCH /tasks). Проверьте, что backend запущен и API_BASE_URL корректный."
            )
            return

        ux = map_http_to_ux(resp.status_code, task_id)
        if ux.ok:
            changed = []
            if "title" in payload:
                changed.append("заголовок")
            if "description" in payload:
                changed.append("описание")
            if "assignment_scope" in payload:
                changed.append("scope")
            await msg.reply_text(f"Готово. Задача #{task_id}: {', '.join(changed)} обновлено.")
        else:
            await msg.reply_text(ux.text)
        return

    if action == "report":
        if len(rest) != 1:
            await msg.reply_text("Формат: /task <id> report <url>")
            return

        report_url = rest[0]
        try:
            resp = await backend.submit_report(task_id=task_id, user_id=user_id, report_url=report_url)
        except Exception:
            log.exception("POST /tasks/{id}/report failed")
            await msg.reply_text(
                "Ошибка запроса к backend (report). Проверьте, что backend запущен и API_BASE_URL корректный."
            )
            return

        ux = map_http_to_ux(resp.status_code, task_id)
        await msg.reply_text(
            f"Отчёт по задаче #{task_id} отправлен на согласование." if ux.ok else ux.text
        )
        return

    if action == "approve":
        try:
            resp = await backend.approve_report(task_id=task_id, user_id=user_id)
        except Exception:
            log.exception("POST /tasks/{id}/approve failed")
            await msg.reply_text(
                "Ошибка запроса к backend (approve). Проверьте, что backend запущен и API_BASE_URL корректный."
            )
            return

        ux = map_http_to_ux(resp.status_code, task_id)
        await msg.reply_text(f"Задача #{task_id} принята и завершена." if ux.ok else ux.text)
        return
