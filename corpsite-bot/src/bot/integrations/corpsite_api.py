from __future__ import annotations

from typing import Any, Dict, List, Optional

from telegram import Update
from telegram.ext import ContextTypes

from bot.integrations.corpsite_api import CorpsiteAPI
from bot.handlers.bind import require_bound_user


# -----------------------
# Helpers
# -----------------------

def _fmt_event(ev: Dict[str, Any]) -> str:
    """
    Human-readable event formatter for history.
    """
    et = ev.get("event_type", "?")
    ts = ev.get("created_at", "")
    actor = ev.get("actor_user_id")
    payload = ev.get("payload") or {}

    parts = [f"• [{ts}] {et}"]
    if actor is not None:
        parts.append(f"(user {actor})")

    comment = payload.get("current_comment")
    if comment:
        parts.append(f"\n  💬 {comment}")

    link = payload.get("report_link")
    if link:
        parts.append(f"\n  🔗 {link}")

    return " ".join(parts)


# -----------------------
# /tasks command
# -----------------------

async def cmd_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if msg is None:
        return

    backend: CorpsiteAPI = context.application.bot_data["backend"]  # type: ignore[assignment]

    # Ensure user is bound → gives internal user_id
    user_id = await require_bound_user(update, context)
    if user_id is None:
        return

    args = context.args or []

    # -----------------------
    # /tasks  (list)
    # -----------------------
    if not args:
        resp = await backend.list_tasks(user_id=user_id, limit=20)
        if resp.status_code != 200 or not resp.json:
            await msg.reply_text("Не удалось получить список задач.")
            return

        items = resp.json.get("items", [])
        if not items:
            await msg.reply_text("Задач нет.")
            return

        lines: List[str] = ["Ваши задачи:"]
        for t in items:
            lines.append(
                f"#{t['task_id']}  {t['title']}  [{t.get('status_name_ru')}]"
            )

        await msg.reply_text("\n".join(lines))
        return

    # -----------------------
    # /tasks <id> history
    # -----------------------
    if len(args) == 2 and args[1].lower() == "history":
        try:
            task_id = int(args[0])
        except ValueError:
            await msg.reply_text("Неверный id задачи.")
            return

        resp = await backend.get_task_events(
            task_id=task_id,
            user_id=user_id,
            include_archived=False,
        )

        if resp.status_code == 404:
            await msg.reply_text("Задача не найдена или недоступна.")
            return

        if resp.status_code != 200 or not isinstance(resp.json, list):
            await msg.reply_text("Не удалось получить историю задачи.")
            return

        events: List[Dict[str, Any]] = resp.json
        if not events:
            await msg.reply_text(f"История задачи #{task_id} пуста.")
            return

        lines = [f"История задачи #{task_id}:"]
        for ev in events:
            lines.append(_fmt_event(ev))

        await msg.reply_text("\n".join(lines))
        return

    # -----------------------
    # /tasks <id>  (view)
    # -----------------------
    if len(args) == 1:
        try:
            task_id = int(args[0])
        except ValueError:
            await msg.reply_text("Неверный id задачи.")
            return

        resp = await backend.get_task(task_id=task_id, user_id=user_id)
        if resp.status_code != 200 or not resp.json:
            await msg.reply_text("Задача не найдена или недоступна.")
            return

        t = resp.json
        text = (
            f"Задача #{t['task_id']}\n"
            f"{t['title']}\n"
            f"Статус: {t.get('status_name_ru')}\n"
        )

        actions = t.get("allowed_actions") or []
        if actions:
            text += "\nДоступные действия:\n"
            for a in actions:
                text += f"• {a}\n"

        await msg.reply_text(text)
        return

    await msg.reply_text("Использование:\n"
                         "/tasks\n"
                         "/tasks <id>\n"
                         "/tasks <id> history")
