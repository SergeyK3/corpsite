# tests/personnel_applications/test_iin.py
"""Unit tests for production IIN utility."""
from __future__ import annotations

import pytest

from app.domain.iin import IinValidationError, normalize_and_validate_iin, normalize_iin, validate_iin


def test_normalize_strips_non_digits() -> None:
    assert normalize_iin("9001 0135-0123") == "900101350123"


def test_validate_requires_twelve_digits() -> None:
    with pytest.raises(IinValidationError):
        validate_iin("123")
    with pytest.raises(IinValidationError):
        validate_iin("1234567890123")


def test_normalize_and_validate_happy_path() -> None:
    assert normalize_and_validate_iin("9001-0135-0123") == "900101350123"
