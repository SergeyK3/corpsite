"""Encrypt/decrypt personnel intake raw tokens for HR recovery (at-rest protection)."""
from __future__ import annotations

import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken

INTAKE_URL_PATH_PREFIX = "/intake/"


def _encryption_secret() -> str:
    explicit = (os.getenv("PERSONNEL_INTAKE_TOKEN_ENCRYPTION_KEY") or "").strip()
    if not explicit:
        raise RuntimeError(
            "PERSONNEL_INTAKE_TOKEN_ENCRYPTION_KEY must be set for intake token encryption."
        )
    return explicit


def _fernet() -> Fernet:
    secret = _encryption_secret()
    if secret.startswith("gAAAA") and len(secret) >= 44:
        key = secret.encode("utf-8")
    else:
        digest = hashlib.sha256(secret.encode("utf-8")).digest()
        key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_intake_raw_token(raw_token: str) -> str:
    token = str(raw_token or "").strip()
    if not token:
        raise ValueError("raw_token is required")
    return _fernet().encrypt(token.encode("utf-8")).decode("utf-8")


def decrypt_intake_raw_token(token_ciphertext: str | None) -> str | None:
    value = str(token_ciphertext or "").strip()
    if not value:
        return None
    try:
        return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeDecodeError):
        return None


def intake_url_path_from_raw_token(raw_token: str) -> str:
    token = str(raw_token or "").strip()
    if not token:
        raise ValueError("raw_token is required")
    return f"{INTAKE_URL_PATH_PREFIX}{token}"


def decrypt_intake_url_path(token_ciphertext: str | None) -> str | None:
    raw = decrypt_intake_raw_token(token_ciphertext)
    if not raw:
        return None
    return intake_url_path_from_raw_token(raw)
