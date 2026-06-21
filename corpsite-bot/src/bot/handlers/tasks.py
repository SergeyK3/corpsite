# corpsite-bot/src/bot/handlers/tasks.py
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Optional, Any, List, Dict, Tuple

from telegram import Update
from telegram.ext import ContextTypes

from ..integrations.corpsite_api import CorpsiteAPI

log = logging.getLogger("corpsite-bot")


@dataclass(frozen=True)
class CommandParseError(Exception):
    message: str


# -----------------------
# Resolve user_id via backend (users.telegram_id)
# -----------------------

# cache: tg_user_id -> (user_id, expires_at_monotonic)
_UID_CACHE: dict[int, Tuple[int, float]] = {}
_UID_CACHE_TTL_S = 600.0  # 10 минут


def _get_backend(context: ContextTypes.DEFAULT_TYPE) -> Optional[CorpsiteAPI]:
    bd = context.bot_data or {}
    api = bd.get("api") or bd.get("corpsite_api") or bd.get("backend")
    return api if isinstance(api, CorpsiteAPI) else None


def _uid_cache_get(tg_user_id: int) -> Optional[int]:
    rec = _UID_CACHE.get(int(tg_user_id))
    if not rec:
        return None
    uid, exp = rec
    if time.monotonic() >= exp:
        _UID_CACHE.pop(int(tg_user_id), None)
        return None
    return int(uid)


def _uid_cache_set(tg_user_id: int, user_id: int) -> None:
    _UID_CACHE[int(tg_user_id)] = (int(user_id), time.monotonic() + _UID_CACHE_TTL_S)


async def _resolve_user_id(
    *,
    backend: CorpsiteAPI,
    tg_user_id: int,
    tg_username: Optional[str],
) -> tuple[Optional[int], int]:
    """
    Returns (user_id or None, status_code)
    status_code:
      200/201 ok
      404 not bound
      0 backend unreachable
      other: backend error
    """
    cached = _uid_cache_get(tg_user_id)
    if cached is not None:
        return cached, 200

    resp = await backend.self_bind(
        telegram_user_id=int(tg_user_id),
        telegram_username=tg_username,
    )
    sc = int(resp.status_code or 0)

    if sc in (200, 201) and isinstance(resp.json, dict):
        uid = resp.json.get("user_id")
        try:
            if uid is not None and int(uid) > 0:
                _uid_cache_set(tg_user_id, int(uid))
                return int(uid), sc
        except Exception:
            return None, sc
        return None, sc

    return None, sc


# -----------------------
# Parsing / formatting
# -----------------------

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
        "Команды задач:\n"
        "/tasks                     — список задач\n"
        "/tasks <id>                — показать задачу\n"
        "/tasks <id> history        — история событий\n"
        "/tasks <id> update title=\"...\" desc=\"...\" scope=\"functional|admin\"\n"
        "/tasks <id> report <url> [comment]\n"
        "/tasks <id> approve [comment]\n"
        "/tasks <id> reject [comment]\n"
        "/tasks help                — справка\n"
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
        return [
            str(a).lower()
            for a in aa
            if str(a).lower() in ("update", "report", "approve", "reject")
        ]
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
        lines.append(f"Доступные действия: {' / '.join(actions)}")
    return "\n".join(lines)


def _fmt_dt_short(iso: str) -> str:
    # Пока оставляем как есть (ISO). Если захотите — сделаем короткий формат.
    return iso


def _fmt_event_line(ev: dict) -> str:
    ts = _fmt_dt_short(str(ev.get("created_at", "")))
    et = str(ev.get("event_type", "")).strip()
    actor = ev.get("actor_user_id")
    payload = ev.get("payload") or {}

    parts = [f"• {ts} {et}".strip()]
    if actor is not None:
        parts.append(f"от user{actor}")

    link = payload.get("report_link")
    if link:
        parts.append(f"— {link}")

    comment = (payload.get("current_comment") or "").strip()
    if comment:
        parts.append(f"— Комментарий: {comment}")

    return " ".join(p for p in parts if p)


