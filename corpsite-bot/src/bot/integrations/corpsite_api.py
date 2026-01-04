from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx


@dataclass(frozen=True)
class SimpleResponse:
    status_code: int
    json: Optional[Dict[str, Any]] = None


class CorpsiteAPI:
    def __init__(self, base_url: str, timeout_s: float = 15.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self._client = httpx.AsyncClient(timeout=self.timeout_s)

    def _headers(self, user_id: int) -> Dict[str, str]:
        return {"X-User-Id": str(user_id)}

    @staticmethod
    def _safe_json(resp: httpx.Response) -> Optional[Dict[str, Any]]:
        try:
            if resp.content:
                return resp.json()
        except Exception:
            pass
        return None

    async def patch_task(
        self,
        task_id: int,
        user_id: int,
        payload: Dict[str, Any],
    ) -> SimpleResponse:
        url = f"{self.base_url}/tasks/{task_id}"
        resp = await self._client.patch(url, json=payload, headers=self._headers(user_id))
        return SimpleResponse(status_code=resp.status_code, json=self._safe_json(resp))

    async def submit_report(
        self,
        task_id: int,
        user_id: int,
        report_link: str,
        current_comment: str = "",
    ) -> SimpleResponse:
        url = f"{self.base_url}/tasks/{task_id}/report"
        body = {
            "submitted_by": user_id,
            "report_link": report_link,
            "current_comment": current_comment,
        }
        resp = await self._client.post(url, json=body, headers=self._headers(user_id))
        return SimpleResponse(status_code=resp.status_code, json=self._safe_json(resp))

    async def approve_report(
        self,
        task_id: int,
        user_id: int,
        approve: bool = True,
        current_comment: str = "",
    ) -> SimpleResponse:
        url = f"{self.base_url}/tasks/{task_id}/approve"
        body = {
            "approved_by": user_id,
            "approve": approve,
            "current_comment": current_comment,
        }
        resp = await self._client.post(url, json=body, headers=self._headers(user_id))
        return SimpleResponse(status_code=resp.status_code, json=self._safe_json(resp))
