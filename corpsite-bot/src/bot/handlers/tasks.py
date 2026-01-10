# corpsite-bot/src/bot/handlers/tasks.py
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional, Any, List, Dict

from telegram import Update
from telegram.ext import ContextTypes

from ..storage.bindings import get_binding

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


def _help_text() -> str:
    return (
        "Формат:\n"
        "/tasks                     — список задач\n"
        "/tasks list                — список задач\n"
        "/tasks <id>                — показать задачу\n"
        "/tasks <id> history        — история событий\n"
        "/tasks <id> update title=\"...\" desc=\"...\" scope=\"functional|admin\"\n"
        "/tasks <id> report <url> [comment]\n"
        "/tasks <id> approve [comment]\n"
        "/tasks <id> reject [comment]\n"
    )


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
    if m := (_ASSIGN_SCOPE_KV_RE.search(raw_text) or _SCOPE_KV_RE.search(raw_text)):
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
        return [str(a).lower() for a in aa if str(a).lower() in ("update", "report", "approve", "reject")]
    return []


def _fmt_task_line(t: dict) -> Optional[str]:
    tid = t.get("task_id")
    if not tid:
        return None
    return f"#{tid}  {_safe_title(t.get('title'))}  {_status_label(t.get('status_code'))}"


def _fmt_task_view(t: dict) -> str:
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


def _fmt_dt_short(iso: str) -> str:
    # Оставляем как есть (backend отдаёт ISO). Если нужно укоротить — сделаем отдельно.
    return iso


def _fmt_event_line(ev: dict) -> str:
    ts = _fmt_dt_short(str(ev.get("created_at", "")))
    et = str(ev.get("event_type", ""))
    actor = ev.get("actor_user_id")
    payload = ev.get("payload") or {}

    parts = [f"• {ts} {et}"]
    if actor is not None:
        parts.append(f"от user{actor}")

    link = payload.get("report_link")
    if link:
        parts.append(f"— {link}")

    comment = (payload.get("current_comment") or "").strip()
    if comment:
        parts.append(f"— Комментарий: {comment}")

    return " ".join(parts)


def _parse_task_command(args: list[str]) -> tuple[int, str, list[str]]:
    if len(args) < 2:
        raise CommandParseError(_help_text())

    if not args[0].isdigit():
        raise CommandParseError("task_id должен быть числом. Пример: /tasks 123 approve")

    task_id = int(args[0])
    action = args[1].lower()
    rest = args[2:]

    if action not in ("update", "report", "approve", "reject", "history"):
        raise CommandParseError("Неизвестное действие. Допустимо: update/report/approve/reject/history")

    return task_id, action, rest


def _extract_backend_detail(resp: Any) -> str:
    """
    Пытаемся аккуратно вытащить человеко-читаемую причину из ответа backend.
    Поддерживает варианты detail/message/errors без жёсткой привязки к схеме.
    """
    try:
        data = getattr(resp, "json", None)
        if isinstance(data, dict):
            for k in ("detail", "message", "error"):
                v = data.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()
            # иногда бывают списки ошибок
            errs = data.get("errors")
            if isinstance(errs, list) and errs:
                head = errs[0]
                if isinstance(head, str) and head.strip():
                    return head.strip()
                if isinstance(head, dict):
                    dv = head.get("detail") or head.get("message")
                    if isinstance(dv, str) and dv.strip():
                        return dv.strip()
    except Exception:
        pass

    try:
        txt = getattr(resp, "text", "") or ""
        return txt.strip()
    except Exception:
        return ""


def _user_friendly_action_error(action: str, resp: Any) -> str:
    """
    Unified 403/404/409 semantics:
    - 403: нет прав
    - 404: нет доступа/не найдено
    - 409: конфликт состояния/валидации
    """
    sc = int(getattr(resp, "status_code", 0) or 0)
    detail = _extract_backend_detail(resp)

    if sc == 403:
        return "Недостаточно прав для этого действия."
    if sc == 404:
        return "Задача не найдена или недоступна."
    if sc == 409:
        return detail or "Невозможно выполнить действие в текущем статусе задачи."
    # прочие ошибки
    return detail or "Ошибка выполнения операции."


