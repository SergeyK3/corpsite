# FILE: app/auth.py
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Depends, Security, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.db.engine import engine
from app.security.directory_scope import is_privileged
from app.security.auth_policy import (
    fetch_user_auth_policy_row,
    fetch_user_auth_policy_row_by_login,
    is_password_change_allowed_path,
    is_user_locked,
    record_login_failed,
    record_login_success,
    require_password_not_expired_or_change_allowed,
    validate_token_version_claim,
)


router = APIRouter(prefix="/auth", tags=["auth"])


# -----------------------
# Swagger / OpenAPI security
# -----------------------
# We need Swagger to ALWAYS attach Authorization header to secured endpoints.
# Using HTTPBearer(auto_error=False) makes the scheme optional in OpenAPI in many setups,
# so Swagger won't add the header. We make it required, but keep your 401 messages.
class JWTBearer(HTTPBearer):
    def __init__(self) -> None:
        # auto_error=True => OpenAPI marks it as security requirement (Swagger will inject header)
        super().__init__(auto_error=True)

    async def __call__(self, request: Request) -> HTTPAuthorizationCredentials:
        try:
            creds = await super().__call__(request)
        except HTTPException:
            # Normalize any "not authenticated" to your 401 wording
            raise HTTPException(status_code=401, detail="Missing Authorization: Bearer token")

        if not creds or (creds.scheme or "").lower() != "bearer" or not (creds.credentials or "").strip():
            raise HTTPException(status_code=401, detail="Missing Authorization: Bearer token")

        return creds


_bearer = JWTBearer()


# -----------------------
# Config
# -----------------------
def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _is_prod_env() -> bool:
    return _env("APP_ENV", "dev").lower() in {"prod", "production"}


AUTH_JWT_SECRET = _env("AUTH_JWT_SECRET", "dev-secret-change-me")


def _validate_auth_config() -> None:
    if _is_prod_env() and (
        not AUTH_JWT_SECRET or AUTH_JWT_SECRET == "dev-secret-change-me"
    ):
        raise RuntimeError(
            "AUTH_JWT_SECRET must be set to a non-default value when APP_ENV=prod"
        )


_validate_auth_config()

# Backward-compat:
# - Old config: AUTH_JWT_EXPIRES_MIN (minutes)
# - New preferred config: AUTH_JWT_EXPIRES_DAYS (days)
#
# If AUTH_JWT_EXPIRES_DAYS is set (or defaulted), we use it.
# If it's empty/invalid, we fall back to minutes.
def _jwt_ttl_seconds() -> int:
    days_raw = _env("AUTH_JWT_EXPIRES_DAYS", "10")  # default: 10 days (as requested)
    try:
        days = int(days_raw)
        if days > 0:
            return days * 24 * 60 * 60
    except Exception:
        pass

    # fallback to minutes (legacy)
    min_raw = _env("AUTH_JWT_EXPIRES_MIN", "720")  # legacy default 12h
    try:
        mins = int(min_raw)
        if mins > 0:
            return mins * 60
    except Exception:
        pass

    # last resort
    return 10 * 24 * 60 * 60


# -----------------------
# Password hashing (PBKDF2-HMAC-SHA256)
# Format: pbkdf2$<iters>$<salt_b64url>$<dk_b64url>
# -----------------------
def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * ((4 - (len(s) % 4)) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("utf-8"))


def hash_password(password: str, *, iters: int = 200_000) -> str:
    pwd = (password or "").encode("utf-8")
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", pwd, salt, iters, dklen=32)
    return f"pbkdf2${iters}${_b64url(salt)}${_b64url(dk)}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algo, it_s, salt_b64, dk_b64 = (password_hash or "").split("$", 3)
        if algo != "pbkdf2":
            return False
        iters = int(it_s)
        salt = _b64url_decode(salt_b64)
        dk_expected = _b64url_decode(dk_b64)
        dk = hashlib.pbkdf2_hmac(
            "sha256",
            (password or "").encode("utf-8"),
            salt,
            iters,
            dklen=len(dk_expected),
        )
        return hmac.compare_digest(dk, dk_expected)
    except Exception:
        return False


