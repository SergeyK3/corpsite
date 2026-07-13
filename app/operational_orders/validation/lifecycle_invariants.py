"""Lifecycle state ↔ metadata invariant validation (OO-IMP-005B).

Reusable utilities only — not wired to API or lifecycle commands.
"""
from __future__ import annotations

from typing import Any

from app.db.models.operational_orders import (
    DOCUMENT_STATUS_CREATED,
    DOCUMENT_STATUS_PUBLISHED,
    DOCUMENT_STATUS_READY_FOR_SIGNATURE,
    DOCUMENT_STATUS_REGISTERED,
    DOCUMENT_STATUS_SIGNED,
)
from app.document_engine import ValidationIssue, ValidationResult, ValidationSeverity


def _require_field(
    issues: list[ValidationIssue],
    *,
    code: str,
    field_path: str,
    value: Any,
    message: str,
) -> None:
    if value is None or (isinstance(value, str) and not value.strip()):
        issues.append(
            ValidationIssue(
                code=code,
                severity=ValidationSeverity.ERROR,
                message=message,
                field_path=field_path,
            )
        )


def validate_signed_metadata(document: dict[str, Any]) -> ValidationResult:
    """SIGNED requires signed_at."""
    issues: list[ValidationIssue] = []
    status = str(document.get("status") or "")
    if status != DOCUMENT_STATUS_SIGNED:
        return ValidationResult.from_issues(issues)

    _require_field(
        issues,
        code="OO501",
        field_path="document.signed_at",
        value=document.get("signed_at"),
        message="SIGNED status requires signed_at.",
    )
    return ValidationResult.from_issues(issues)


def validate_registered_metadata(document: dict[str, Any]) -> ValidationResult:
    """REGISTERED requires signature and registration metadata."""
    issues: list[ValidationIssue] = []
    status = str(document.get("status") or "")
    if status != DOCUMENT_STATUS_REGISTERED:
        return ValidationResult.from_issues(issues)

    _require_field(
        issues,
        code="OO502",
        field_path="document.signed_at",
        value=document.get("signed_at"),
        message="REGISTERED status requires signed_at.",
    )
    _require_field(
        issues,
        code="OO503",
        field_path="document.registration_number",
        value=document.get("registration_number"),
        message="REGISTERED status requires registration_number.",
    )
    _require_field(
        issues,
        code="OO504",
        field_path="document.registration_year",
        value=document.get("registration_year"),
        message="REGISTERED status requires registration_year.",
    )
    _require_field(
        issues,
        code="OO505",
        field_path="document.registration_date",
        value=document.get("registration_date"),
        message="REGISTERED status requires registration_date.",
    )
    _require_field(
        issues,
        code="OO506",
        field_path="document.registered_at",
        value=document.get("registered_at"),
        message="REGISTERED status requires registered_at.",
    )
    return ValidationResult.from_issues(issues)


def validate_published_metadata(document: dict[str, Any]) -> ValidationResult:
    """PUBLISHED requires publication metadata."""
    issues: list[ValidationIssue] = []
    status = str(document.get("status") or "")
    if status != DOCUMENT_STATUS_PUBLISHED:
        return ValidationResult.from_issues(issues)

    _require_field(
        issues,
        code="OO507",
        field_path="document.published_at",
        value=document.get("published_at"),
        message="PUBLISHED status requires published_at.",
    )
    _require_field(
        issues,
        code="OO508",
        field_path="document.published_by_user_id",
        value=document.get("published_by_user_id"),
        message="PUBLISHED status requires published_by_user_id.",
    )
    return ValidationResult.from_issues(issues)


def validate_lifecycle_metadata(document: dict[str, Any]) -> ValidationResult:
    """Aggregate lifecycle metadata invariants for a document snapshot."""
    issues: list[ValidationIssue] = []
    for result in (
        validate_signed_metadata(document),
        validate_registered_metadata(document),
        validate_published_metadata(document),
    ):
        issues.extend(result.issues)
    return ValidationResult.from_issues(issues)


def validate_backward_compatible_document(document: dict[str, Any]) -> ValidationResult:
    """Pre-005B operational documents remain valid without lifecycle metadata."""
    issues: list[ValidationIssue] = []
    status = str(document.get("status") or "")
    if status not in {
        DOCUMENT_STATUS_CREATED,
        DOCUMENT_STATUS_READY_FOR_SIGNATURE,
        DOCUMENT_STATUS_REGISTERED,
    }:
        return ValidationResult.from_issues(issues)

    lifecycle_fields = (
        "signed_at",
        "signed_by_user_id",
        "registration_number",
        "registration_year",
        "registration_date",
        "registered_at",
        "registered_by_user_id",
        "published_at",
        "published_by_user_id",
    )
    if status in {DOCUMENT_STATUS_CREATED, DOCUMENT_STATUS_READY_FOR_SIGNATURE}:
        for field_name in lifecycle_fields:
            if document.get(field_name) is not None:
                issues.append(
                    ValidationIssue(
                        code="OO509",
                        severity=ValidationSeverity.ERROR,
                        message=f"{status} must not carry {field_name}.",
                        field_path=f"document.{field_name}",
                    )
                )
    return ValidationResult.from_issues(issues)
