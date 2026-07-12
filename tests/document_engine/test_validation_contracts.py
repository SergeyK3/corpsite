# tests/document_engine/test_validation_contracts.py
"""Unit tests for UDE validation contracts (UDE-007)."""
from __future__ import annotations

import dataclasses

import pytest

from app.document_engine.contracts.validation import (
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)


def test_validation_issue_immutable_and_normalized() -> None:
    issue = ValidationIssue(
        code="  V001  ",
        severity=ValidationSeverity.ERROR,
        message="  Required field  ",
        field_path=" order.number ",
        metadata={"source": "test"},
    )
    assert issue.code == "V001"
    assert issue.message == "Required field"
    assert issue.field_path == "order.number"
    assert issue.metadata == {"source": "test"}
    with pytest.raises(dataclasses.FrozenInstanceError):
        issue.code = "V002"  # type: ignore[misc]


@pytest.mark.parametrize("field", ["code", "message"])
def test_validation_issue_rejects_empty_required_fields(field: str) -> None:
    payload = {
        "code": "V001",
        "severity": ValidationSeverity.ERROR,
        "message": "msg",
    }
    payload[field] = "   "
    with pytest.raises(ValueError):
        ValidationIssue(**payload)


def test_validation_result_semantics() -> None:
    errors_only = ValidationResult.from_issues(
        [
            ValidationIssue(
                code="E1",
                severity=ValidationSeverity.ERROR,
                message="error",
            )
        ]
    )
    assert errors_only.has_errors is True
    assert errors_only.has_warnings is False
    assert errors_only.is_valid is False

    warnings_only = ValidationResult.from_issues(
        [
            ValidationIssue(
                code="W1",
                severity=ValidationSeverity.WARNING,
                message="warn",
            )
        ]
    )
    assert warnings_only.has_errors is False
    assert warnings_only.has_warnings is True
    assert warnings_only.is_valid is True

    mixed = ValidationResult.from_issues(
        [
            ValidationIssue(
                code="W1",
                severity=ValidationSeverity.WARNING,
                message="warn",
            ),
            ValidationIssue(
                code="E1",
                severity=ValidationSeverity.ERROR,
                message="error",
            ),
        ]
    )
    assert mixed.has_errors is True
    assert mixed.has_warnings is True
    assert mixed.is_valid is False

    empty = ValidationResult()
    assert empty.has_errors is False
    assert empty.has_warnings is False
    assert empty.is_valid is True


def test_validation_result_equality_by_issues() -> None:
    issue = ValidationIssue(
        code="V001",
        severity=ValidationSeverity.INFO,
        message="info",
    )
    left = ValidationResult.from_issues([issue])
    right = ValidationResult.from_issues([issue])
    assert left == right
