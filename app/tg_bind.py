# app/tg_bind.py
from __future__ import annotations

import hashlib
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Any

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.engine import engine
from app.errors import raise_error, ErrorCode

router = APIRouter(tags=["tg-bind"])

# ---- config ----
BOT_BIND_TOKEN = (os.getenv("BOT_BIND_TOKEN") or "").strip()
DEFAULT_TTL_MINUTES = int(os.getenv("TG_BIND_CODE_TTL_MINUTES", "30"))

# We do NOT fail import-time. Config error is reported on consume.
# This is useful for dev-mode.
# if not BOT_BIND_TOKEN: pass


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _gen_code() -> str:
    """
    Human-readable code: 8 chars + dash + 4 chars.
    Sufficient for MVP.
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


def _conflict_detail(
    *,
    code: str,
    message: str,
    reason: str,
    hint: str,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Produce the same "stable UX error contract" shape as app/errors.py,
    but without depending on missing ErrorCode enum values.
    """
    data: Dict[str, Any] = {
        "error": "conflict",
        "message": message,
        "reason": reason,
        "hint": hint,
        "code": code,
    }
    if extra:
        data.update(extra)
    return data


def _require_bot_token(x_bot_token: str | None) -> None:
    # server configuration error (not 403/409)
    if not BOT_BIND_TOKEN:
        raise HTTPException(status_code=500, detail="BOT_BIND_TOKEN is not configured on backend")

    # forbidden (403) by error contract
    if not x_bot_token or x_bot_token.strip() != BOT_BIND_TOKEN:
        raise_error(ErrorCode.TGBIND_FORBIDDEN_CONSUME)


def _require_user_id(x_user_id: int | None) -> int:
    # forbidden (403) by error contract
    if x_user_id is None or x_user_id <= 0:
        raise_error(ErrorCode.TGBIND_FORBIDDEN_NOT_AUTH)
    return int(x_user_id)


def _has_active_code_for_user(user_id: int) -> bool:
    now = _now_utc()
    for rec in _CODES.values():
        if rec.user_id == int(user_id) and rec.used_at is None and rec.expires_at > now:
            return True
    return False


def _gc_expired_codes() -> None:
    now = _now_utc()
    dead = [h for h, rec in _CODES.items() if rec.expires_at <= now or rec.used_at is not None]
    for h in dead:
        _CODES.pop(h, None)


# ---- DB helpers ----
# IMPORTANT: users.telegram_id is treated as TEXT in DB.
# Therefore:
# - bind uses TEXT
# - comparisons use TEXT
# - we never compare TEXT to INT


def _get_user_id_by_telegram_id(tg_user_id: int) -> Optional[int]:
    sql = "SELECT user_id FROM users WHERE telegram_id = :tg LIMIT 1"
    tg_text = str(int(tg_user_id))  # ALWAYS TEXT
    with engine.begin() as conn:
        row = conn.execute(text(sql), {"tg": tg_text}).fetchone()
    if not row:
        return None
    return int(row[0])


def _get_telegram_id_by_user_id(user_id: int) -> Optional[int]:
    sql = "SELECT telegram_id FROM users WHERE user_id = :uid"
    with engine.begin() as conn:
        row = conn.execute(text(sql), {"uid": int(user_id)}).fetchone()
    if not row:
        return None
    v = row[0]
    if v is None:
        return None
    # telegram_id stored as TEXT; convert to int only if numeric
    try:
        return int(str(v).strip())
    except Exception:
        return None


