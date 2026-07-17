"""Internal onboarding routes for cron/bot (WP-ONBOARDING-002)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.db.engine import engine
from app.directory.common import as_http500
from app.employee_onboarding.application.reminder_service import run_onboarding_reminders
from app.employee_onboarding.infrastructure.notification_repository import (
    ack_onboarding_delivery,
    list_pending_onboarding_deliveries,
)
from app.security.bot_internal_auth import require_valid_internal_api_token

router = APIRouter(prefix="/internal/onboarding", tags=["onboarding-internal"])


class ReminderRunOut(BaseModel):
    due_soon_sent: int
    overdue_sent: int


class DeliveryAckIn(BaseModel):
    notification_id: int = Field(..., ge=1)
    user_id: int = Field(..., ge=1)
    channel: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)
    error_code: str | None = None


@router.post("/reminders/run", response_model=ReminderRunOut)
def post_run_reminders(
    _token: None = Depends(require_valid_internal_api_token),
) -> ReminderRunOut:
    try:
        with engine.begin() as conn:
            result = run_onboarding_reminders(conn)
        return ReminderRunOut(
            due_soon_sent=result.due_soon_sent,
            overdue_sent=result.overdue_sent,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.get("/notification-deliveries/pending")
def get_pending_deliveries(
    limit: int = 100,
    _token: None = Depends(require_valid_internal_api_token),
) -> dict[str, Any]:
    try:
        with engine.connect() as conn:
            items = list_pending_onboarding_deliveries(conn, limit=limit)
        return {"items": items}
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post("/notification-deliveries/ack")
def post_delivery_ack(
    body: DeliveryAckIn,
    _token: None = Depends(require_valid_internal_api_token),
) -> dict[str, str]:
    try:
        with engine.begin() as conn:
            ack_onboarding_delivery(
                conn,
                notification_id=body.notification_id,
                user_id=body.user_id,
                channel=body.channel,
                status=body.status,
                error_code=body.error_code,
            )
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)
