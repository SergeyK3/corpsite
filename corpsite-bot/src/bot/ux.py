from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class UxResult:
    ok: bool
    text: str


def map_http_to_ux(status_code: int, task_id: Optional[int] = None) -> UxResult:
    tid = f" #{task_id}" if task_id is not None else ""

    if status_code in (200, 201, 204):
        return UxResult(ok=True, text=f"Готово.{tid}")

    if status_code == 401:
        return UxResult(ok=False, text="Требуется авторизация. Выполните /start.")
    if status_code == 403:
        return UxResult(ok=False, text=f"Нет прав на это действие по задаче{tid}.")
    if status_code == 404:
        return UxResult(ok=False, text=f"Задача{tid} не найдена или недоступна.")
    if status_code == 409:
        return UxResult(ok=False, text=f"Действие невозможно из-за текущего статуса задачи{tid}.")
    if status_code == 422:
        return UxResult(ok=False, text="Данные не приняты. Проверьте формат.")
    if status_code == 429:
        return UxResult(ok=False, text="Слишком много запросов. Повторите позже.")
    if 500 <= status_code <= 599:
        return UxResult(ok=False, text="Ошибка сервера. Повторите позже.")

    return UxResult(ok=False, text=f"Не удалось выполнить команду (HTTP {status_code}).")
