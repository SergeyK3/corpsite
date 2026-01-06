# corpsite-bot/src/bot/handlers/tasks.py
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional, Any, Tuple

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
    1: "IN_PROGRESS",
    2: "WAITING_REPORT",
    3: "WAITING_APPROVAL",
    4: "DONE",
    5: "ARCHIVED",
}


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


def _status_ru(status_code: str) -> str:
    icon, ru = _STATUS_MAP.get(status_code, _UNKNOWN_STATUS)
    return f"{icon} {ru}"


def _get_task_id(t: dict) -> Optional[int]:
    raw = t.get("task_id", t.get("id"))
    try:
        return int(raw)
    except Exception:
        return None


def _normalize_status_code(raw: Any) -> str:
    if raw is None:
        return ""

    if isinstance(raw, str):
        return raw.strip()

    if isinstance(raw, int):
        return STATUS_ID_TO_CODE.get(raw, "")

    if isinstance(raw, float):
        try:
            return STATUS_ID_TO_CODE.get(int(raw), "")
        except Exception:
            return ""

    if isinstance(raw, dict):
        if "code" in raw and raw["code"] is not None:
            return str(raw["code"]).strip()
        if "status" in raw and raw["status"] is not None:
            return str(raw["status"]).strip()
        if "id" in raw and raw["id"] is not None:
            try:
                return STATUS_ID_TO_CODE.get(int(raw["id"]), "")
            except Exception:
                return ""
        if "status_id" in raw and raw["status_id"] is not None:
            try:
                return STATUS_ID_TO_CODE.get(int(raw["status_id"]), "")
            except Exception:
                return ""

    return ""


def _get_status_code(t: dict) -> str:
    raw = t.get("status_id", t.get("status_code", t.get("status")))
    code = _normalize_status_code(raw)
    if not code and raw is not None:
        log.error(
            "Unknown status format/value: raw=%r (type=%s) task_id=%r",
            raw,
            type(raw).__name__,
            t.get("task_id", t.get("id")),
        )
    return code


def _available_actions_by_status(status_code: str) -> list[str]:
    if status_code == "IN_PROGRESS":
        return ["update"]
    if status_code == "WAITING_REPORT":
        return ["report"]
    if status_code == "WAITING_APPROVAL":
        return ["approve"]
    return []


def _is_action_allowed_by_status(status_code: str, action: str) -> bool:
    return action in _available_actions_by_status(status_code)


def _to_int_or_none(v: Any) -> Optional[int]:
    try:
        if v is None:
            return None
        if isinstance(v, bool):
            return None
        return int(v)
    except Exception:
        return None


def _pick_first_int(d: dict, keys: tuple[str, ...]) -> Optional[int]:
    for k in keys:
        if k in d:
            iv = _to_int_or_none(d.get(k))
            if iv is not None:
                return iv
    return None


def _get_executor_user_id(task: dict) -> Optional[int]:
    # Исполнитель (assignee/executor) — разные возможные ключи
    return _pick_first_int(
        task,
        (
            "executor_user_id",
            "assignee_user_id",
            "assigned_to_user_id",
            "assigned_user_id",
            "executor_id",
            "assignee_id",
            "assigned_to",
            "assigned_to_id",
        ),
    )


def _get_initiator_user_id(task: dict) -> Optional[int]:
    # Руководитель/инициатор (creator/owner/author/approver) — разные возможные ключи
    return _pick_first_int(
        task,
        (
            "created_by",
            "created_by_user_id",
            "initiator_user_id",
            "author_user_id",
            "owner_user_id",
            "owner_id",
            "approver_user_id",  # если backend хранит явного согласующего
        ),
    )


def _is_action_allowed_by_role(*, task: dict, user_id: int, action: str) -> Tuple[bool, str]:
    """
    Role-guard:
      - approve: только инициатор/руководитель (по полям creator/initiator/owner/approver)
      - update/report: только исполнитель (по полям executor/assignee)
    Если нужные поля отсутствуют — не блокируем (чтобы не сломать процесс),
    но статус-guard остаётся.
    """
    executor_id = _get_executor_user_id(task)
    initiator_id = _get_initiator_user_id(task)

    if action == "approve":
        if initiator_id is None:
            return True, ""  # нет данных — не блокируем
        if user_id == initiator_id:
            return True, ""
        return False, "Недостаточно прав: approve доступен только руководителю (инициатору задачи)."

    if action in ("update", "report"):
        if executor_id is None:
            return True, ""  # нет данных — не блокируем
        if user_id == executor_id:
            return True, ""
        return False, "Недостаточно прав: update/report доступны только исполнителю задачи."

    return True, ""


def _fmt_task_line_v1(t: dict) -> Optional[str]:
    tid = _get_task_id(t)
    if tid is None:
        return None
    title = _safe_title(t.get("title", ""))
    return f"#{tid}  {title}  {_status_label(_get_status_code(t))}"


