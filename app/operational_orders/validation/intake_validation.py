"""Intake validation for Operational Orders draft workspaces."""
from __future__ import annotations

from typing import Any, Sequence

from app.document_engine import LocaleCode, ValidationIssue, ValidationResult, ValidationSeverity
from app.db.models.operational_orders import (
    CLARIFICATION_SEVERITY_ERROR,
    CLARIFICATION_STATUS_OPEN,
    LOCALE_KK,
    LOCALE_RU,
)


def _meaningful_text(value: str | None) -> bool:
    return bool(str(value or "").strip())


def validate_intake_workspace(
    *,
    workspace: dict[str, Any],
    blocks: Sequence[dict[str, Any]],
    clarifications: Sequence[dict[str, Any]],
    provenance_count: int,
    for_ready_for_editorial: bool = False,
) -> ValidationResult:
    issues: list[ValidationIssue] = []

    if not workspace.get("initiator_reference"):
        issues.append(
            ValidationIssue(
                code="OI001",
                severity=ValidationSeverity.ERROR,
                message="Initiator is required.",
                field_path="initiator",
            )
        )
    if not workspace.get("content_author_reference"):
        issues.append(
            ValidationIssue(
                code="OI002",
                severity=ValidationSeverity.ERROR,
                message="Content author is required.",
                field_path="content_author",
            )
        )
    if not workspace.get("submitting_org_unit_id"):
        issues.append(
            ValidationIssue(
                code="OI003",
                severity=ValidationSeverity.ERROR,
                message="Submitting unit is required.",
                field_path="submitting_org_unit_id",
            )
        )
    if not workspace.get("record_creator_user_id"):
        issues.append(
            ValidationIssue(
                code="OI007",
                severity=ValidationSeverity.ERROR,
                message="Record creator is required.",
                field_path="record_creator_user_id",
            )
        )

    if not blocks:
        issues.append(
            ValidationIssue(
                code="OI004",
                severity=ValidationSeverity.ERROR,
                message="At least one submitted text block is required.",
                field_path="blocks",
            )
        )

    locales_present: set[str] = set()
    sequences: set[tuple[str, str, int]] = set()
    has_title = False

    for block in blocks:
        locale = str(block.get("locale") or "").strip().lower()
        if not locale:
            issues.append(
                ValidationIssue(
                    code="OI005",
                    severity=ValidationSeverity.ERROR,
                    message="Locale is required for each text block.",
                    field_path="blocks.locale",
                )
            )
        elif locale not in {LocaleCode.RU.value, LocaleCode.KK.value}:
            issues.append(
                ValidationIssue(
                    code="OI005",
                    severity=ValidationSeverity.ERROR,
                    message=f"Unsupported locale: {locale}",
                    field_path="blocks.locale",
                )
            )
        else:
            locales_present.add(locale)

        source_type = str(block.get("source_type") or "").strip()
        if not source_type:
            issues.append(
                ValidationIssue(
                    code="OI006",
                    severity=ValidationSeverity.ERROR,
                    message="Source type is required for each text block.",
                    field_path="blocks.source_type",
                )
            )

        if not _meaningful_text(block.get("submitted_text")):
            issues.append(
                ValidationIssue(
                    code="OI013",
                    severity=ValidationSeverity.ERROR,
                    message="Submitted text must not be empty.",
                    field_path="blocks.submitted_text",
                )
            )

        seq_key = (
            locale,
            str(block.get("block_type") or ""),
            int(block.get("sequence") or 0),
        )
        if seq_key in sequences:
            issues.append(
                ValidationIssue(
                    code="OI012",
                    severity=ValidationSeverity.ERROR,
                    message="Duplicate block sequence within locale and block type.",
                    field_path="blocks.sequence",
                )
            )
        sequences.add(seq_key)

        if str(block.get("block_type") or "").upper() == "TITLE" and _meaningful_text(
            block.get("submitted_text")
        ):
            has_title = True

    if blocks and not has_title and not _meaningful_text(workspace.get("proposed_title")):
        issues.append(
            ValidationIssue(
                code="OI008",
                severity=ValidationSeverity.WARNING,
                message="Title block or proposed title is missing.",
                field_path="title",
            )
        )

    if LOCALE_RU not in locales_present:
        severity = ValidationSeverity.ERROR if for_ready_for_editorial else ValidationSeverity.WARNING
        issues.append(
            ValidationIssue(
                code="OI009",
                severity=severity,
                message="Russian (RU) locale text is missing.",
                field_path="locales.ru",
            )
        )
    if LOCALE_KK not in locales_present:
        severity = ValidationSeverity.ERROR if for_ready_for_editorial else ValidationSeverity.WARNING
        issues.append(
            ValidationIssue(
                code="OI010",
                severity=severity,
                message="Kazakh (KK) locale text is missing.",
                field_path="locales.kk",
            )
        )

    if blocks and provenance_count < len(blocks):
        issues.append(
            ValidationIssue(
                code="OI011",
                severity=ValidationSeverity.ERROR if for_ready_for_editorial else ValidationSeverity.WARNING,
                message="Provenance is incomplete for one or more blocks.",
                field_path="provenance",
            )
        )

    blocking_clarifications = [
        item
        for item in clarifications
        if item.get("status") == CLARIFICATION_STATUS_OPEN
        and item.get("severity") == CLARIFICATION_SEVERITY_ERROR
    ]
    if blocking_clarifications:
        issues.append(
            ValidationIssue(
                code="OI014",
                severity=ValidationSeverity.ERROR,
                message="Unresolved blocking clarifications remain.",
                field_path="clarifications",
                metadata={"count": len(blocking_clarifications)},
            )
        )

    return ValidationResult.from_issues(issues)
