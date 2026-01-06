# corpsite-bot/src/bot/handlers/tasks.py
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional, Any

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


def _help_text() -> str:
    return (
        "Формат:\n"
        "/tasks                     — список задач\n"
        "/tasks list                — список задач\n"
        "/tasks <id>                — показать задачу\n"
        "/tasks <id> update title=\"...\" desc=\"...\" scope=\"functional|admin\"\n"
        "/tasks <id> report <url>\n"
        "/tasks <id> approve\n\n"
        "Примечание: scope принимает также internal→functional, external→admin."
    )


def _parse_task_command(args: list[str]) -> tuple[int, str, list[str]]:
    # /tasks <id> <action> ...
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
        return s[:900] + ("..." if len(s) > 900 else "")
    except Exception:
        pass

    try:
        t = (resp.text or "").strip()
        if not t:
            return ""
        return t[:900] + ("..." if len(t) > 900 else "")
    except Exception:
        return ""


def _extract_items(payload: object) -> list[dict]:
    """
    Backend может вернуть:
      - list[task]
      - {"items": [...], "total": ...}
      - {"data": [...]} (на будущее)
      - {"results": [...]} (на будущее)
    """
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("items", "data", "results"):
            v = payload.get(key)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
    return []


def _safe_title(value: Any) -> str:
    s = str(value or "").replace("\n", " ").replace("\r", " ").strip()
    if not s:
        s = "Без названия"
    if len(s) > _TITLE_MAX_LEN:
        s = s[: _TITLE_MAX_LEN - 1].rstrip() + "…"
    return s


def _status_label(status_code: Any) -> str:
    code = str(status_code or "").strip()
    icon, ru = _STATUS_MAP.get(code, _UNKNOWN_STATUS)
    return f"{icon} {ru}"


def _get_task_id(t: dict) -> Optional[int]:
    raw = t.get("task_id", t.get("id"))
    try:
        return int(raw)
    except Exception:
        return None


def _get_status_code(t: dict) -> str:
    # backend у вас местами использует status_id / status_code / status
    return str(t.get("status_id", t.get("status_code", t.get("status", ""))) or "").strip()


def _fmt_task_line_v1(t: dict) -> Optional[str]:
    """
    Вариант A (краткий):
      #<id>  <title>  <icon> <status_ru>
    """
    tid = _get_task_id(t)
    if tid is None:
        return None

    title = _safe_title(t.get("title", ""))
    return f"#{tid}  {title}  {_status_label(_get_status_code(t))}"


def _fmt_task_view_v1(t: dict) -> str:
    """
    Боевой вывод для /tasks <id>:
      Задача #123
      Статус: ⏳ В работе
      Заголовок: ...
      Описание: ... (если есть)
    """
    tid = _get_task_id(t)
    tid_str = str(tid) if tid is not None else str(t.get("task_id", t.get("id", "")))

    title = _safe_title(t.get("title", ""))
    desc = str(t.get("description", t.get("desc", "")) or "").strip()
    status_line = _status_label(_get_status_code(t))

    lines: list[str] = [
        f"Задача #{tid_str}",
        f"Статус: {status_line}",
        f"Заголовок: {title}",
    ]
    if desc:
        lines.append(f"Описание: {desc}")
    return "\n".join(lines)


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

    backend = context.bot_data.get("backend")
    if backend is None:
        log.error('backend dependency is missing in bot_data (expected key "backend")')
        await msg.reply_text("Ошибка конфигурации бота: backend не инициализирован.")
        return

    args = context.args or []

    # ---------------------------
    # /tasks, /tasks list  -> list (V1)
    # ---------------------------
    if (not args) or (len(args) == 1 and args[0].strip().lower() == "list"):
        try:
            resp = await backend.list_tasks(user_id=user_id, limit=_LIST_LIMIT, include_archived=False)
        except Exception:
            log.exception("GET /tasks failed")
            await msg.reply_text("Не удалось получить список задач. Попробуйте позже.")
            return

        if resp.status_code != 200:
            await msg.reply_text("Не удалось получить список задач. Попробуйте позже.")
            return

        try:
            data = resp.json()
        except Exception:
            await msg.reply_text("Не удалось получить список задач. Попробуйте позже.")
            return

        items = _extract_items(data)
        if not items:
            await msg.reply_text("У вас нет активных задач.")
            return

        lines: list[str] = ["Ваши задачи:"]
        for t in items[:_LIST_LIMIT]:
            line = _fmt_task_line_v1(t)
            if line:
                lines.append(line)

        if len(lines) == 1:
            await msg.reply_text("У вас нет активных задач.")
            return

        await msg.reply_text("\n".join(lines))
        return

    # ---------------------------
    # /tasks <id>  -> view (V1)
    # ---------------------------
    if len(args) == 1 and args[0].isdigit():
        task_id = int(args[0])
        try:
            resp = await backend.get_task(task_id=task_id, user_id=user_id, include_archived=False)
        except Exception:
            log.exception("GET /tasks/{id} failed")
            await msg.reply_text("Не удалось получить задачу. Попробуйте позже.")
            return

        if resp.status_code != 200:
            # Для view можно оставить UX-маппинг, но без технических деталей.
            ux = map_http_to_ux(resp.status_code, task_id)
            await msg.reply_text(ux.text)
            return

        try:
            data = resp.json()
        except Exception:
            await msg.reply_text("Не удалось получить задачу. Попробуйте позже.")
            return

        if not isinstance(data, dict):
            await msg.reply_text("Не удалось получить задачу. Попробуйте позже.")
            return

        await msg.reply_text(_fmt_task_view_v1(data))
        return

    # ---------------------------
    # /tasks <id> <action> ...
    # ---------------------------
    try:
        task_id, action, rest = _parse_task_command(args)
    except CommandParseError as e:
        await msg.reply_text(e.message)
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
        await msg.reply_text(
            f"{ux.text}\n\nHTTP: {resp.status_code}" + (f"\nДетали backend:\n{preview}" if preview else "")
        )
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