def _fmt_task_view_v1(t: dict) -> str:
    tid = _get_task_id(t)
    tid_str = str(tid) if tid is not None else str(t.get("task_id", t.get("id", "")))

    title = _safe_title(t.get("title", ""))
    desc = str(t.get("description", t.get("desc", "")) or "").strip()
    status_code = _get_status_code(t)
    status_line = _status_label(status_code)

    lines: list[str] = [
        f"Задача #{tid_str}",
        f"Статус: {status_line}",
        f"Заголовок: {title}",
    ]
    if desc:
        lines.append(f"Описание: {desc}")

    actions = _available_actions_by_status(status_code)
    if actions:
        lines.append("")
        lines.append(f"Доступные действия: {' / '.join(actions)}")

    return "\n".join(lines)


def _unwrap_backend_result(result: Any) -> Tuple[bool, int, Any]:
    if isinstance(result, (list, dict)):
        return True, 200, result

    status_code = getattr(result, "status_code", None)

    # SimpleResponse-like (json как поле)
    if status_code is not None and hasattr(result, "json") and not callable(getattr(result, "json")):
        data = getattr(result, "json")
        code = int(status_code)
        return (code == 200), code, data

    # response-like (json как метод)
    json_fn = getattr(result, "json", None)
    if status_code is not None and callable(json_fn):
        try:
            data = result.json()
        except Exception:
            return False, int(status_code), None
        code = int(status_code)
        return (code == 200), code, data

    return False, 0, None


async def _fetch_task_for_guard(
    backend: Any,
    *,
    task_id: int,
    user_id: int,
) -> Tuple[Optional[dict], Optional[int]]:
    try:
        raw = await backend.get_task(task_id=task_id, user_id=user_id, include_archived=False)
        ok, http_code, data = _unwrap_backend_result(raw)
    except Exception:
        log.exception("get_task (guard) failed")
        return None, None

    if not ok or not isinstance(data, dict):
        return None, http_code
    return data, http_code


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

    # /tasks, /tasks list
    if (not args) or (len(args) == 1 and args[0].strip().lower() == "list"):
        try:
            raw = await backend.list_tasks(user_id=user_id, limit=_LIST_LIMIT, include_archived=False)
            ok, http_code, data = _unwrap_backend_result(raw)
        except Exception:
            log.exception("list_tasks failed")
            await msg.reply_text("Не удалось получить список задач. Попробуйте позже.")
            return

        if not ok or data is None:
            log.error("list_tasks not ok: http=%s data_type=%s", http_code, type(data).__name__)
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

    # /tasks <id>
    if len(args) == 1 and args[0].isdigit():
        task_id = int(args[0])
        try:
            raw = await backend.get_task(task_id=task_id, user_id=user_id, include_archived=False)
            ok, http_code, data = _unwrap_backend_result(raw)
        except Exception:
            log.exception("get_task failed")
            await msg.reply_text("Не удалось получить задачу. Попробуйте позже.")
            return

        if not ok or not isinstance(data, dict):
            ux = map_http_to_ux(http_code if http_code else 500, task_id)
            await msg.reply_text(ux.text)
            return

        await msg.reply_text(_fmt_task_view_v1(data))
        return

    # /tasks <id> <action> ...
    try:
        task_id, action, rest = _parse_task_command(args)
    except CommandParseError as e:
        await msg.reply_text(e.message)
        return

    # ---------------------------
    # Guard: получаем актуальную задачу (для статуса + ролей)
    # ---------------------------
    task_for_guard, http_code = await _fetch_task_for_guard(backend, task_id=task_id, user_id=user_id)
    if task_for_guard is None:
        if http_code:
            ux = map_http_to_ux(http_code, task_id)
            await msg.reply_text(ux.text)
        else:
            await msg.reply_text("Не удалось проверить статус/права по задаче. Попробуйте позже.")
        return

    current_status = _get_status_code(task_for_guard)

    # 1) Guard по статусу
    if not _is_action_allowed_by_status(current_status, action):
        allowed = _available_actions_by_status(current_status)
        if allowed:
            await msg.reply_text(
                f"Действие недоступно для текущего статуса: {_status_ru(current_status)}.\n"
                f"Доступные действия: {' / '.join(allowed)}"
            )
        else:
            await msg.reply_text(
                f"Действия недоступны для текущего статуса: {_status_ru(current_status)}."
            )
        return

    # 2) Guard по ролям (инициатор/исполнитель)
    ok_role, deny_msg = _is_action_allowed_by_role(task=task_for_guard, user_id=user_id, action=action)
    if not ok_role:
        await msg.reply_text(deny_msg)
        return

    # ---------------------------
    # Allowed actions
    # ---------------------------
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
