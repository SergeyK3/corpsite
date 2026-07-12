"""Workspace freeze and promotion replay validation codes (OO-IMP-003B)."""
from __future__ import annotations

from app.document_engine import ValidationIssue, ValidationResult, ValidationSeverity


def workspace_frozen_issue() -> ValidationIssue:
    return ValidationIssue(
        code="OO312",
        severity=ValidationSeverity.ERROR,
        message="Workspace is frozen after promotion.",
        field_path="workspace.stage",
    )


def workspace_drift_advisory() -> ValidationIssue:
    return ValidationIssue(
        code="OO311",
        severity=ValidationSeverity.WARNING,
        message="Workspace editorial package differs from promoted document snapshot.",
        field_path="workspace.fingerprint",
    )


def revision_required_advisory() -> ValidationIssue:
    return ValidationIssue(
        code="OO313",
        severity=ValidationSeverity.WARNING,
        message="A future Revision Command is required to publish workspace changes.",
        field_path="document.revision",
    )


def promotion_replay_advisory() -> ValidationIssue:
    return ValidationIssue(
        code="OO314",
        severity=ValidationSeverity.INFO,
        message="Promotion replay returned existing document aggregate.",
        field_path="promotion.replay",
    )


def workspace_already_promoted_advisory() -> ValidationIssue:
    return ValidationIssue(
        code="OO315",
        severity=ValidationSeverity.INFO,
        message="Workspace already has a promoted document.",
        field_path="workspace.promotion",
    )


def build_replay_advisories(*, drift_detected: bool) -> ValidationResult:
    issues = [promotion_replay_advisory(), workspace_already_promoted_advisory()]
    if drift_detected:
        issues.extend([workspace_drift_advisory(), revision_required_advisory()])
    return ValidationResult.from_issues(issues)
