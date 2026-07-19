"""Unit tests for HR control list storage helpers."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app.services.hr_import_control_list_storage import (
    ControlListFilenameError,
    build_technical_filename,
    format_report_period,
    parse_control_list_filename,
    sha256_hex,
)


def test_parse_control_list_filename_accepts_cyrillic_name():
    parsed = parse_control_list_filename("контрольный2606.xlsx")
    assert parsed.yymm == "2606"
    assert parsed.report_month == date(2026, 6, 1)
    assert parsed.original_filename == "контрольный2606.xlsx"


def test_parse_control_list_filename_rejects_invalid_name():
    with pytest.raises(ControlListFilenameError):
        parse_control_list_filename("tmp2606.xlsx")


def test_is_legacy_import_code():
    from app.services.hr_import_control_list_storage import is_legacy_import_code

    assert is_legacy_import_code("legacy-148") is True
    assert is_legacy_import_code("2606-01") is False


def test_build_technical_filename():
    assert build_technical_filename("2606-01", ".xlsx") == "control-list-2606-01.xlsx"


def test_format_report_period():
    assert format_report_period(date(2026, 6, 1)) == "06.2026"


def test_sha256_hex():
    assert sha256_hex(b"abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
