# tests/personnel_intake/test_token_encryption.py
from __future__ import annotations

import pytest

from app.personnel_intake.infrastructure.token_encryption import (
    decrypt_intake_raw_token,
    decrypt_intake_url_path,
    encrypt_intake_raw_token,
    intake_url_path_from_raw_token,
)


def test_encrypt_decrypt_roundtrip(monkeypatch) -> None:
    monkeypatch.setenv("PERSONNEL_INTAKE_TOKEN_ENCRYPTION_KEY", "test-intake-encryption-secret")
    raw = "sample-intake-token-value"
    ciphertext = encrypt_intake_raw_token(raw)
    assert ciphertext != raw
    assert decrypt_intake_raw_token(ciphertext) == raw
    assert decrypt_intake_url_path(ciphertext) == intake_url_path_from_raw_token(raw)


def test_decrypt_invalid_ciphertext_returns_none(monkeypatch) -> None:
    monkeypatch.setenv("PERSONNEL_INTAKE_TOKEN_ENCRYPTION_KEY", "test-intake-encryption-secret")
    assert decrypt_intake_raw_token("not-a-valid-token") is None


def test_missing_encryption_key_raises(monkeypatch) -> None:
    monkeypatch.delenv("PERSONNEL_INTAKE_TOKEN_ENCRYPTION_KEY", raising=False)
    with pytest.raises(RuntimeError, match="PERSONNEL_INTAKE_TOKEN_ENCRYPTION_KEY"):
        encrypt_intake_raw_token("sample-token")
