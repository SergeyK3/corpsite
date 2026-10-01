"""Explicit data-exchange permissions; no implicit ADMIN shortcut."""
from __future__ import annotations

from fastapi import HTTPException

from app.security.admin_permissions import has_admin_permission

DATA_EXCHANGE_VIEW = "DATA_EXCHANGE_VIEW"
DATA_EXCHANGE_UPLOAD_PREVIEW = "DATA_EXCHANGE_UPLOAD_PREVIEW"
DATA_EXCHANGE_DRY_RUN = "DATA_EXCHANGE_DRY_RUN"
DATA_EXCHANGE_CONFIRM_APPLY = "DATA_EXCHANGE_CONFIRM_APPLY"
DATA_EXCHANGE_EXPORT_REFERENCE = "DATA_EXCHANGE_EXPORT_REFERENCE"

PERMISSIONS = (
    DATA_EXCHANGE_VIEW,
    DATA_EXCHANGE_UPLOAD_PREVIEW,
    DATA_EXCHANGE_DRY_RUN,
    DATA_EXCHANGE_CONFIRM_APPLY,
    DATA_EXCHANGE_EXPORT_REFERENCE,
)


def require_exchange_permission(user: dict, permission: str) -> int:
    try:
        user_id = int(user["user_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Authentication required.") from exc
    if permission not in PERMISSIONS or not has_admin_permission(user_id, permission):
        raise HTTPException(status_code=403, detail="Data exchange permission required.")
    return user_id
