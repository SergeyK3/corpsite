# corpsite-bot/src/bot/events_renderer.py
from __future__ import annotations

from typing import Any, Dict


def _s(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _add_line(lines: list[str], label: str, value: str) -> None:
    if value:
        lines.append(f"{label}: {value}")


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

    lines: list[str] = []

    if event_type == "REPORT_SUBMITTED":
        lines.append(f"Отчёт отправлен • {task_part}")
        lines.append("Статус: Ожидает согласования")
        _add_line(lines, "Ссылка", _s(payload.get("report_link")))
        _add_line(lines, "Комментарий", current_comment)

    elif event_type == "APPROVED":
        lines.append(f"Отчёт принят • {task_part}")
        lines.append("Статус: Выполнено")
        _add_line(lines, "Комментарий", current_comment)

    elif event_type == "REJECTED":
        lines.append(f"Отчёт отклонён • {task_part}")
        lines.append("Статус: Возвращено на доработку")
        _add_line(lines, "Комментарий", current_comment)

    else:
        lines.append(f"Обновление • {task_part}")

    return "\n".join(lines)