# -----------------------
# JWT (HS256) minimal implementation
# -----------------------
def _json_dumps(obj: Any) -> bytes:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _json_loads(data: bytes) -> Any:
    return json.loads(data.decode("utf-8"))


def _sign(message: bytes, secret: str) -> bytes:
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()


def create_access_token(user_id: int, *, token_version: Optional[int] = None) -> str:
    now = int(time.time())
    exp = now + _jwt_ttl_seconds()
    header = {"alg": "HS256", "typ": "JWT"}
    payload: Dict[str, Any] = {"sub": str(int(user_id)), "iat": now, "exp": exp}
    if token_version is not None:
        payload["token_version"] = int(token_version)

    header_b64 = _b64url(_json_dumps(header))
    payload_b64 = _b64url(_json_dumps(payload))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    sig_b64 = _b64url(_sign(signing_input, AUTH_JWT_SECRET))
    return f"{header_b64}.{payload_b64}.{sig_b64}"


def decode_and_verify_token(token: str) -> Dict[str, Any]:
    token = (token or "").strip()
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("invalid token")

    header_b64, payload_b64, sig_b64 = parts
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    expected_sig_b64 = _b64url(_sign(signing_input, AUTH_JWT_SECRET))
    if not hmac.compare_digest(expected_sig_b64, sig_b64):
        raise ValueError("bad signature")

    payload = _json_loads(_b64url_decode(payload_b64))
    exp = int(payload.get("exp") or 0)
    now = int(time.time())
    if exp <= 0 or now >= exp:
        raise ValueError("expired")

    return payload


def _telegram_bound_from_id(telegram_id: Any) -> bool:
    if telegram_id is None:
        return False
    return bool(str(telegram_id).strip())


