"""One-time password recovery mediated by a confirmed Telegram binding."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from sqlalchemy import text

from app.db.engine import engine
from app.services.security_audit_service import write_security_event

_GENERIC_MESSAGE = "Если для этой учётной записи доступно восстановление, код отправлен в Telegram."


def generic_request_message() -> Dict[str, str]:
    return {"message": _GENERIC_MESSAGE}


def _code_hash(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _valid_code(code: str) -> bool:
    return len(code) == 8 and code.isascii() and code.isdigit()


def request_recovery(login: str) -> Dict[str, str]:
    """Queue a delivery without revealing whether a User or Telegram binding exists."""
    normalized = (login or "").strip().lower()
    if not normalized:
        return generic_request_message()
    with engine.begin() as conn:
        user = conn.execute(text("""
            SELECT user_id, telegram_id FROM public.users
            WHERE lower(login)=:login AND is_active IS TRUE
              AND NULLIF(btrim(COALESCE(telegram_id::text, '')), '') IS NOT NULL
            LIMIT 1 FOR UPDATE
        """), {"login": normalized}).mappings().one_or_none()
        if user is None:
            return generic_request_message()
        recent = conn.execute(text("""
            SELECT 1 FROM public.telegram_password_recovery_requests
            WHERE user_id=:user_id AND requested_at > now() - interval '1 minute'
            LIMIT 1
        """), {"user_id": int(user["user_id"])}).first()
        if recent is not None:
            return generic_request_message()
        conn.execute(text("""
            UPDATE public.telegram_password_recovery_requests
            SET status='CANCELLED'
            WHERE user_id=:user_id AND status IN ('PENDING','CLAIMED','ISSUED')
        """), {"user_id": int(user["user_id"])})
        conn.execute(text("""
            INSERT INTO public.telegram_password_recovery_requests
              (request_id, user_id, telegram_user_id, status)
            VALUES (:request_id, :user_id, :telegram_user_id, 'PENDING')
        """), {"request_id": str(uuid4()), "user_id": int(user["user_id"]), "telegram_user_id": str(user["telegram_id"]).strip()})
        write_security_event(
            event_type="PASSWORD_RESET_REQUESTED", actor_user_id=None,
            target_user_id=int(user["user_id"]), metadata={"channel": "telegram"}, conn=conn,
        )
    return generic_request_message()


def claim_pending_delivery() -> Optional[Dict[str, Any]]:
    """Atomically lease one delivery to the trusted bot; no code exists yet."""
    with engine.begin() as conn:
        row = conn.execute(text("""
            WITH candidate AS (
              SELECT request_id FROM public.telegram_password_recovery_requests
              WHERE status='PENDING' OR (status='CLAIMED' AND claim_until < now())
              ORDER BY requested_at ASC
              FOR UPDATE SKIP LOCKED LIMIT 1
            )
            UPDATE public.telegram_password_recovery_requests r
            SET status='CLAIMED', claim_until=now() + interval '2 minutes'
            FROM candidate WHERE r.request_id=candidate.request_id
            RETURNING r.request_id, r.telegram_user_id
        """)).mappings().one_or_none()
    return dict(row) if row else None


def record_bot_delivery(request_id: str, code: str) -> bool:
    """Persist only the hash after the bot has sent the plaintext code."""
    if not _valid_code(code):
        return False
    with engine.begin() as conn:
        row = conn.execute(text("""
            UPDATE public.telegram_password_recovery_requests
            SET status='ISSUED', code_hash=:code_hash, issued_at=now(),
                expires_at=now() + interval '15 minutes', claim_until=NULL
            WHERE request_id=:request_id AND status='CLAIMED' AND claim_until >= now()
            RETURNING user_id
        """), {"request_id": str(request_id), "code_hash": _code_hash(code)}).mappings().one_or_none()
        if row is None:
            return False
        write_security_event(
            event_type="PASSWORD_RESET_REQUESTED", actor_user_id=None,
            target_user_id=int(row["user_id"]), metadata={"channel": "telegram", "delivery": "sent"}, conn=conn,
        )
    return True


def complete_recovery(*, login: str, code: str, new_password: str, confirmation: str) -> Dict[str, str]:
    # Lazy import avoids the auth router ↔ recovery service import cycle.
    from app.auth import hash_password
    normalized = (login or "").strip().lower()
    if not 8 <= len(new_password or "") <= 200:
        raise ValueError("PASSWORD_POLICY_FAILED")
    if new_password != confirmation:
        raise ValueError("PASSWORD_CONFIRMATION_MISMATCH")
    if not _valid_code(code):
        raise ValueError("CODE_INVALID")
    with engine.begin() as conn:
        request = conn.execute(text("""
            SELECT r.request_id, r.user_id, r.code_hash, r.attempt_count, r.expires_at,
                   u.password_hash, u.locked_reason
            FROM public.telegram_password_recovery_requests r
            JOIN public.users u ON u.user_id=r.user_id
            WHERE lower(u.login)=:login AND r.status='ISSUED' AND u.is_active IS TRUE
            ORDER BY r.issued_at DESC NULLS LAST
            LIMIT 1 FOR UPDATE OF r, u
        """), {"login": normalized}).mappings().one_or_none()
        if request is None:
            raise ValueError("CODE_INVALID")
        expired = request["expires_at"] is None or request["expires_at"] <= datetime.now(timezone.utc)
        valid = not expired and hmac.compare_digest(str(request["code_hash"] or ""), _code_hash(code))
        if not valid:
            attempts = int(request["attempt_count"] or 0) + 1
            status = "LOCKED" if attempts >= 5 else ("EXPIRED" if expired else "ISSUED")
            conn.execute(text("""
                UPDATE public.telegram_password_recovery_requests
                SET attempt_count=:attempts, status=:status
                WHERE request_id=:request_id
            """), {"attempts": attempts, "status": status, "request_id": str(request["request_id"])})
            raise ValueError("CODE_EXPIRED" if expired else "CODE_INVALID")
        brute_force = str(request["locked_reason"] or "") == "brute_force"
        conn.execute(text("""
            UPDATE public.users SET password_hash=:password_hash, password_changed_at=now(),
              must_change_password=FALSE, temp_password_expires_at=NULL,
              token_version=COALESCE(token_version,1)+1,
              locked_at=CASE WHEN :brute_force THEN NULL ELSE locked_at END,
              locked_until=CASE WHEN :brute_force THEN NULL ELSE locked_until END,
              locked_reason=CASE WHEN :brute_force THEN NULL ELSE locked_reason END,
              failed_login_count=CASE WHEN :brute_force THEN 0 ELSE failed_login_count END,
              last_failed_login_at=CASE WHEN :brute_force THEN NULL ELSE last_failed_login_at END
            WHERE user_id=:user_id
        """), {"password_hash": hash_password(new_password), "brute_force": brute_force, "user_id": int(request["user_id"])})
        conn.execute(text("""
            UPDATE public.telegram_password_recovery_requests
            SET status='USED', used_at=now() WHERE request_id=:request_id
        """), {"request_id": str(request["request_id"])})
        write_security_event(
            event_type="PASSWORD_RESET_COMPLETED", actor_user_id=int(request["user_id"]),
            target_user_id=int(request["user_id"]), metadata={"channel": "telegram", "brute_force_lock_cleared": brute_force}, conn=conn,
        )
    return {"message": "Пароль изменён. Выполните вход с новым паролем."}
