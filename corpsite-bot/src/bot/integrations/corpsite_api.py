from __future__ import annotations

from typing import Any, Dict, Optional

import requests


class CorpsiteAPI:
    def __init__(self, base_url: str, timeout_s: float = 15.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

    def _headers(self, user_id: int) -> Dict[str, str]:
        return {"X-User-Id": str(user_id)}

    def patch_task(self, *, task_id: int, user_id: int, payload: Dict[str, Any]) -> requests.Response:
        url = f"{self.base_url}/tasks/{task_id}"
        return requests.patch(url, json=payload, headers=self._headers(user_id), timeout=self.timeout_s)

    def submit_report(self, *, task_id: int, user_id: int, report_url: str) -> requests.Response:
        url = f"{self.base_url}/tasks/{task_id}/report"
        return requests.post(
            url,
            json={"report_url": report_url},
            headers=self._headers(user_id),
            timeout=self.timeout_s,
        )

    def approve_report(self, *, task_id: int, user_id: int) -> requests.Response:
        url = f"{self.base_url}/tasks/{task_id}/approve"
        return requests.post(url, json={}, headers=self._headers(user_id), timeout=self.timeout_s)

    def fetch_task_statuses(self) -> dict[str, Any]:
        url = f"{self.base_url}/meta/task-statuses"
        r = requests.get(url, timeout=self.timeout_s)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, dict) else {"items": []}
