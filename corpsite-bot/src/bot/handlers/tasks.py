# corpsite-bot/src/bot/handlers/tasks.py
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from ..storage.bindings import get_binding  # <-- ВАЖНО: больше не используем BINDINGS напрямую
from ..ux import map_http_to_ux

log = logging.getLogger("corpsite-bot")


@dataclass(frozen=True)
class CommandParseError(Exception):
    message: str


def _get_bound_user_id(tg_user_id: int) -> Optional[int]:
    return get_binding(tg_user_id)


_TITLE_KV_RE = re.compile(r'title="([^"]+)"')
_DESC_KV_RE = re.compile(r'desc="([^"]+)"')
_SCOPE_KV_RE = re.compile(r'scope="([^"]+)"')
_ASSIGN_SCOPE_KV_RE = re.compile(r'assignment_scope="([^"]+)"')


def _help_text() -> str:
    return (
        "Формат:\n"
        "/tasks <id> update title=\"...\" desc=\"...\" scope=\"functional|admin\"\n"
        "/tasks <id> report <url>\n"
        "/tasks <id> approve\n\n"
        "Примечание: scope принимает также internal→functional, external→admin."
    )


def _parse_task_command(args: list[str]) -> tuple[int, str, list[str]]:
    if len(args) < 2:
        raise CommandParseError(_help_text())

    try:
        task_id = int(args[0])
    except ValueError:
        raise CommandParseError("task_id должен быть числом. Пример: /tasks 123 approve")

    action = args[1].lower()
    rest = args[2:]
    if action not in ("update", "report", "approve"):
        raise CommandParseError("Неизвестное действие. Допустимо: update/report/approve")

    return task_id, action, rest


def _normalize_assignment_scope(value: str) -> str:
    v = (value or "").strip()
    if not v:
        return v

    low = v.lower()
    if low in ("functional", "admin"):
        return low
    if low == "internal":
        return "functional"
    if low == "external":
        return "admin"
    return v


def _parse_update_payload_from_text(raw_text: str) -> dict[str, object]:
    payload: dict[str, object] = {}

    m = _TITLE_KV_RE.search(raw_text)
    if m:
        payload["title"] = m.group(1).strip()

    m = _DESC_KV_RE.search(raw_text)
    if m:
        payload["description"] = m.group(1).strip()

    # приоритет: assignment_scope="..." если указали явно
    m = _ASSIGN_SCOPE_KV_RE.search(raw_text)
    if m:
        payload["assignment_scope"] = _normalize_assignment_scope(m.group(1))
    else:
        m = _SCOPE_KV_RE.search(raw_text)
        if m:
            payload["assignment_scope"] = _normalize_assignment_scope(m.group(1))

    if not payload:
        raise CommandParseError(
            'update требует хотя бы одно поле: title="..." или desc="..." или scope="..."'
        )

    return payload


def _resp_body_preview(resp) -> str:
    try:
        j = resp.json()
        s = str(j)
        return s[:800] + ("..." if len(s) > 800 else "")
    except Exception:
        pass

    try:
        t = (resp.text or "").strip()
        if not t:
            return ""
        return t[:800] + ("..." if len(t) > 800 else "")
    except Exception:
        return ""


async def cmd_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if msg is None:
        return

    user = update.effective_user
    if user is None:
        await msg.reply_text("Не удалось определить пользователя Telegram.")
        return

    tg_user_id = user.id
    user_id = _get_bound_user_id(tg_user_id)
    if user_id is None:
        await msg.reply_text("Пользователь не привязан. Обратитесь к администратору.")
        return

    if not context.args:
        await msg.reply_text(_help_text())
        return

    try:
        task_id, action, rest = _parse_task_command(context.args)
    except CommandParseError as e:
        await msg.reply_text(e.message)
        return

    backend = context.bot_data.get("backend")
    if backend is None:
        log.error('backend dependency is missing in bot_data (expected key "backend")')
        await msg.reply_text("Ошибка конфигурации бота: backend не инициализирован.")
        return

    if action == "update":
        raw_text = msg.text or ""
        try:
            payload = _parse_update_payload_from_text(raw_text)
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
            changed: list[str] = []
            if "title" in payload:
                changed.append("заголовок")
            if "description" in payload:
                changed.append("описание")
            if "assignment_scope" in payload:
                changed.append("scope")
            await msg.reply_text(f"Готово. Задача #{task_id}: {', '.join(changed)} обновлено.")
            return

        preview = _resp_body_preview(resp)
        if preview:
            await msg.reply_text(f"{ux.text}\n\nHTTP: {resp.status_code}\nДетали backend:\n{preview}")
        else:
            await msg.reply_text(f"{ux.text}\n\nHTTP: {resp.status_code}")
        return

    if action == "report":
        if len(rest) != 1:
            await msg.reply_text("Формат: /tasks <id> report <url>")
            return

        report_link = rest[0]
        try:
            resp = await backend.submit_report(
                task_id=task_id,
                user_id=user_id,
                report_link=report_link,
                current_comment="",
            )
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
        if len(rest) != 0:
            await msg.reply_text("Формат: /tasks <id> approve")
            return

        try:
            resp = await backend.approve_report(
                task_id=task_id,
                user_id=user_id,
                current_comment="",
            )
        except Exception:
            log.exception("POST /tasks/{id}/approve failed")
            await msg.reply_text(
                "Ошибка запроса к backend (approve). Проверьте, что backend запущен и API_BASE_URL корректный."
            )
            return

        ux = map_http_to_ux(resp.status_code, task_id)
        await msg.reply_text(f"Задача #{task_id} принята и завершена." if ux.ok else ux.text)
        return