def _bind_user_to_telegram(*, user_id: int, tg_user_id: int) -> None:
    """
    Sets users.telegram_id = tg_user_id (TEXT) for user_id.

    Conflicts:
      - if tg_user_id already bound to another user_id -> 409
      - if user_id already has another telegram_id -> 409

    Idempotency:
      - if already bound to this tg_user_id -> OK (no-op)
    """
    uid = int(user_id)
    tg_text = str(int(tg_user_id))  # ALWAYS TEXT

    with engine.begin() as conn:
        # 1) Is this tg already used by another user?
        row = conn.execute(
            text("SELECT user_id FROM users WHERE telegram_id = :tg LIMIT 1"),
            {"tg": tg_text},
        ).fetchone()
        if row and int(row[0]) != uid:
            # Keep the same contract shape; no dependency on missing ErrorCode enum
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=_conflict_detail(
                    code="TGBIND_CONFLICT_TG_ALREADY_BOUND",
                    message="Невозможно выполнить привязку",
                    reason="Этот Telegram уже привязан к другому пользователю",
                    hint="Обратитесь к администратору для смены привязки",
                    extra={"tg_user_id": int(tg_user_id)},
                ),
            )

        # 2) Does user already have another telegram_id?
        row2 = conn.execute(
            text("SELECT telegram_id FROM users WHERE user_id = :uid"),
            {"uid": uid},
        ).fetchone()
        if not row2:
            raise HTTPException(status_code=404, detail="user not found")

        existing_tg = row2[0]
        if existing_tg is not None:
            existing_text = str(existing_tg).strip()
            if existing_text and existing_text != tg_text:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=_conflict_detail(
                        code="TGBIND_CONFLICT_USER_ALREADY_BOUND",
                        message="Невозможно выполнить привязку",
                        reason="Пользователь уже привязан к другому Telegram",
                        hint="Обратитесь к администратору для смены привязки",
                        extra={"user_id": uid, "telegram_id": existing_text},
                    ),
                )

        # 3) Set (if NULL/empty or already same)
        try:
            conn.execute(
                text("UPDATE users SET telegram_id = :tg WHERE user_id = :uid"),
                {"tg": tg_text, "uid": uid},
            )
        except IntegrityError:
            # In case unique constraint triggers unexpectedly
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=_conflict_detail(
                    code="TGBIND_CONFLICT_TG_ALREADY_BOUND",
                    message="Невозможно выполнить привязку",
                    reason="Этот Telegram уже привязан к другому пользователю",
                    hint="Обратитесь к администратору для смены привязки",
                    extra={"tg_user_id": int(tg_user_id)},
                ),
            )


# ---- schemas ----
class TgBindCodeOut(BaseModel):
    code: str
    expires_at: datetime


class ConsumeBindCodeIn(BaseModel):
    code: str = Field(min_length=3, max_length=64)
    tg_user_id: int = Field(gt=0)


class ConsumeBindCodeOut(BaseModel):
    user_id: int


class SelfBindOut(BaseModel):
    user_id: int


# ---- endpoints ----
@router.post("/me/tg-bind-code", response_model=TgBindCodeOut)
def create_bind_code(x_user_id: int | None = Header(default=None, alias="X-User-Id")) -> TgBindCodeOut:
    """
    MVP without LK:
    issues a one-time code for current user identified via X-User-Id.
    """
    _gc_expired_codes()

    user_id = _require_user_id(x_user_id)

    # if active code exists — 409 (contract)
    if _has_active_code_for_user(user_id):
        raise_error(ErrorCode.TGBIND_CONFLICT_CODE_EXISTS, extra={"user_id": int(user_id)})

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
    Bot-only endpoint.
    1) Validate X-Bot-Token
    2) Validate code
    3) Persist users.telegram_id binding (source of truth)
    """
    _require_bot_token(x_bot_token)

    _gc_expired_codes()

    code_hash = _hash_code(payload.code.strip().upper())
    rec = _CODES.get(code_hash)

    now = _now_utc()

    # Do not disclose details: same 409 for missing/expired/used.
    if rec is None:
        raise_error(ErrorCode.TGBIND_CONFLICT_CODE_INVALID)

    if rec.used_at is not None:
        raise_error(ErrorCode.TGBIND_CONFLICT_CODE_INVALID)

    if rec.expires_at <= now:
        _CODES.pop(code_hash, None)
        raise_error(ErrorCode.TGBIND_CONFLICT_CODE_INVALID)

    # Persist binding in DB (atomic in helper transaction)
    _bind_user_to_telegram(user_id=int(rec.user_id), tg_user_id=int(payload.tg_user_id))

    # Mark code as used after successful DB write
    rec.used_at = now
    rec.used_by_tg_user_id = int(payload.tg_user_id)

    return ConsumeBindCodeOut(user_id=int(rec.user_id))


@router.post("/auth/self-bind", response_model=SelfBindOut)
def auth_self_bind(
    x_telegram_user_id: int | None = Header(default=None, alias="X-Telegram-User-Id"),
    x_telegram_username: str | None = Header(default=None, alias="X-Telegram-Username"),
) -> SelfBindOut:
    """
    Binding check (backend-only; users table is source of truth).

    Behavior:
      - if tg_user_id found in users.telegram_id -> 200 {user_id}
      - if not -> 404 not bound
    """
    if x_telegram_user_id is None or int(x_telegram_user_id) <= 0:
        raise HTTPException(status_code=400, detail="X-Telegram-User-Id is required and must be > 0")

    _ = (x_telegram_username or "").strip()  # accepted but not used yet

    user_id = _get_user_id_by_telegram_id(int(x_telegram_user_id))
    if user_id is None:
        raise HTTPException(status_code=404, detail="not bound")

    return SelfBindOut(user_id=int(user_id))
