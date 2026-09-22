# app/tg_bind.py
from __future__ import annotations

import hashlib
import os
import secrets
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.engine import engine
from app.errors import raise_error, ErrorCode
from app.security.directory_scope import require_uid

router = APIRouter(tags=["tg-bind"])

# ---- config ----
BOT_BIND_TOKEN = (os.getenv("BOT_BIND_TOKEN") or "").strip()
DEFAULT_TTL_MINUTES = int(os.getenv("TG_BIND_CODE_TTL_MINUTES", "30"))

# We do NOT fail import-time. Config error is reported on consume.
# This is useful for dev-mode.
# if not BOT_BIND_TOKEN: pass


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_code(code: str) -> str:
    return str(code or "").strip().lower()


def _hash_code(code: str) -> str:
    return hashlib.sha256(_normalize_code(code).encode("utf-8")).hexdigest()


def _gen_code() -> str:
    """
    Human-readable, case-insensitive 8-character code for phone input.
    """
    alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
    return "".join(secrets.choice(alphabet) for _ in range(8))


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


def _require_request_user_id(
    *,
    authorization: str | None,
    x_user_id: int | None,
    x_internal_api_token: str | None,
) -> int:
    try:
        return require_uid(
            authorization=authorization,
            x_user_id=str(int(x_user_id)) if x_user_id is not None else None,
            x_internal_api_token=x_internal_api_token,
        )
    except HTTPException:
        raise_error(ErrorCode.TGBIND_FORBIDDEN_NOT_AUTH)



# ---- DB helpers ----
# IMPORTANT: users.telegram_id is treated as TEXT in DB.
# Therefore:
# - bind uses TEXT
# - comparisons use TEXT
# - we never compare TEXT to INT


def resolve_user_id_by_telegram_id(tg_user_id: int) -> Optional[int]:
    """Public helper: map Telegram user id → corpsite user_id via users.telegram_id."""
    return _get_user_id_by_telegram_id(tg_user_id)


