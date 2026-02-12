# corpsite-bot/src/bot/integrations/corpsite_api.py
from __future__ import annotations

import os
import time
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx

log = logging.getLogger("corpsite-bot.api")


@dataclass
class APIResponse:
    status_code: int
    json: Any = None
    text: str = ""


def _truthy_env(name: str) -> bool:
    v = (os.getenv(name) or "").strip().lower()
    return v in ("1", "true", "yes", "y", "on")


class CorpsiteAPI:
    """
    Minimal async API client for Corpsite backend.

    - Auth/ACL requests use header: X-User-Id
    - Bootstrap flows (self-bind / consume bind-code) use custom headers.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout_s: float = 10.0,
    ) -> None:
        # Priority:
        # 1) base_url argument (from bot.py)
        # 2) API_BASE_URL (.env)
        # 3) CORPSITE_API_BASE_URL (legacy fallback)
        env_url = (os.getenv("API_BASE_URL") or os.getenv("CORPSITE_API_BASE_URL") or "").strip()
        self.base_url = (base_url or env_url).strip().rstrip("/")
        if not self.base_url:
            raise RuntimeError("API_BASE_URL (or CORPSITE_API_BASE_URL) is not set")

        # Token for bind-consume (bot -> backend). Required for POST /tg/bind/consume only.
        self._bot_bind_token = (os.getenv("BOT_BIND_TOKEN") or "").strip()

        # Enable detailed HTTP logs only when needed.
        self._trace = _truthy_env("CORPSITE_HTTP_TRACE")

        ts = float(timeout_s)
        timeout = httpx.Timeout(
            timeout=ts,
            connect=min(5.0, ts),
            read=ts,
            write=ts,
            pool=min(5.0, ts),
        )

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            follow_redirects=True,
        )

        log.info(
            "CorpsiteAPI initialized. base_url=%s timeout_s=%s trace=%s",
            self.base_url,
            ts,
            self._trace,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        user_id: int,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> APIResponse:
        headers = {"X-User-Id": str(int(user_id))}
        t0 = time.perf_counter()

        if self._trace:
            j = None if json_body is None else {k: json_body.get(k) for k in list(json_body.keys())[:20]}
            log.info(
                "HTTP -> %s %s user_id=%s params=%s json_keys=%s",
                method,
                path,
                user_id,
                params,
                None if j is None else list(j.keys()),
            )

        try:
            r = await self._client.request(
                method=method,
                url=path,
                headers=headers,
                params=params,
                json=json_body,
            )
        except Exception as e:
            dt = time.perf_counter() - t0
            log.warning("HTTP !! %s %s user_id=%s failed after %.3fs: %s", method, path, user_id, dt, repr(e))
            return APIResponse(status_code=0, json=None, text=str(e))

        dt = time.perf_counter() - t0

        parsed: Any = None
        try:
            if r.content:
                parsed = r.json()
        except Exception:
            parsed = None

        if self._trace:
            snippet = (r.text or "")[:300]
            log.info(
                "HTTP <- %s %s user_id=%s status=%s %.3fs body=%s",
                method,
                path,
                user_id,
                r.status_code,
                dt,
                snippet,
            )

        return APIResponse(status_code=r.status_code, json=parsed, text=r.text)

    async def _request_headers(
        self,
        method: str,
        path: str,
        *,
        headers: Dict[str, str],
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> APIResponse:
        """
        Low-level request with arbitrary headers (no X-User-Id requirement).
        Use for bootstrap/auth flows such as self-bind / consume bind-code.
        """
        t0 = time.perf_counter()

        if self._trace:
            j = None if json_body is None else {k: json_body.get(k) for k in list(json_body.keys())[:20]}
            log.info(
                "HTTP -> %s %s headers_keys=%s params=%s json_keys=%s",
                method,
                path,
                list(headers.keys()),
                params,
                None if j is None else list(j.keys()),
            )

        try:
            r = await self._client.request(
                method=method,
                url=path,
                headers=headers,
                params=params,
                json=json_body,
            )
        except Exception as e:
            dt = time.perf_counter() - t0
            log.warning("HTTP !! %s %s failed after %.3fs: %s", method, path, dt, repr(e))
            return APIResponse(status_code=0, json=None, text=str(e))

        dt = time.perf_counter() - t0

        parsed: Any = None
        try:
            if r.content:
                parsed = r.json()
        except Exception:
            parsed = None

        if self._trace:
            snippet = (r.text or "")[:300]
            log.info("HTTP <- %s %s status=%s %.3fs body=%s", method, path, r.status_code, dt, snippet)

        return APIResponse(status_code=r.status_code, json=parsed, text=r.text)

    # -----------------------
    # Diagnostics / Meta
    # -----------------------

    async def health(self) -> APIResponse:
        return await self._request_headers("GET", "/health", headers={})

    async def get_task_statuses(self, *, user_id: int) -> APIResponse:
        return await self._request("GET", "/meta/task-statuses", user_id=user_id)

    # -----------------------
    # Auth / Bind
    # -----------------------

    async def self_bind(
        self,
        *,
        telegram_user_id: int,
        telegram_username: Optional[str] = None,
    ) -> APIResponse:
        """
        POST /auth/self-bind
        Headers:
          X-Telegram-User-Id: <int>
          X-Telegram-Username: <str> (optional)
        """
        headers: Dict[str, str] = {"X-Telegram-User-Id": str(int(telegram_user_id))}
        if telegram_username:
            headers["X-Telegram-Username"] = str(telegram_username).strip()
        return await self._request_headers("POST", "/auth/self-bind", headers=headers)

    async def consume_bind_code(
        self,
        *,
        code: str,
        telegram_user_id: int,
    ) -> APIResponse:
        """
        POST /tg/bind/consume
        Headers:
          X-Bot-Token: <BOT_BIND_TOKEN from bot .env>
        JSON:
          { "code": "...", "tg_user_id": 123 }
        """
        if not self._bot_bind_token:
            return APIResponse(status_code=0, json=None, text="BOT_BIND_TOKEN is not set in bot environment")

        headers: Dict[str, str] = {"X-Bot-Token": self._bot_bind_token}
        body = {"code": str(code or "").strip(), "tg_user_id": int(telegram_user_id)}
        return await self._request_headers("POST", "/tg/bind/consume", headers=headers, json_body=body)

    # -----------------------
    # Tasks
    # -----------------------

    async def list_tasks(
        self,
        *,
        user_id: int,
        period_id: Optional[int] = None,
        status_code: Optional[str] = None,
        search: Optional[str] = None,
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> APIResponse:
        params: Dict[str, Any] = {
            "include_archived": bool(include_archived),
            "limit": int(limit),
            "offset": int(offset),
        }
        if period_id is not None:
            params["period_id"] = int(period_id)
        if status_code:
            params["status_code"] = str(status_code).strip()
        if search:
            params["search"] = str(search)

        return await self._request("GET", "/tasks", user_id=user_id, params=params)

    async def get_task(
        self,
        *,
        task_id: int,
        user_id: int,
        include_archived: bool = False,
    ) -> APIResponse:
        params = {"include_archived": bool(include_archived)}
        return await self._request("GET", f"/tasks/{int(task_id)}", user_id=user_id, params=params)

    async def patch_task(
        self,
        *,
        task_id: int,
        user_id: int,
        payload: Dict[str, Any],
    ) -> APIResponse:
        return await self._request("PATCH", f"/tasks/{int(task_id)}", user_id=user_id, json_body=payload)

    async def task_action(
        self,
        *,
        task_id: int,
        user_id: int,
        action: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> APIResponse:
        action_norm = str(action).strip().lower()
        return await self._request(
            "POST",
            f"/tasks/{int(task_id)}/actions/{action_norm}",
            user_id=user_id,
            json_body=(payload or {}),
        )

    async def submit_report(
        self,
        *,
        task_id: int,
        user_id: int,
        report_link: str,
        current_comment: str = "",
    ) -> APIResponse:
        body = {
            "report_link": str(report_link).strip(),
            "current_comment": str(current_comment or "").strip(),
        }
        return await self.task_action(task_id=task_id, user_id=user_id, action="report", payload=body)

    async def approve_report(
        self,
        *,
        task_id: int,
        user_id: int,
        approve: bool = True,
        current_comment: str = "",
    ) -> APIResponse:
        comment = str(current_comment or "").strip()
        if bool(approve):
            return await self.task_action(
                task_id=task_id,
                user_id=user_id,
                action="approve",
                payload={"current_comment": comment},
            )
        return await self.task_action(
            task_id=task_id,
            user_id=user_id,
            action="reject",
            payload={"current_comment": comment},
        )

    # -----------------------
    # Events / History
    # -----------------------

    async def get_task_events(
        self,
        *,
        task_id: int,
        user_id: int,
        include_archived: bool = False,
        since_audit_id: Optional[int] = None,
        limit: int = 200,
    ) -> APIResponse:
        params: Dict[str, Any] = {
            "include_archived": bool(include_archived),
            "limit": int(limit),
        }
        if since_audit_id is not None:
            params["cursor"] = int(since_audit_id)

        return await self._request("GET", f"/tasks/{int(task_id)}/events", user_id=user_id, params=params)

    async def get_my_events(
        self,
        *,
        user_id: int,
        limit: int = 200,
        offset: int = 0,
        since_audit_id: Optional[int] = None,
        event_type: Optional[str] = None,
    ) -> APIResponse:
        params: Dict[str, Any] = {
            "limit": int(limit),
            "offset": int(offset),
        }
        if since_audit_id is not None:
            params["cursor"] = int(since_audit_id)
        if event_type:
            params["event_type"] = str(event_type).strip()

        return await self._request("GET", "/tasks/me/events", user_id=user_id, params=params)

    # -----------------------
    # Deliveries (telegram channel ack)
    # -----------------------

    async def get_pending_deliveries(
        self,
        *,
        user_id: int,
        channel: str,
        cursor_from: int = 0,
        cursor_user_id: int = 0,
        limit: int = 200,
    ) -> APIResponse:
        """
        GET /tasks/internal/task-event-deliveries/pending?channel=telegram&cursor_from=0&cursor_user_id=0&limit=200

        Возвращает:
          { "items": [...], "next_cursor": <int>, "next_cursor_audit_id": <int>, "next_cursor_user_id": <int> }
        items содержат audit_id, user_id, task_id, event_type, payload, created_at, channel, status, telegram_chat_id
        """
        ch = str(channel).strip() or "telegram"
        params: Dict[str, Any] = {
            "channel": ch,
            "cursor_from": int(cursor_from),
            "cursor_user_id": int(cursor_user_id),
            "limit": int(limit),
        }
        return await self._request(
            "GET",
            "/tasks/internal/task-event-deliveries/pending",
            user_id=user_id,
            params=params,
        )

    async def ack_delivery(
        self,
        *,
        user_id: int,
        audit_id: int,
        delivery_user_id: int,
        channel: str,
        status: str,
        error_code: Optional[str] = None,
        error_text: Optional[str] = None,
    ) -> APIResponse:
        """
        POST /tasks/internal/task-event-deliveries/ack
        JSON:
          {
            "audit_id": 44,
            "user_id": 34,
            "channel": "telegram",
            "status": "SENT" | "FAILED",
            "error_code": "...",
            "error_text": "..."
          }
        """
        body: Dict[str, Any] = {
            "audit_id": int(audit_id),
            "user_id": int(delivery_user_id),
            "channel": str(channel).strip(),
            "status": str(status or "").strip().upper(),
        }
        if error_code:
            body["error_code"] = str(error_code).strip()
        if error_text:
            body["error_text"] = str(error_text).strip()

        return await self._request(
            "POST",
            "/tasks/internal/task-event-deliveries/ack",
            user_id=user_id,
            json_body=body,
        )
