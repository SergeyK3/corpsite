"""OPS-026.2 — Telegram health API schemas."""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

TelegramHealthStatus = Literal["GREEN", "YELLOW", "RED"]


class TelegramHealthQueueResponse(BaseModel):
    pending_count: int = 0
    sent_24h: int = 0
    failed_24h: int = 0
    oldest_pending_at: Optional[str] = None
    oldest_pending_age_sec: Optional[float] = None


class TelegramHealthDeliveryResponse(BaseModel):
    last_sent_at: Optional[str] = None
    last_failed_at: Optional[str] = None
    last_error_code: Optional[str] = None
    last_error_text: Optional[str] = None


class TelegramHealthBindingsResponse(BaseModel):
    active_users: int = 0
    users_with_telegram: int = 0
    coverage_percent: float = 0.0


class TelegramHealthBotConfigurationResponse(BaseModel):
    bot_token_present: bool = False
    internal_api_token_present: bool = False
    bot_bind_token_present: bool = False
    api_base_url: Optional[str] = None
    events_delivery_channel: str = "telegram"
    events_internal_api_user_id: Optional[str] = None
    telegram_delivery_allowlist_configured: bool = False


class TelegramHealthErrorSummaryResponse(BaseModel):
    error_code: Optional[str] = None
    occurred_at: Optional[str] = None
    message: Optional[str] = None


class TelegramHealthUnavailableMetricResponse(BaseModel):
    metric: str
    reason: str


class TelegramHealthResponse(BaseModel):
    checked_at: str
    channel: str
    window_hours: int = 24
    status: TelegramHealthStatus
    status_reasons: List[str] = Field(default_factory=list)
    queue: TelegramHealthQueueResponse
    delivery: TelegramHealthDeliveryResponse
    bindings: TelegramHealthBindingsResponse
    bot_configuration: TelegramHealthBotConfigurationResponse
    error_summary: Optional[TelegramHealthErrorSummaryResponse] = None
    unavailable_metrics: List[TelegramHealthUnavailableMetricResponse] = Field(default_factory=list)
