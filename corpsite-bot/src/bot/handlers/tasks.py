from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional, Any, Tuple, List, Dict

from telegram import Update
from telegram.ext import ContextTypes

from ..storage.bindings import get_binding
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

# UX V1
_TITLE_MAX_LEN = 80
_LIST_LIMIT = 20

_STATUS_MAP: dict[str, tuple[str, str]] = {
    "IN_PROGRESS": ("⏳", "В работе"),
    "WAITING_REPORT": ("🕒", "Ожидает отчёта"),
    "WAITING_APPROVAL": ("👀", "На согласовании"),
    "DONE": ("✅", "Выполнено"),
    "ARCHIVED": ("📦", "Архив"),
}
_UNKNOWN_STATUS = ("❓", "Неизвестный статус")

STATUS_ID_TO_CODE: dict[int, str] = {
    1: "WAITING_REPORT",
    2: "IN_PROGRESS",
    3: "WAITING_APPROVAL",
    4: "DONE",
    5: "ARCHIVED",
    8: "INBOX",
}


def _help_text() -> str:
    return (
        "Формат:\n"
        "/tasks                     — список задач\n"
        "/tasks list                — список задач\n"
        "/tasks <id>                — показать задачу\n"
        "/tasks <id> history        — история событий\n"
        "/tasks <id> update title=\"...\" desc=\"...\" scope=\"functional|admin\"\n"
        "/tasks <id> report <url>\n"
        "/tasks <id> approve\n"
        "/tasks <id> reject\n"
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
    if action not in ("update", "report", "approve", "reject"):
        raise CommandParseError("Неизвестное действие. Допустимо: update/report/approve/reject")

    return task_id, action, rest


def _normalize_assignment_scope(value: str) -> str:
    low = (value or "").strip().lower()
    if low in ("functional", "internal"):
        return "functional"
    if low in ("admin", "external"):
        return "admin"
    return low


def _parse_update_payload_from_text(raw_text: str) -> dict[str, object]:
    payload: dict[str, object] = {}

    if m := _TITLE_KV_RE.search(raw_text):
        payload["title"] = m.group(1).strip()
    if m := _DESC_KV_RE.search(raw_text):
        payload["description"] = m.group(1).strip()
    if m := _ASSIGN_SCOPE_KV_RE.search(raw_text) or _SCOPE_KV_RE.search(raw_text):
        payload["assignment_scope"] = _normalize_assignment_scope(m.group(1))

    if not payload:
        raise CommandParseError(
            'update требует хотя бы одно поле: title="..." или desc="..." или scope="..."'
        )

    return payload


def _safe_title(value: Any) -> str:
    s = str(value or "").replace("\n", " ").strip()
    return (s[:_TITLE_MAX_LEN] + "…") if len(s) > _TITLE_MAX_LEN else (s or "Без названия")


def _status_label(code: Any) -> str:
    icon, ru = _STATUS_MAP.get(str(code), _UNKNOWN_STATUS)
    return f"{icon} {ru}"


def _extract_allowed_actions(task: dict) -> List[str]:
    aa = task.get("allowed_actions")
    if isinstance(aa, list):
        return [str(a).lower() for a in aa if a in ("update", "report", "approve", "reject")]
    return []


def _fmt_task_line_v1(t: dict) -> Optional[str]:
    tid = t.get("task_id")
    if not tid:
        return None
    return f"#{tid}  {_safe_title(t.get('title'))}  {_status_label(t.get('status_code'))}"


def _fmt_task_view_v1(t: dict) -> str:
    lines = [
        f"Задача #{t.get('task_id')}",
        f"Статус: {_status_label(t.get('status_code'))}",
        f"Заголовок: {_safe_title(t.get('title'))}",
    ]
    if t.get("description"):
        lines.append(f"Описание: {t['description']}")
    actions = _extract_allowed_actions(t)
    if actions:
        lines.append(f"\nДоступные действия: {' / '.join(actions)}")
    return "\n".join(lines)


def _fmt_event_line(ev: dict) -> str:
    ts = ev.get("created_at", "")
    et = ev.get("event_type", "")
    actor = ev.get("actor_user_id")
    payload = ev.get("payload") or {}

    line = f"[{ts}] {et}"
    if actor:
        line += f" (user {actor})"
    if payload.get("current_comment"):
        line += f"\n  💬 {payload['current_comment']}"
    if payload.get("report_link"):
        line += f"\n  🔗 {payload['report_link']}"
    return line


async def cmd_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not msg:
        return

    tg_user = update.effective_user
    if not tg_user:
        return

    user_id = _get_bound_user_id(tg_user.id)
    if user_id is None:
        await msg.reply_text("Пользователь не привязан.")
        return

    backend = context.bot_data.get("backend")
    if backend is None:
        await msg.reply_text("Backend не инициализирован.")
        return

    args = context.args or []

    # /tasks list
    if not args or args == ["list"]:
        raw = await backend.list_tasks(user_id=user_id, limit=_LIST_LIMIT)
        items = raw.json.get("items", []) if raw.json else []
        if not items:
            await msg.reply_text("Задач нет.")
            return
        lines = ["Ваши задачи:"]
        for t in items:
            if line := _fmt_task_line_v1(t):
                lines.append(line)
        await msg.reply_text("\n".join(lines))
        return

    # /tasks <id>
    if len(args) == 1 and args[0].isdigit():
        tid = int(args[0])
        raw = await backend.get_task(task_id=tid, user_id=user_id)
        if raw.status_code != 200 or not raw.json:
            await msg.reply_text("Задача недоступна.")
            return
        await msg.reply_text(_fmt_task_view_v1(raw.json))
        return

    # /tasks <id> history
    if len(args) == 2 and args[0].isdigit() and args[1].lower() == "history":
        tid = int(args[0])
        raw = await backend.get_task_events(task_id=tid, user_id=user_id)
        if raw.status_code != 200 or not isinstance(raw.json, list):
            await msg.reply_text("Не удалось получить историю.")
            return
        if not raw.json:
            await msg.reply_text(f"История задачи #{tid} пуста.")
            return
        lines = [f"История задачи #{tid}:"]
        for ev in raw.json:
            lines.append(_fmt_event_line(ev))
        await msg.reply_text("\n".join(lines))
        return

    # /tasks <id> action
    try:
        task_id, action, rest = _parse_task_command(args)
    except CommandParseError as e:
        await msg.reply_text(e.message)
        return

    if action == "report":
        if len(rest) != 1:
            await msg.reply_text("Формат: /tasks <id> report <url>")
            return
        resp = await backend.submit_report(task_id, user_id, rest[0])
        await msg.reply_text(
            "Отчёт отправлен." if resp.status_code < 300 else "Ошибка отправки отчёта."
        )
        return

    if action == "approve":
        resp = await backend.approve(task_id, user_id)
        await msg.reply_text(
            "Задача принята." if resp.status_code < 300 else "Ошибка approve."
        )
        return

    if action == "reject":
        resp = await backend.reject(task_id, user_id)
        await msg.reply_text(
            "Задача возвращена." if resp.status_code < 300 else "Ошибка reject."
        )
        return