def _parse_task_command(args: list[str]) -> tuple[int, str, list[str]]:
    if len(args) < 2:
        raise CommandParseError(_help_text())

    if not args[0].isdigit():
        raise CommandParseError("task_id должен быть числом. Пример: /tasks 123 approve")

    task_id = int(args[0])
    action = args[1].lower()
    rest = args[2:]

    if action not in ("update", "report", "approve", "reject", "history"):
        raise CommandParseError(
            "Неизвестное действие. Допустимо: update/report/approve/reject/history"
        )

    return task_id, action, rest


def _extract_backend_detail(resp: Any) -> str:
    """
    Extracts a short human-readable message from backend response.
    Supports both:
      - detail: "string"
      - detail: {error,message,reason,hint,code}
    """
    # 1) JSON
    try:
        data = getattr(resp, "json", None)

        # Some clients expose json as a method; CorpsiteAPI uses field .json
        if callable(data):
            data = data()

        if isinstance(data, dict):
            # FastAPI default: {"detail": "..."} or {"detail": {...}}
            detail = data.get("detail")
            if isinstance(detail, str) and detail.strip():
                return detail.strip()
            if isinstance(detail, dict):
                # stable UX error contract
                msg = (detail.get("message") or "").strip()
                reason = (detail.get("reason") or "").strip()
                hint = (detail.get("hint") or "").strip()
                code = (detail.get("code") or "").strip()

                parts: List[str] = []
                if msg:
                    parts.append(msg)
                if reason and reason != msg:
                    parts.append(reason)
                if hint:
                    parts.append(hint)
                if not parts and code:
                    parts.append(code)
                return " — ".join(parts).strip()

            # alternative shapes
            for k in ("message", "error"):
                v = data.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()

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

    # 2) Text
    try:
        txt = getattr(resp, "text", "") or ""
        return txt.strip()
    except Exception:
        return ""


def _user_friendly_action_error(action: str, resp: Any) -> str:
    sc = int(getattr(resp, "status_code", 0) or 0)
    detail = _extract_backend_detail(resp)

    if sc == 403:
        return "Недостаточно прав."
    if sc == 404:
        return "Задача не найдена или недоступна."
    if sc == 409:
        return detail or "Невозможно выполнить действие в текущем статусе задачи."
    if sc == 422:
        return detail or "Некорректные данные запроса."
    if sc >= 500:
        return "Ошибка сервера. Попробуйте позже."
    return detail or "Ошибка выполнения операции."


def _looks_like_url(s: str) -> bool:
    s = (s or "").strip().lower()
    return s.startswith("http://") or s.startswith("https://")


def _strip_legacy_decision_token(rest: List[str]) -> List[str]:
    """
    Legacy UX compatibility:
      /tasks <id> approve ok "comment"
      /tasks <id> reject back "comment"

    Tokens ok/back DO NOT control backend action; they should not be included into comment.
    We only strip the first token if it equals ok/back.
    """
    if not rest:
        return rest
    head = (rest[0] or "").strip().lower()
    if head in ("ok", "back"):
        return rest[1:]
    return rest


# -----------------------
# Handler
# -----------------------

