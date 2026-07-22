"""Unit tests for ADR-059 review exception display/correction helpers."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.services.hr_import_review_exception_detail_service import (
    ROSTER_IMPORT_CORRECTABLE_FIELDS,
    _resolve_reference_display_value,
)


def test_resolve_reference_display_value_org_unit_id() -> None:
    conn = MagicMock()
    conn.execute.return_value.scalar.return_value = "Терапевтическое отделение"
    display = _resolve_reference_display_value(
        conn,
        field="org_unit_id",
        value=47,
        record_kind="roster",
    )
    assert display == "Терапевтическое отделение"


def test_resolve_reference_display_value_record_kind() -> None:
    conn = MagicMock()
    display = _resolve_reference_display_value(
        conn,
        field="record_kind",
        value="training",
        record_kind="training",
    )
    assert display == "Обучение"


def test_roster_correctable_fields_include_department_and_position() -> None:
    assert "department" in ROSTER_IMPORT_CORRECTABLE_FIELDS
    assert "position_raw" in ROSTER_IMPORT_CORRECTABLE_FIELDS