def _looks_like_url(s: str) -> bool:
    s = (s or "").strip().lower()
    return s.startswith("http://") or s.startswith("https://")


async def cmd_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not msg:
        return

    tg_user = update.effective_user
    if not tg_user:
        return

    user_id = _get_bound_user_id(tg_user.id)
    if user_id is None:
        await msg.reply_text("Вы не привязаны. Используйте /bind (если вы админ) или обратитесь к администратору.")
        return

    backend = context.bot_data.get("backend")
    if backend is None:
        await msg.reply_text("Backend не инициализирован.")
        return

    args = context.args or []

    # /tasks or /tasks list
    if not args or args == ["list"]:
        raw = await backend.list_tasks(user_id=user_id, limit=_LIST_LIMIT)
        items = raw.json.get("items", []) if raw.json else []
        if not items:
            await msg.reply_text("Задач нет.")
            return
        lines = ["Ваши задачи:"]
        for t in items:
            line = _fmt_task_line(t)
            if line:
                lines.append(line)
        await msg.reply_text("\n".join(lines))
        return

    # /tasks <id> (view)
    if len(args) == 1 and args[0].isdigit():
        tid = int(args[0])
        raw = await backend.get_task(task_id=tid, user_id=user_id)
        if raw.status_code != 200 or not raw.json:
            await msg.reply_text("Задача не найдена или недоступна.")
            return
        await msg.reply_text(_fmt_task_view(raw.json))
        return

    # /tasks <id> <action> ...
    try:
        task_id, action, rest = _parse_task_command(args)
    except CommandParseError as e:
        await msg.reply_text(e.message)
        return

    # history
    if action == "history":
        raw = await backend.get_task_events(task_id=task_id, user_id=user_id, include_archived=False)
        if raw.status_code == 404:
            await msg.reply_text("Задача не найдена или недоступна.")
            return
        if raw.status_code != 200 or not isinstance(raw.json, list):
            await msg.reply_text(_user_friendly_action_error(action="history", resp=raw))
            return
        if not raw.json:
            await msg.reply_text(f"История по задаче #{task_id}: событий нет.")
            return

        lines = [f"История по задаче #{task_id}:"]
        for ev in raw.json:
            lines.append(_fmt_event_line(ev))
        await msg.reply_text("\n".join(lines))
        return

    # update
    if action == "update":
        raw_text = (msg.text or "")
        try:
            payload = _parse_update_payload_from_text(raw_text)
        except CommandParseError as e:
            await msg.reply_text(e.message)
            return

        resp = await backend.patch_task(task_id=task_id, user_id=user_id, payload=payload)
        if resp.status_code < 300:
            await msg.reply_text("Изменения сохранены.")
        else:
            await msg.reply_text(_user_friendly_action_error(action="update", resp=resp))
        return

    # report: используем unified action endpoint (устойчивее, чем отдельный submit_report)
    if action == "report":
        if len(rest) < 1:
            await msg.reply_text("Формат: /tasks <id> report <url> [comment]")
            return

        url = rest[0].strip()
        if not _looks_like_url(url):
            await msg.reply_text("Некорректная ссылка. Ожидается URL, начинающийся с http:// или https://")
            return

        comment = " ".join(rest[1:]).strip()
        payload: Dict[str, Any] = {"report_link": url}
        if comment:
            payload["current_comment"] = comment

        resp = await backend.task_action(task_id=task_id, user_id=user_id, action="report", payload=payload)
        if resp.status_code < 300:
            await msg.reply_text("Отчёт отправлен.")
        else:
            await msg.reply_text(_user_friendly_action_error(action="report", resp=resp))
        return

    # approve / reject: unified action endpoint
    if action in ("approve", "reject"):
        comment = " ".join(rest).strip()
        payload: Dict[str, Any] = {}
        if comment:
            payload["current_comment"] = comment

        resp = await backend.task_action(task_id=task_id, user_id=user_id, action=action, payload=payload)
        if resp.status_code < 300:
            await msg.reply_text("Задача принята." if action == "approve" else "Задача возвращена.")
        else:
            await msg.reply_text(_user_friendly_action_error(action=action, resp=resp))
        return