async def cmd_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not msg:
        return

    tg_user = update.effective_user
    if not tg_user:
        return

    backend = _get_backend(context)
    if backend is None:
        await msg.reply_text("Сервис временно недоступен.")
        return

    tg_user_id = int(tg_user.id)
    tg_username = (tg_user.username or "").strip() or None

    user_id, sc = await _resolve_user_id(
        backend=backend,
        tg_user_id=tg_user_id,
        tg_username=tg_username,
    )
    if user_id is None:
        if sc == 404:
            await msg.reply_text("Telegram не привязан к профилю. Используйте /bind.")
            return
        if sc == 0:
            await msg.reply_text("Backend временно недоступен. Попробуйте позже.")
            return
        await msg.reply_text("Не удалось определить пользователя. Попробуйте позже.")
        return

    args = context.args or []

    # /tasks help
    if args == ["help"]:
        await msg.reply_text(_help_text())
        return

    # /tasks or /tasks list
    if not args or args == ["list"]:
        raw = await backend.list_tasks(telegram_user_id=tg_user_id, limit=_LIST_LIMIT)

        # Expect dict {"items":[...]} but be defensive
        if raw.status_code != 200 or raw.json is None:
            await msg.reply_text(_user_friendly_action_error(action="list", resp=raw))
            return

        items: List[dict] = []
        if isinstance(raw.json, dict):
            items = raw.json.get("items", []) or []
        elif isinstance(raw.json, list):
            items = raw.json
        else:
            items = []

        if not items:
            await msg.reply_text("Задач нет.")
            return

        lines = ["Ваши задачи:"]
        for t in items:
            if isinstance(t, dict):
                line = _fmt_task_line(t)
                if line:
                    lines.append(line)

        await msg.reply_text("\n".join(lines))
        return

    # /tasks <id> (view)
    if len(args) == 1 and args[0].isdigit():
        tid = int(args[0])
        raw = await backend.get_task(task_id=tid, telegram_user_id=tg_user_id)
        if raw.status_code != 200 or not isinstance(raw.json, dict):
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
        raw = await backend.get_task_events(
            task_id=task_id,
            telegram_user_id=tg_user_id,
            include_archived=False,
        )
        if raw.status_code == 404:
            await msg.reply_text("Задача не найдена или недоступна.")
            return
        if raw.status_code != 200 or not isinstance(raw.json, list):
            await msg.reply_text(_user_friendly_action_error(action="history", resp=raw))
            return
        if not raw.json:
            await msg.reply_text(f"Задача #{task_id}: история пустая.")
            return

        lines = [f"История по задаче #{task_id}:"]
        for ev in raw.json:
            if isinstance(ev, dict):
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

        resp = await backend.patch_task(task_id=task_id, telegram_user_id=tg_user_id, payload=payload)
        if int(resp.status_code or 0) < 300:
            await msg.reply_text("Изменения сохранены.")
        else:
            await msg.reply_text(_user_friendly_action_error(action="update", resp=resp))
        return

    # report
    if action == "report":
        if len(rest) < 1:
            await msg.reply_text("Формат: /tasks <id> report <url> [comment]")
            return

        url = rest[0].strip()
        if not _looks_like_url(url):
            await msg.reply_text("Некорректная ссылка. Нужен URL, начинающийся с http:// или https://")
            return

        comment = " ".join(rest[1:]).strip()
        payload: Dict[str, Any] = {"report_link": url}
        if comment:
            payload["current_comment"] = comment

        resp = await backend.task_action(task_id=task_id, telegram_user_id=tg_user_id, action="report", payload=payload)
        if int(resp.status_code or 0) < 300:
            await msg.reply_text("Отчёт отправлен.")
        else:
            await msg.reply_text(_user_friendly_action_error(action="report", resp=resp))
        return

    # approve / reject
    if action in ("approve", "reject"):
        # Compatibility: strip leading ok/back so they don't pollute current_comment.
        rest = _strip_legacy_decision_token(list(rest))

        comment = " ".join(rest).strip()
        payload: Dict[str, Any] = {}
        if comment:
            payload["current_comment"] = comment

        resp = await backend.task_action(task_id=task_id, telegram_user_id=tg_user_id, action=action, payload=payload)
        if int(resp.status_code or 0) < 300:
            await msg.reply_text("Согласовано." if action == "approve" else "Отклонено.")
        else:
            await msg.reply_text(_user_friendly_action_error(action=action, resp=resp))
        return
