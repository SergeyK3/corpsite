# corpsite-bot/src/bot/integrations/corpsite_api.py

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx


@dataclass
class APIResponse:
    status_code: int
    json: Any = None
    text: str = ""


class CorpsiteAPI:
    """
    Minimal async API client for Corpsite backend.
    Uses X-User-Id header for auth/ACL.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout_s: float = 10.0,
    ) -> None:
        self.base_url = (base_url or os.getenv("CORPSITE_API_BASE_URL") or "").strip().rstrip("/")
        if not self.base_url:
            raise RuntimeError("CORPSITE_API_BASE_URL is not set")

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout_s),
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    # -----------------------
    # Low-level request helper
    # -----------------------

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

        try:
            r = await self._client.request(
                method=method,
                url=path,
                headers=headers,
                params=params,
                json=json_body,
            )
        except Exception as e:
            return APIResponse(status_code=0, json=None, text=str(e))

        parsed: Any = None
        try:
            if r.content:
                parsed = r.json()
        except Exception:
            parsed = None

        return APIResponse(status_code=r.status_code, json=parsed, text=r.text)

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

    async def submit_report(
        self,
        *,
        task_id: int,
        user_id: int,
        report_link: str,
        current_comment: str = "",
    ) -> APIResponse:
        body = {"report_link": str(report_link).strip(), "current_comment": str(current_comment or "").strip()}
        return await self._request("POST", f"/tasks/{int(task_id)}/report", user_id=user_id, json_body=body)

    async def approve_report(
        self,
        *,
        task_id: int,
        user_id: int,
        approve: bool = True,
        current_comment: str = "",
    ) -> APIResponse:
        body = {"approve": bool(approve), "current_comment": str(current_comment or "").strip()}
        return await self._request("POST", f"/tasks/{int(task_id)}/approve", user_id=user_id, json_body=body)

    async def task_action(
        self,
        *,
        task_id: int,
        user_id: int,
        action: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> APIResponse:
        """
        Unified actions endpoint:
          POST /tasks/{task_id}/actions/{action}
        action: report | approve | reject
        """
        action_norm = str(action).strip().lower()
        return await self._request(
            "POST",
            f"/tasks/{int(task_id)}/actions/{action_norm}",
            user_id=user_id,
            json_body=(payload or {}),
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
        """
        Backend:
          GET /tasks/{task_id}/events?include_archived=&since_audit_id=&limit=
        Returns: list[ { event_type, actor_user_id, actor_role_id, created_at, payload } ]
        """
        params: Dict[str, Any] = {
            "include_archived": bool(include_archived),
            "limit": int(limit),
        }
        if since_audit_id is not None:
            params["since_audit_id"] = int(since_audit_id)

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
        """
        Backend:
          GET /tasks/me/events?limit=&offset=&since_audit_id=&event_type=
        Returns: list[
          { event_id, task_id, event_type, actor_user_id, actor_role_id, created_at, payload }
        ]
        """
        params: Dict[str, Any] = {
            "limit": int(limit),
            "offset": int(offset),
        }
        if since_audit_id is not None:
            params["since_audit_id"] = int(since_audit_id)
        if event_type:
            params["event_type"] = str(event_type).strip()

        return await self._request("GET", "/tasks/me/events", user_id=user_id, params=params)
