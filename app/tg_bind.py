# app/tg_bind.py
from __future__ import annotations

import hashlib
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field


router = APIRouter(tags=["tg-bind"])

# ---- config ----
BOT_BIND_TOKEN = (os.getenv("BOT_BIND_TOKEN") or "").strip()
DEFAULT_TTL_MINUTES = int(os.getenv("TG_BIND_CODE_TTL_MINUTES", "30"))

if not BOT_BIND_TOKEN:
    # Не падаем при импорте, чтобы не ломать dev,
    # но endpoint /tg/bind/consume будет отдавать 401 всегда.
    pass


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _gen_code() -> str:
    """
    Человекочитаемый код: 8 символов + дефис + 4 символа (примерно).
    Не крипто-идеален, но достаточно для MVP.
    """
    a = secrets.token_hex(4)  # 8 hex chars
    b = secrets.token_hex(2)  # 4 hex chars
    return f"{a}-{b}".upper()


@dataclass
class _BindCodeRecord:
    user_id: int
    expires_at: datetime
    used_at: Optional[datetime] = None
    used_by_tg_user_id: Optional[int] = None


# in-memory store: code_hash -> record
_CODES: Dict[str, _BindCodeRecord] = {}


def _require_bot_token(x_bot_token: str | None) -> None:
    if not BOT_BIND_TOKEN:
        raise HTTPException(status_code=401, detail="BOT_BIND_TOKEN is not configured on backend")
    if not x_bot_token or x_bot_token.strip() != BOT_BIND_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _require_user_id(x_user_id: int | None) -> int:
    if x_user_id is None or x_user_id <= 0:
        raise HTTPException(status_code=401, detail="X-User-Id header is required")
    return int(x_user_id)


# ---- schemas ----
class TgBindCodeOut(BaseModel):
    code: str
    expires_at: datetime


class ConsumeBindCodeIn(BaseModel):
    code: str = Field(min_length=3, max_length=64)
    tg_user_id: int = Field(gt=0)


class ConsumeBindCodeOut(BaseModel):
    user_id: int


# ---- endpoints ----
@router.post("/me/tg-bind-code", response_model=TgBindCodeOut)
def create_bind_code(x_user_id: int | None = Header(default=None, alias="X-User-Id")) -> TgBindCodeOut:
    """
    MVP для тестирования без ЛК:
    выдаёт одноразовый код для текущего пользователя, определяемого через X-User-Id.
    """
    user_id = _require_user_id(x_user_id)

    code = _gen_code()
    code_hash = _hash_code(code)

    expires_at = _now_utc() + timedelta(minutes=DEFAULT_TTL_MINUTES)
    _CODES[code_hash] = _BindCodeRecord(user_id=user_id, expires_at=expires_at)

    return TgBindCodeOut(code=code, expires_at=expires_at)


@router.post("/tg/bind/consume", response_model=ConsumeBindCodeOut)
def consume_bind_code(
    payload: ConsumeBindCodeIn,
    x_bot_token: str | None = Header(default=None, alias="X-Bot-Token"),
) -> ConsumeBindCodeOut:
    """
    Endpoint, который должен вызывать только бот.
    """
    _require_bot_token(x_bot_token)

    code_hash = _hash_code(payload.code.strip().upper())
    rec = _CODES.get(code_hash)

    # Ничего не раскрываем наружу: "не найдено" одинаково для отсутствующих/просроченных/использованных.
    if rec is None:
        raise HTTPException(status_code=404, detail="Code not found")

    now = _now_utc()
    if rec.used_at is not None:
        raise HTTPException(status_code=404, detail="Code not found")
    if rec.expires_at <= now:
        # можно удалить, чтобы не копить
        _CODES.pop(code_hash, None)
        raise HTTPException(status_code=404, detail="Code not found")

    # mark used
    rec.used_at = now
    rec.used_by_tg_user_id = int(payload.tg_user_id)

    return ConsumeBindCodeOut(user_id=rec.user_id)