def unbind_user_telegram(*, user_id: int, actor_user_id: Optional[int] = None) -> dict[str, Any]:
    """
    Clear users.telegram_id / telegram_username for user_id.
    Does not modify employee_id. Idempotent when already unbound.
    """
    uid = int(user_id)
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT user_id, employee_id, telegram_id, telegram_username
                FROM public.users
                WHERE user_id = :uid
                LIMIT 1
                """
            ),
            {"uid": uid},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="user not found")

        employee_id = row.get("employee_id")
        existing_tg = row.get("telegram_id")
        had_binding = existing_tg is not None and bool(str(existing_tg).strip())

        if had_binding:
            conn.execute(
                text(
                    """
                    UPDATE public.users
                    SET telegram_id = NULL,
                        telegram_username = NULL
                    WHERE user_id = :uid
                    """
                ),
                {"uid": uid},
            )

    applied = bool(had_binding)
    if applied:
        try:
            from app.services.security_audit_service import write_security_event

            write_security_event(
                event_type="ACCESS_CHANGED",
                actor_user_id=int(actor_user_id) if actor_user_id is not None else uid,
                target_user_id=uid,
                target_employee_id=int(employee_id) if employee_id is not None else None,
                success=True,
                metadata={
                    "source": "telegram_unbind",
                    "telegram_id": str(existing_tg).strip() if existing_tg is not None else None,
                    "employee_id_preserved": int(employee_id) if employee_id is not None else None,
                },
            )
        except Exception:
            pass

    return {
        "user_id": uid,
        "applied": applied,
        "telegram_bound": False,
        "employee_id": int(employee_id) if employee_id is not None else None,
    }


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


def _bind_user_to_telegram(
    *,
    user_id: int,
    tg_user_id: int,
    telegram_username: Optional[str] = None,
    conn: Any | None = None,
) -> None:
    """
    Sets users.telegram_id (TEXT), telegram_username and telegram_bound_at for user_id.

    When ``conn`` is provided, the binding participates in the caller's
    transaction.  This is used by bind-code consumption so the code cannot be
    marked used unless the User binding is committed as well.

    Conflicts:
      - if tg_user_id already bound to another user_id -> 409
      - if user_id already has another telegram_id -> 409

    Idempotency:
      - if already bound to this tg_user_id -> OK (no-op)
    """
    uid = int(user_id)
    tg_text = str(int(tg_user_id))  # ALWAYS TEXT

    with (nullcontext(conn) if conn is not None else engine.begin()) as conn:
        # 1) Is this tg already used by another user?
        row = conn.execute(
            text("SELECT user_id FROM users WHERE telegram_id = :tg LIMIT 1 FOR UPDATE"),
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
            text("SELECT telegram_id FROM users WHERE user_id = :uid FOR UPDATE"),
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
                text(
                    "UPDATE users SET telegram_id = :tg, telegram_username = :telegram_username, "
                    "telegram_bound_at = now() WHERE user_id = :uid"
                ),
                {"tg": tg_text, "telegram_username": telegram_username, "uid": uid},
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
    telegram_username: Optional[str] = Field(default=None, max_length=256)


class ConsumeBindCodeOut(BaseModel):
    user_id: int


class SelfBindOut(BaseModel):
    user_id: int


# ---- endpoints ----
@router.post("/me/tg-bind-code", response_model=TgBindCodeOut)
def create_bind_code(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_user_id: int | None = Header(default=None, alias="X-User-Id"),
    x_internal_api_token: str | None = Header(default=None, alias="X-Internal-Api-Token"),
) -> TgBindCodeOut:
    """
    MVP without LK:
    issues a one-time code for current user identified by JWT
    or by X-User-Id only in development / compatibility mode.
    """
    user_id = _require_request_user_id(
        authorization=authorization,
        x_user_id=x_user_id,
        x_internal_api_token=x_internal_api_token,
    )

    code = _gen_code()
    code_hash = _hash_code(code)
    expires_at = _now_utc() + timedelta(minutes=DEFAULT_TTL_MINUTES)

    with engine.begin() as conn:
        # Serialize issuance per User across backend processes.  Without this,
        # two concurrent requests that both see no active row could leave two
        # valid codes (or race on the partial unique index).
        conn.execute(
            text("SELECT pg_advisory_xact_lock(:user_id)"),
            {"user_id": int(user_id)},
        )
        conn.execute(
            text(
                "UPDATE public.telegram_bind_codes "
                "SET invalidated_at = now() "
                "WHERE user_id = :user_id AND used_at IS NULL AND invalidated_at IS NULL"
            ),
            {"user_id": int(user_id)},
        )
        conn.execute(
            text(
                "INSERT INTO public.telegram_bind_codes "
                "(user_id, code_hash, created_at, expires_at) "
                "VALUES (:user_id, :code_hash, now(), :expires_at)"
            ),
            {
                "user_id": int(user_id),
                "code_hash": code_hash,
                "expires_at": expires_at,
            },
        )

    return TgBindCodeOut(code=code, expires_at=expires_at)


@router.post("/tg/bind/consume", response_model=ConsumeBindCodeOut)
def consume_bind_code(
    payload: ConsumeBindCodeIn,
    # IMPORTANT: header name used by clients/bot is X-Bot-Bind-Token
    x_bot_token: str | None = Header(default=None, alias="X-Bot-Bind-Token"),
) -> ConsumeBindCodeOut:
    """
    Bot-only endpoint.
    1) Validate X-Bot-Token
    2) Validate code
    3) Persist users.telegram_id binding (source of truth)
    """
    _require_bot_token(x_bot_token)

    code_hash = _hash_code(payload.code)
    now = _now_utc()
    with engine.begin() as conn:
        rec = conn.execute(
            text(
                "SELECT bind_code_id, user_id, expires_at, used_at, invalidated_at "
                "FROM public.telegram_bind_codes WHERE code_hash = :code_hash FOR UPDATE"
            ),
            {"code_hash": code_hash},
        ).mappings().one_or_none()

        # Do not disclose details: same 409 for missing, expired, invalidated or used.
        if (
            rec is None
            or rec["used_at"] is not None
            or rec["invalidated_at"] is not None
            or rec["expires_at"] <= now
        ):
            raise_error(ErrorCode.TGBIND_CONFLICT_CODE_INVALID)

        username = (payload.telegram_username or "").strip() or None
        _bind_user_to_telegram(
            user_id=int(rec["user_id"]),
            tg_user_id=int(payload.tg_user_id),
            telegram_username=username,
            conn=conn,
        )
        conn.execute(
            text(
                "UPDATE public.telegram_bind_codes SET used_at = :used_at "
                "WHERE bind_code_id = :bind_code_id AND used_at IS NULL AND invalidated_at IS NULL"
            ),
            {"used_at": now, "bind_code_id": int(rec["bind_code_id"])},
        )

    return ConsumeBindCodeOut(user_id=int(rec["user_id"]))


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
