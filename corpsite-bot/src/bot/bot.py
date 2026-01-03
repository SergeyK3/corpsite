import os
import logging
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


# -----------------------
# Env
# -----------------------
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set. Put BOT_TOKEN=... into corpsite-bot/.env")


# -----------------------
# Logging
# -----------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("corpsite-bot")


# -----------------------
# HTTP helpers
# -----------------------
def http_get_json(url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    r = requests.get(url, params=params or {}, timeout=15)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, dict):
        return {"items": []}
    return data


def fetch_task_statuses() -> List[Dict[str, Any]]:
    url = f"{API_BASE_URL}/meta/task-statuses"
    data = http_get_json(url)
    items = data.get("items", [])
    return items if isinstance(items, list) else []


def fetch_my_tasks(user_id: int) -> List[Dict[str, Any]]:
    """
    MVP контракт:
    GET /tasks?user_id=<int>
    -> {"items":[{"task_id":3,"title":"...","status_code":"WAITING_REPORT","status_name_ru":"...","period_id":1}, ...]}
    """
    url = f"{API_BASE_URL}/tasks"
    data = http_get_json(url, params={"user_id": user_id})
    items = data.get("items", [])
    return items if isinstance(items, list) else []


# -----------------------
# Formatters
# -----------------------
def format_statuses(items: List[Dict[str, Any]]) -> str:
    if not items:
        return "Статусы не найдены (пустой список)."

    lines = ["Статусы задач:"]
    for it in items:
        code = str(it.get("code", "")).strip()
        name_ru = str(it.get("name_ru", "")).strip()
        sort_order = it.get("sort_order", "")
        if sort_order != "":
            lines.append(f"- {code}: {name_ru} (sort={sort_order})")
        else:
            lines.append(f"- {code}: {name_ru}")
    return "\n".join(lines)


def format_task_one(task: Dict[str, Any]) -> str:
    task_id = task.get("task_id")
    title = str(task.get("title", "")).strip()
    period_id = task.get("period_id")
    status_name = str(task.get("status_name_ru", "")).strip()
    status_code = str(task.get("status_code", "")).strip()

    parts = []
    parts.append(f"Задача #{task_id}")
    if title:
        parts.append(f"{title}")
    if period_id is not None:
        parts.append(f"Период: {period_id}")
    if status_name or status_code:
        if status_name and status_code:
            parts.append(f"Статус: {status_name} ({status_code})")
        elif status_name:
            parts.append(f"Статус: {status_name}")
        else:
            parts.append(f"Статус: {status_code}")
    return "\n".join(parts)


# -----------------------
# Handlers
# -----------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Corpsite bot (MVP).\n"
        "Команды:\n"
        "/statuses — статусы задач\n"
        "/my_tasks — мои задачи (MVP)\n"
    )


async def statuses(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        items = fetch_task_statuses()
        await update.message.reply_text(format_statuses(items))
    except requests.RequestException as e:
        log.exception("Failed to fetch statuses")
        await update.message.reply_text(
            "Ошибка запроса к API. Проверьте backend и API_BASE_URL.\n"
            f"API_BASE_URL={API_BASE_URL}\n"
            f"Детали: {e}"
        )
    except Exception as e:
        log.exception("Unexpected error in /statuses")
        await update.message.reply_text(f"Неожиданная ошибка: {e}")


async def my_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Самый простой MVP: используем telegram_user_id как user_id для запроса.
    Позже заменим на сопоставление tg_id -> users.user_id.
    """
    try:
        if not update.effective_user:
            await update.message.reply_text("Не удалось определить пользователя Telegram.")
            return

        tg_user_id = int(update.effective_user.id)

        items = fetch_my_tasks(tg_user_id)
        if not items:
            await update.message.reply_text("Задач не найдено.")
            return

        # одна задача → одно сообщение
        for t in items:
            await update.message.reply_text(format_task_one(t))

    except requests.RequestException as e:
        log.exception("Failed to fetch my tasks")
        await update.message.reply_text(
            "Ошибка запроса к API /tasks. Проверьте, что эндпоинт реализован и доступен.\n"
            f"API_BASE_URL={API_BASE_URL}\n"
            f"Детали: {e}"
        )
    except Exception as e:
        log.exception("Unexpected error in /my_tasks")
        await update.message.reply_text(f"Неожиданная ошибка: {e}")


# -----------------------
# Main
# -----------------------
def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("statuses", statuses))
    app.add_handler(CommandHandler("my_tasks", my_tasks))

    log.info("Bot started. Polling...")
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
