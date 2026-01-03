from __future__ import annotations

import os
import time
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, List

import httpx


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TaskStatus:
    code: str
    name: str
    name_ru: str

    # Если backend позже добавит тексты уведомлений — подхватим без изменения кода бота
    # Например: notification_text, message_template, etc.
    notification_text: Optional[str] = None


class MetaApiError(RuntimeError):
    pass


class MetaApiClient:
    """
    Клиент для Meta API Corpsite.
    Основная цель: получить статусы задач и их русские названия/уведомления.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout_s: float = 10.0,
        cache_ttl_s: int = 600,
    ) -> None:
        self.base_url = (base_url or os.getenv("META_API_BASE_URL") or "http://127.0.0.1:8000").rstrip("/")
        self.timeout_s = timeout_s
        self.cache_ttl_s = cache_ttl_s

        self._cache_fetched_at: float = 0.0
        self._cache_by_code: Dict[str, TaskStatus] = {}

    # -------------------------
    # Public API (async)
    # -------------------------
    async def get_task_statuses(self, force_refresh: bool = False) -> Dict[str, TaskStatus]:
        """
        Возвращает словарь {CODE: TaskStatus}.
        Использует TTL-кэш; обновляет при force_refresh=True или по истечении TTL.
        """
        if not force_refresh and self._is_cache_valid():
            return self._cache_by_code

        statuses = await self._fetch_task_statuses()
        by_code = {s.code: s for s in statuses if s.code}

        # Если API вернул пусто — это ошибка интеграции (лучше упасть, чем молча работать неверно)
        if not by_code:
            raise MetaApiError("Meta API вернул пустой список статусов или не содержит 'code'.")

        self._cache_by_code = by_code
        self._cache_fetched_at = time.time()
        return self._cache_by_code

    async def get_status_name_ru(self, code: str, fallback: Optional[str] = None) -> str:
        """
        Удобный метод: получить name_ru по коду статуса.
        """
        try:
            statuses = await self.get_task_statuses()
            if code in statuses and statuses[code].name_ru:
                return statuses[code].name_ru
        except Exception:
            # Логи только при ошибке
            logger.exception("Ошибка при получении name_ru статуса из Meta API (code=%s).", code)

        return fallback or code

    async def get_status_notification_text(self, code: str, fallback: Optional[str] = None) -> Optional[str]:
        """
        Если backend отдаёт текст уведомления (например notification_text),
        бот может использовать его напрямую.
        """
        try:
            statuses = await self.get_task_statuses()
            if code in statuses:
                txt = statuses[code].notification_text
                if txt:
                    return txt
        except Exception:
            logger.exception("Ошибка при получении notification_text из Meta API (code=%s).", code)

        return fallback

    async def build_one_task_one_message(
        self,
        task_title: str,
        status_code: str,
        task_url: Optional[str] = None,
        fallback_text: Optional[str] = None,
    ) -> str:
        """
        Формирует одно итоговое сообщение на одну задачу:
        - приоритет: notification_text (если есть в API)
        - иначе: "{task_title}\nСтатус: {name_ru}\n{url}"
        """
        notify = await self.get_status_notification_text(status_code)
        if notify:
            # Если backend использует плейсхолдеры, поддержим два варианта без жёсткой привязки:
            # {title}, {status}, {url}
            name_ru = await self.get_status_name_ru(status_code)
            url_part = task_url or ""
            try:
                msg = notify.format(title=task_title, status=name_ru, url=url_part)
                return msg.strip()
            except Exception:
                # если шаблон кривой — не ломаем бота
                logger.exception("Не удалось применить шаблон notification_text (code=%s).", status_code)

        name_ru = await self.get_status_name_ru(status_code)
        parts = [task_title, f"Статус: {name_ru}"]
        if task_url:
            parts.append(task_url)
        msg = "\n".join(parts).strip()

        return msg if msg else (fallback_text or "")

    # -------------------------
    # Low-level fetch
    # -------------------------
    async def _fetch_task_statuses(self) -> List[TaskStatus]:
        url = f"{self.base_url}/meta/task-statuses"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                r = await client.get(url)
                r.raise_for_status()
                data = r.json()
        except Exception as e:
            # Логи только при ошибке
            logger.exception("Ошибка запроса Meta API: GET %s", url)
            raise MetaApiError(f"Не удалось получить статусы из Meta API: {e}") from e

        # Ожидаемые варианты формата:
        # 1) [{"code":"IN_PROGRESS","name":"IN_PROGRESS","name_ru":"..."}]
        # 2) {"items":[...]} или {"data":[...]} — поддержим мягко
        items: Any = data
        if isinstance(data, dict):
            items = data.get("items") or data.get("data") or data.get("results") or data.get("statuses") or []

        if not isinstance(items, list):
            raise MetaApiError("Неподдерживаемый формат ответа Meta API для task-statuses (ожидался список).")

        result: List[TaskStatus] = []
        for raw in items:
            if not isinstance(raw, dict):
                continue

            code = (raw.get("code") or raw.get("status") or raw.get("id") or "").strip()
            name = (raw.get("name") or code or "").strip()
            name_ru = (raw.get("name_ru") or raw.get("ru") or raw.get("title_ru") or "").strip()

            # Подхват возможных полей текста уведомления (если появятся на backend)
            notification_text = (
                raw.get("notification_text")
                or raw.get("notify_text")
                or raw.get("message_text")
                or raw.get("message_template")
            )
            if isinstance(notification_text, str):
                notification_text = notification_text.strip()
            else:
                notification_text = None

            # Если name_ru не пришёл — сделаем минимальный fallback, чтобы бот не “молчал”
            if not name_ru:
                name_ru = code or name or "Статус"

            if code:
                result.append(TaskStatus(code=code, name=name, name_ru=name_ru, notification_text=notification_text))

        return result

    def _is_cache_valid(self) -> bool:
        if not self._cache_by_code:
            return False
        return (time.time() - self._cache_fetched_at) < self.cache_ttl_s
