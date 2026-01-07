# corpsite-bot/src/bot/integrations/corpsite_api.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Union, List, Literal

import httpx


JsonT = Optional[Union[Dict[str, Any], List[Any]]]


@dataclass(frozen=True)
class SimpleResponse:
    status_code: int
    json: JsonT = None


class CorpsiteAPI:
    """
    Thin async client for Corpsite backend.
    Auth context is provided via header: X-User-Id.
    """

    def __init__(self, base_url: str, timeout_s: float = 15.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_s = float(timeout_s)
        self._client = httpx.AsyncClient(timeout=self.timeout_s)

    async def aclose(self) -> None:
        """
        IMPORTANT: call on bot shutdown to close underlying HTTP connections.
        """
        await self._client.aclose()

    async def close(self) -> None:
        """
        Alias for aclose() for convenience.
        """
        await self.aclose()

    def _headers(self, user_id: int) -> Dict[str, str]:
        return {"X-User-Id": str(int(user_id))}

    @staticmethod
    def _safe_json(resp: httpx.Response) -> JsonT:
        try:
            if resp.content:
                return resp.json()
        except Exception:
            pass
        return None

    # ----------------------------
    # Tasks: list / get / patch
    # ----------------------------

    async def list_tasks(
        self,
        user_id: int,
        limit: int = 20,
        include_archived: bool = False,
    ) -> SimpleResponse:
        """
        GET /tasks
        """
        url = f"{self.base_url}/tasks"
        params = {
            "limit": int(limit),
            "include_archived": str(bool(include_archived)).lower(),
        }
        resp = await self._client.get(url, params=params, headers=self._headers(user_id))
        return SimpleResponse(status_code=resp.status_code, json=self._safe_json(resp))

    async def get_task(
        self,
        task_id: int,
        user_id: int,
        include_archived: bool = False,
    ) -> SimpleResponse:
        """
        GET /tasks/{id}
        """
        url = f"{self.base_url}/tasks/{int(task_id)}"
        params = {"include_archived": str(bool(include_archived)).lower()}
        resp = await self._client.get(url, params=params, headers=self._headers(user_id))
        return SimpleResponse(status_code=resp.status_code, json=self._safe_json(resp))

    async def patch_task(
        self,
        task_id: int,
        user_id: int,
        payload: Dict[str, Any],
    ) -> SimpleResponse:
        """
        PATCH /tasks/{id}
        Allowed fields are validated by backend.
        """
        url = f"{self.base_url}/tasks/{int(task_id)}"
        resp = await self._client.patch(url, json=payload, headers=self._headers(user_id))
        return SimpleResponse(status_code=resp.status_code, json=self._safe_json(resp))

    # ----------------------------
    # Actions (preferred, new)
    # ----------------------------

    async def task_action(
        self,
        task_id: int,
        user_id: int,
        action: Literal["report", "approve", "reject"],
        payload: Optional[Dict[str, Any]] = None,
    ) -> SimpleResponse:
        """
        POST /tasks/{id}/actions/{action}
        """
        url = f"{self.base_url}/tasks/{int(task_id)}/actions/{action}"
        body = payload or {}
        resp = await self._client.post(url, json=body, headers=self._headers(user_id))
        return SimpleResponse(status_code=resp.status_code, json=self._safe_json(resp))

    async def submit_report(
        self,
        task_id: int,
        user_id: int,
        report_link: str,
        current_comment: str = "",
    ) -> SimpleResponse:
        """
        POST /tasks/{id}/actions/report
        Backend determines actor from X-User-Id; do NOT send submitted_by.
        """
        body = {
            "report_link": (report_link or "").strip(),
            "current_comment": (current_comment or "").strip(),
        }
        return await self.task_action(task_id=task_id, user_id=user_id, action="report", payload=body)

    async def approve(
        self,
        task_id: int,
        user_id: int,
        current_comment: str = "",
    ) -> SimpleResponse:
        """
        POST /tasks/{id}/actions/approve
        Backend determines actor from X-User-Id; do NOT send approved_by.
        """
        body = {"current_comment": (current_comment or "").strip()}
        return await self.task_action(task_id=task_id, user_id=user_id, action="approve", payload=body)

    async def reject(
        self,
        task_id: int,
        user_id: int,
        current_comment: str = "",
    ) -> SimpleResponse:
        """
        POST /tasks/{id}/actions/reject
        """
        body = {"current_comment": (current_comment or "").strip()}
        return await self.task_action(task_id=task_id, user_id=user_id, action="reject", payload=body)

    # ----------------------------
    # Compatibility layer for current bot handlers
    # ----------------------------

    async def approve_report(
        self,
        task_id: int,
        user_id: int,
        current_comment: str = "",
        approve: bool = True,
    ) -> SimpleResponse:
        """
        Compatibility method (used by handlers/tasks.py right now).

        If approve=True -> /actions/approve
        If approve=False -> /actions/reject

        Note: handler currently calls approve_report(...) without approve flag,
        so default approve=True matches "approve".
        """
        if bool(approve):
            return await self.approve(task_id=task_id, user_id=user_id, current_comment=current_comment)
        return await self.reject(task_id=task_id, user_id=user_id, current_comment=current_comment)

    # ----------------------------
    # Legacy endpoints (keep, optional)
    # ----------------------------

    async def submit_report_legacy(
        self,
        task_id: int,
        user_id: int,
        report_link: str,
        current_comment: str = "",
    ) -> SimpleResponse:
        """
        LEGACY: POST /tasks/{id}/report
        Оставлено как fallback, но предпочтительно использовать submit_report().
        """
        url = f"{self.base_url}/tasks/{int(task_id)}/report"
        body = {
            "report_link": (report_link or "").strip(),
            "current_comment": (current_comment or "").strip(),
        }
        resp = await self._client.post(url, json=body, headers=self._headers(user_id))
        return SimpleResponse(status_code=resp.status_code, json=self._safe_json(resp))

    async def approve_report_legacy(
        self,
        task_id: int,
        user_id: int,
        approve: bool = True,
        current_comment: str = "",
    ) -> SimpleResponse:
        """
        LEGACY: POST /tasks/{id}/approve
        В текущем backend approve/reject лучше вызывать через /actions/*.
        """
        url = f"{self.base_url}/tasks/{int(task_id)}/approve"
        body = {
            "approve": bool(approve),
            "current_comment": (current_comment or "").strip(),
        }
        resp = await self._client.post(url, json=body, headers=self._headers(user_id))
        return SimpleResponse(status_code=resp.status_code, json=self._safe_json(resp))