def _normalize_telegram_username(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    policy_row = fetch_user_auth_policy_row(int(user_id))
    if not policy_row:
        return None

    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT
                    u.user_id,
                    u.role_id,
                    r.name AS role_name_ru,
                    u.unit_id,
                    u.is_active,
                    u.login,
                    u.telegram_id,
                    u.telegram_username
                FROM public.users u
                LEFT JOIN public.roles r
                    ON r.role_id = u.role_id
                WHERE u.user_id = :uid
                """
            ),
            {"uid": int(user_id)},
        ).mappings().first()

    if not row:
        return None

    return {
        "user_id": int(row["user_id"]),
        "role_id": int(row["role_id"]) if row["role_id"] is not None else None,
        "role_name_ru": str(row["role_name_ru"]) if row["role_name_ru"] is not None else None,
        "unit_id": int(row["unit_id"]) if row["unit_id"] is not None else None,
        "is_active": bool(row["is_active"]),
        "login": str(row["login"]) if row["login"] is not None else None,
        "telegram_bound": _telegram_bound_from_id(row.get("telegram_id")),
        "telegram_username": _normalize_telegram_username(row.get("telegram_username")),
        "must_change_password": bool(policy_row.get("must_change_password") or False),
        "token_version": int(policy_row.get("token_version") or 1),
        "locked_at": policy_row.get("locked_at"),
        "locked_reason": policy_row.get("locked_reason"),
    }


def _enrich_user_context(user: Dict[str, Any]) -> Dict[str, Any]:
    """Add backend-aligned privilege flags for UI (no enforcement)."""
    from app.security.admin_guard import evaluate_admin_access
    from app.security.admin_permissions import (
        has_any_personnel_read_permission,
        has_hr_governance_permission,
    )

    out = dict(user)
    out["is_privileged"] = is_privileged(out)
    out["is_system_admin"] = int(out.get("role_id") or 0) == 2
    uid = int(out.get("user_id") or 0)
    full_admin = evaluate_admin_access(out)
    out["has_personnel_admin"] = full_admin or has_any_personnel_read_permission(uid)
    out["has_hr_governance"] = full_admin or has_hr_governance_permission(uid)

    from app.services.personnel_visibility_resolver_service import (
        enrich_user_with_personnel_visibility,
    )

    return enrich_user_with_personnel_visibility(out)


def _get_user_auth_row_by_login(login: str) -> Optional[Dict[str, Any]]:
    row = fetch_user_auth_policy_row_by_login(login)
    if not row:
        return None
    return {
        "user_id": int(row["user_id"]),
        "role_id": int(row["role_id"]) if row.get("role_id") is not None else None,
        "unit_id": int(row["unit_id"]) if row.get("unit_id") is not None else None,
        "is_active": bool(row.get("is_active")),
        "login": str(row["login"]) if row.get("login") is not None else None,
        "password_hash": str(row.get("password_hash") or ""),
        "locked_at": row.get("locked_at"),
        "locked_until": row.get("locked_until"),
        "locked_reason": row.get("locked_reason"),
        "failed_login_count": int(row.get("failed_login_count") or 0),
        "token_version": int(row.get("token_version") or 1),
        "must_change_password": bool(row.get("must_change_password") or False),
    }


# -----------------------
# Dependencies (for other routers)
# -----------------------
def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials = Security(_bearer),
) -> Dict[str, Any]:
    token = (creds.credentials or "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing Authorization: Bearer token")

    try:
        payload = decode_and_verify_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    sub = (payload.get("sub") or "").strip()
    try:
        user_id = int(sub)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token subject")

    u = _get_user_by_id(user_id)
    if not u:
        raise HTTPException(status_code=401, detail="User not found")
    if not u["is_active"]:
        raise HTTPException(status_code=403, detail="Пользователь неактивен")
    if is_user_locked(u):
        raise HTTPException(status_code=403, detail="Account locked.")

    validate_token_version_claim(payload, u)
    require_password_not_expired_or_change_allowed(request, u)

    return _enrich_user_context(u)


def get_current_user_id(user: Dict[str, Any] = Depends(get_current_user)) -> int:
    return int(user["user_id"])


# -----------------------
# API models
# -----------------------
class LoginRequest(BaseModel):
    login: str = Field(..., min_length=1, max_length=200)
    password: str = Field(..., min_length=1, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=200)
    new_password: str = Field(..., min_length=8, max_length=200)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request) -> TokenResponse:
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    login_value = (payload.login or "").strip()

    u = _get_user_auth_row_by_login(login_value)
    if not u:
        record_login_failed(
            user_id=None,
            login=login_value,
            ip_address=ip_address,
            user_agent=user_agent,
            failure_reason="unknown_login",
        )
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")

    if not u["is_active"]:
        record_login_failed(
            user_id=int(u["user_id"]),
            login=login_value,
            ip_address=ip_address,
            user_agent=user_agent,
            failure_reason="inactive_user",
        )
        raise HTTPException(status_code=403, detail="Пользователь неактивен")

    if is_user_locked(u):
        record_login_failed(
            user_id=int(u["user_id"]),
            login=login_value,
            ip_address=ip_address,
            user_agent=user_agent,
            failure_reason="account_locked",
        )
        raise HTTPException(status_code=403, detail="Account locked.")

    ph = (u.get("password_hash") or "").strip()
    if not ph:
        record_login_failed(
            user_id=int(u["user_id"]),
            login=login_value,
            ip_address=ip_address,
            user_agent=user_agent,
            failure_reason="password_not_set",
        )
        raise HTTPException(status_code=403, detail="Пароль для пользователя не задан")

    if not verify_password(payload.password, ph):
        record_login_failed(
            user_id=int(u["user_id"]),
            login=login_value,
            ip_address=ip_address,
            user_agent=user_agent,
            failure_reason="invalid_credentials",
        )
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")

    record_login_success(
        user_id=int(u["user_id"]),
        ip_address=ip_address,
        user_agent=user_agent,
    )
    token = create_access_token(int(u["user_id"]), token_version=int(u.get("token_version") or 1))
    return TokenResponse(access_token=token, token_type="bearer")


@router.post("/password-change")
def password_change(_payload: PasswordChangeRequest) -> Dict[str, Any]:
    """Stub for future self-service password change (Phase C1/C2)."""
    raise HTTPException(
        status_code=501,
        detail="Password change endpoint is not implemented yet.",
    )


@router.get("/me")
def me(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return user