# FILE: corpsite-bot/src/bot/events_renderer.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional


def _s(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _clip(s: str, max_len: int) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    if max_len <= 0:
        return ""
    if len(s) <= max_len:
        return s
    return s[: max_len - 1].rstrip() + "…"


def _add_line(lines: list[str], label: str, value: str) -> None:
    if value:
        lines.append(f"{label}: {value}")


def _parse_iso_dt(s: str) -> Optional[datetime]:
    s = (s or "").strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _fmt_dt(dt_s: Any) -> str:
    dt = _parse_iso_dt(_s(dt_s))
    if not dt:
        return ""
    try:
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ""


def _fmt_actions(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (list, tuple, set)):
        items = [_s(x) for x in v]
    elif isinstance(v, str):
        items = [p.strip() for p in v.split(",")]
    else:
        items = [_s(v)]
    items = [x for x in items if x]
    items = [x.lower() for x in items]
    seen = set()
    out: list[str] = []
    for x in items:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return " / ".join(out)


def _actions_ru(actions: str) -> str:
    m = {
        "approve": "Согласовать",
        "reject": "Отклонить",
        "archive": "В архив",
        "report": "Отправить отчёт",
    }
    parts = [p.strip().lower() for p in (actions or "").split("/") if p.strip()]
    out: list[str] = []
    for p in parts:
        out.append(m.get(p, p))
    return " / ".join([x for x in out if x]).strip()


def render_event(event: Dict[str, Any]) -> str:
    event_type = _s(event.get("event_type")).upper()
    task_id = event.get("task_id")
    payload = event.get("payload") or {}

    created_at = _fmt_dt(event.get("created_at"))

    # UX: title from backend-enriched payload.task_title
    title = _s(payload.get("task_title")) or _s(event.get("title")) or _s(payload.get("title"))
    title = _clip(title, 120)

    current_comment = _clip(_s(payload.get("current_comment")), 300)

    report_link = _s(payload.get("report_link"))
    if report_link and not (report_link.startswith("http://") or report_link.startswith("https://")):
        report_link = ""

    actions = _fmt_actions(payload.get("allowed_actions"))
    if not actions:
        if event_type == "REPORT_SUBMITTED":
            actions = "approve / reject"
        elif event_type == "APPROVED":
            actions = "archive"
        elif event_type == "REJECTED":
            actions = "report"
        else:
            actions = ""

    task_part = f"№{task_id}" if isinstance(task_id, int) and task_id > 0 else "№?"

    lines: list[str] = []

    if event_type == "REPORT_SUBMITTED":
        head = f"🟦 Отчёт отправлен — {task_part}"
        if created_at:
            head = f"{head} • {created_at}"
        lines.append(head)
        if title:
            lines.append(title)
        lines.append("")
        _add_line(lines, "Отчёт", report_link)
        _add_line(lines, "Комментарий", current_comment)
        lines.append("")
        _add_line(lines, "Действия", _actions_ru(actions))

    elif event_type == "APPROVED":
        head = f"🟩 Согласовано — {task_part}"
        if created_at:
            head = f"{head} • {created_at}"
        lines.append(head)
        if title:
            lines.append(title)
        lines.append("")
        _add_line(lines, "Комментарий", current_comment)
        _add_line(lines, "Статус", "DONE")
        lines.append("")
        _add_line(lines, "Действия", _actions_ru(actions))

    elif event_type == "REJECTED":
        head = f"🟥 Отклонено — {task_part}"
        if created_at:
            head = f"{head} • {created_at}"
        lines.append(head)
        if title:
            lines.append(title)
        lines.append("")
        _add_line(lines, "Причина/комментарий", current_comment)
        _add_line(lines, "Статус", "WAITING_REPORT")
        lines.append("")
        _add_line(lines, "Действия", _actions_ru(actions))

    else:
        head = f"ℹ️ Обновление — {task_part}"
        if created_at:
            head = f"{head} • {created_at}"
        lines.append(head)
        if title:
            lines.append(title)
        lines.append("")
        _add_line(lines, "Комментарий", current_comment)
        if actions:
            lines.append("")
            _add_line(lines, "Действия", _actions_ru(actions))

    return "\n".join(lines).strip()
