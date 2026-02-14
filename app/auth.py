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


AUTH_JWT_SECRET = _env("AUTH_JWT_SECRET", "dev-secret-change-me")
AUTH_JWT_EXPIRES_MIN = int(_env("AUTH_JWT_EXPIRES_MIN", "720"))  # 12h


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


def create_access_token(user_id: int) -> str:
    now = int(time.time())
    exp = now + AUTH_JWT_EXPIRES_MIN * 60
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": str(int(user_id)), "iat": now, "exp": exp}

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


def _get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT user_id, role_id, unit_id, is_active, login
                FROM public.users
                WHERE user_id = :uid
                """
            ),
            {"uid": int(user_id)},
        ).fetchone()
    if not row:
        return None
    return {
        "user_id": int(row[0]),
        "role_id": int(row[1]) if row[1] is not None else None,
        "unit_id": int(row[2]) if row[2] is not None else None,
        "is_active": bool(row[3]),
        "login": str(row[4]) if row[4] is not None else None,
    }


def _get_user_auth_row_by_login(login: str) -> Optional[Dict[str, Any]]:
    l = (login or "").strip().lower()
    if not l:
        return None
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT user_id, role_id, unit_id, is_active, login, password_hash
                FROM public.users
                WHERE lower(login) = :login
                LIMIT 1
                """
            ),
            {"login": l},
        ).fetchone()
    if not row:
        return None
    return {
        "user_id": int(row[0]),
        "role_id": int(row[1]) if row[1] is not None else None,
        "unit_id": int(row[2]) if row[2] is not None else None,
        "is_active": bool(row[3]),
        "login": str(row[4]) if row[4] is not None else None,
        "password_hash": str(row[5]) if row[5] is not None else "",
    }


# -----------------------
# Dependencies (for other routers)
# -----------------------
def get_current_user(
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

    return u


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


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    u = _get_user_auth_row_by_login(payload.login)
    if not u:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")

    if not u["is_active"]:
        raise HTTPException(status_code=403, detail="Пользователь неактивен")

    ph = (u.get("password_hash") or "").strip()
    if not ph:
        raise HTTPException(status_code=403, detail="Пароль для пользователя не задан")

    if not verify_password(payload.password, ph):
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")

    token = create_access_token(int(u["user_id"]))
    return TokenResponse(access_token=token, token_type="bearer")


@router.get("/me")
def me(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return user
