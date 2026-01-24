# corpsite-bot/src/bot/events_renderer.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional


def _s(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _add_line(lines: list[str], label: str, value: str) -> None:
    if value:
        lines.append(f"{label}: {value}")


def _parse_iso_dt(s: str) -> Optional[datetime]:
    s = (s or "").strip()
    if not s:
        return None
    try:
        # accept ...Z and ...+00:00
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _fmt_dt(dt_s: Any) -> str:
    dt = _parse_iso_dt(_s(dt_s))
    if not dt:
        return ""
    # leave timezone as-is; show compact
    try:
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ""


def render_event(event: Dict[str, Any]) -> str:
    """
    event from /tasks/me/events:
      - event_id, task_id, event_type, created_at, payload
    Supported types from backend:
      - REPORT_SUBMITTED, APPROVED, REJECTED
    """
    event_type = _s(event.get("event_type")).upper()
    task_id = event.get("task_id")
    payload = event.get("payload") or {}

    task_part = f"Задача #{task_id}" if isinstance(task_id, int) and task_id > 0 else "Задача"
    current_comment = _s(payload.get("current_comment"))
    created_at = _fmt_dt(event.get("created_at"))

    lines: list[str] = []

    if event_type == "REPORT_SUBMITTED":
        head = f"Отчёт отправлен • {task_part}"
        if created_at:
            head = f"{head} • {created_at}"
        lines.append(head)
        lines.append("Статус: Ожидает согласования")
        _add_line(lines, "Ссылка", _s(payload.get("report_link")))
        _add_line(lines, "Комментарий", current_comment)

    elif event_type == "APPROVED":
        head = f"Отчёт принят • {task_part}"
        if created_at:
            head = f"{head} • {created_at}"
        lines.append(head)
        lines.append("Статус: Выполнено")
        _add_line(lines, "Комментарий", current_comment)

    elif event_type == "REJECTED":
        head = f"Отчёт отклонён • {task_part}"
        if created_at:
            head = f"{head} • {created_at}"
        lines.append(head)
        lines.append("Статус: Возвращено на доработку")
        _add_line(lines, "Комментарий", current_comment)

    else:
        head = f"Обновление • {task_part}"
        if created_at:
            head = f"{head} • {created_at}"
        lines.append(head)

    return "\n".join(lines)
