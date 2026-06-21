# FILE: app/security/bot_internal_auth.py
"""OPS-007a — Telegram bot internal API authentication."""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

from fastapi import Depends, Header, HTTPException

from app.auth import _enrich_user_context, _get_user_by_id
from app.security.directory_scope import has_valid_internal_api_token
from app.tg_bind import resolve_user_id_by_telegram_id

_SERVICE_ACCOUNT_LOGIN = re.compile(r"(^svc_|^service_|^bot_|^system_|^cron_)", re.IGNORECASE)
_SERVICE_ACCOUNT_NAME = re.compile(r"(системн|service account|\bbot\b|\bcron\b)", re.IGNORECASE)


def require_valid_internal_api_token(
    x_internal_api_token: Optional[str] = Header(default=None, alias="X-Internal-Api-Token"),
) -> None:
    if not has_valid_internal_api_token(x_internal_api_token):
        raise HTTPException(status_code=403, detail="Invalid internal API token")


def require_telegram_user_id_header(
    x_telegram_user_id: Optional[int] = Header(default=None, alias="X-Telegram-User-Id"),
) -> int:
    if x_telegram_user_id is None or int(x_telegram_user_id) <= 0:
        raise HTTPException(status_code=400, detail="X-Telegram-User-Id is required and must be > 0")
    return int(x_telegram_user_id)


def is_service_account_user(user: Dict[str, Any]) -> bool:
    login = str(user.get("login") or "")
    full_name = str(user.get("full_name") or "")
    if _SERVICE_ACCOUNT_LOGIN.search(login):
        return True
    if _SERVICE_ACCOUNT_NAME.search(full_name):
        return True
    return False


def resolve_bound_user_id_from_telegram(tg_user_id: int) -> int:
    user_id = resolve_user_id_by_telegram_id(int(tg_user_id))
    if user_id is None:
        raise HTTPException(status_code=404, detail="not bound")
    return int(user_id)


def require_bot_bound_user(
    _internal: None = Depends(require_valid_internal_api_token),
    tg_user_id: int = Depends(require_telegram_user_id_header),
) -> Dict[str, Any]:
    user_id = resolve_bound_user_id_from_telegram(int(tg_user_id))
    user = _get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.get("is_active"):
        raise HTTPException(status_code=403, detail="User is inactive")
    enriched = _enrich_user_context(user)
    if is_service_account_user(enriched):
        raise HTTPException(status_code=403, detail="service account not allowed for bot access")
    return enriched
