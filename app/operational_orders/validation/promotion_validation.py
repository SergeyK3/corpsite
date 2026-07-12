"""Promotion preconditions validation (OO-IMP-003)."""
from __future__ import annotations

from typing import Any, Sequence

from app.db.models.operational_orders import (
    ASSIGNMENT_ACTIVE_STATUSES,
    CLARIFICATION_SEVERITY_ERROR,
    CLARIFICATION_STATUS_OPEN,
    CONFIRMATION_STATUS_CONFIRMED,
    LOCALE_KK,
    LOCALE_RU,
    RECONCILIATION_STATUS_RECONCILED,
    STALENESS_REVIEW_REQUIRED,
    STALENESS_STALE,
    WORKSPACE_STAGE_EDITORIAL_PACKAGE_READY,
)
from app.document_engine import ValidationIssue, ValidationResult, ValidationSeverity
from app.operational_orders.domain import content_fingerprint
from app.operational_orders.validation.editorial_validation import (
    block_effective_text,
    locale_has_effective_text,
    matched_block_pairs,
    required_roles_for_block,
    validate_editorial_package,
)


def workspace_fingerprint(
    *,
    workspace_version: int,
    blocks: Sequence[dict[str, Any]],
    reconciliations: Sequence[dict[str, Any]],
) -> str:
    parts = [f"ws:{int(workspace_version)}"]
    for block in sorted(
        blocks,
        key=lambda b: (str(b["locale"]), str(b["block_type"]), int(b["sequence"])),
    ):
        text = block_effective_text(block)
        if not text.strip():
            continue
        parts.append(
            "|".join(
                (
                    str(block["locale"]),
                    str(block["block_type"]),
                    str(block["sequence"]),
                    str(block["version"]),
                    content_fingerprint(text),
                )
            )
        )
    for reconciliation in sorted(reconciliations, key=lambda r: int(r["id"])):
        if str(reconciliation.get("status")) != RECONCILIATION_STATUS_RECONCILED:
            continue
        parts.append(
            "|".join(
                (
                    "rec",
                    str(reconciliation["id"]),
                    str(reconciliation["ru_content_fingerprint"]),
                    str(reconciliation["kk_content_fingerprint"]),
                )
            )
        )
    return content_fingerprint("\n".join(parts))


def snapshot_fingerprint(localizations: Sequence[dict[str, Any]]) -> str:
    parts = []
    for loc in sorted(
        localizations,
        key=lambda item: (str(item["locale"]), str(item["block_type"]), int(item["sequence"])),
    ):
        parts.append(
            "|".join(
                (
                    str(loc["locale"]),
                    str(loc["block_type"]),
                    str(loc["sequence"]),
                    str(loc["content_fingerprint"]),
                )
            )
        )
    return content_fingerprint("\n".join(parts))


def validate_promotion(
    *,
    workspace: dict[str, Any],
    blocks: Sequence[dict[str, Any]],
    clarifications: Sequence[dict[str, Any]],
    assignments: Sequence[dict[str, Any]],
    confirmations: Sequence[dict[str, Any]],
    reconciliations: Sequence[dict[str, Any]],
    expected_version: int | None = None,
    existing_document: dict[str, Any] | None = None,
) -> ValidationResult:
    issues: list[ValidationIssue] = []

    if existing_document is not None:
        return ValidationResult.from_issues(issues)

    if str(workspace.get("stage")) != WORKSPACE_STAGE_EDITORIAL_PACKAGE_READY:
        issues.append(
            ValidationIssue(
                code="OO301",
                severity=ValidationSeverity.ERROR,
                message="Workspace is not editorial package ready.",
                field_path="workspace.stage",
            )
        )

    if expected_version is not None and int(workspace.get("version") or 0) != int(expected_version):
        issues.append(
            ValidationIssue(
                code="OO305",
                severity=ValidationSeverity.ERROR,
                message="Workspace version conflict.",
                field_path="workspace.version",
            )
        )

    if not locale_has_effective_text(blocks, LOCALE_RU):
        issues.append(
            ValidationIssue(
                code="OO302",
                severity=ValidationSeverity.ERROR,
                message="Russian localization is missing.",
                field_path="blocks.ru",
            )
        )

    if not locale_has_effective_text(blocks, LOCALE_KK):
        issues.append(
            ValidationIssue(
                code="OO302",
                severity=ValidationSeverity.ERROR,
                message="Kazakh localization is missing.",
                field_path="blocks.kk",
            )
        )

    active_assignments = [a for a in assignments if str(a["status"]) in ASSIGNMENT_ACTIVE_STATUSES]
    if active_assignments:
        issues.append(
            ValidationIssue(
                code="OO308",
                severity=ValidationSeverity.ERROR,
                message="Active translation assignment exists.",
                field_path=f"translation_assignments.{active_assignments[0]['id']}",
            )
        )

    for clarification in clarifications:
        if (
            str(clarification.get("status")) == CLARIFICATION_STATUS_OPEN
            and str(clarification.get("severity")) == CLARIFICATION_SEVERITY_ERROR
        ):
            issues.append(
                ValidationIssue(
                    code="OO309",
                    severity=ValidationSeverity.ERROR,
                    message="Open blocking clarification exists.",
                    field_path=f"clarifications.{clarification.get('clarification_id')}",
                )
            )

    for block in blocks:
        text = block_effective_text(block)
        if not text.strip():
            continue
        fp = content_fingerprint(text)
        locale = str(block["locale"])
        for role in required_roles_for_block(locale=locale, assignments=assignments):
            confirmed = any(
                int(c["block_id"]) == int(block["block_id"])
                and str(c["content_fingerprint"]) == fp
                and str(c["confirmation_role"]) == role
                and str(c["status"]) == CONFIRMATION_STATUS_CONFIRMED
                for c in confirmations
            )
            if not confirmed:
                issues.append(
                    ValidationIssue(
                        code="OO303",
                        severity=ValidationSeverity.ERROR,
                        message=f"Missing {role} confirmation for block {block['block_id']}.",
                        field_path=f"blocks.{block['block_id']}.confirmations.{role}",
                    )
                )

        review_state = str(block.get("review_state") or "")
        if review_state in {STALENESS_STALE, STALENESS_REVIEW_REQUIRED}:
            issues.append(
                ValidationIssue(
                    code="OO310",
                    severity=ValidationSeverity.ERROR,
                    message=f"Block {block['block_id']} has stale workspace localization state.",
                    field_path=f"blocks.{block['block_id']}.review_state",
                )
            )

    for ru_block, kk_block in matched_block_pairs(blocks):
        ru_fp = content_fingerprint(block_effective_text(ru_block))
        kk_fp = content_fingerprint(block_effective_text(kk_block))
        reconciled = next(
            (
                r
                for r in reconciliations
                if str(r["status"]) == RECONCILIATION_STATUS_RECONCILED
                and int(r["ru_block_id"]) == int(ru_block["block_id"])
                and int(r["kk_block_id"]) == int(kk_block["block_id"])
                and str(r["ru_content_fingerprint"]) == ru_fp
                and str(r["kk_content_fingerprint"]) == kk_fp
                and int(r["ru_block_version"]) == int(ru_block["version"])
                and int(r["kk_block_version"]) == int(kk_block["version"])
            ),
            None,
        )
        if reconciled is None:
            stale = next(
                (
                    r
                    for r in reconciliations
                    if str(r["status"]) == RECONCILIATION_STATUS_RECONCILED
                    and int(r["ru_block_id"]) == int(ru_block["block_id"])
                    and int(r["kk_block_id"]) == int(kk_block["block_id"])
                ),
                None,
            )
            issues.append(
                ValidationIssue(
                    code="OO304" if stale is None else "OO310",
                    severity=ValidationSeverity.ERROR,
                    message=(
                        "Bilingual reconciliation is missing for block pair."
                        if stale is None
                        else "Bilingual reconciliation is stale for block pair."
                    ),
                    field_path=f"reconciliations.{ru_block['block_id']}-{kk_block['block_id']}",
                )
            )

    editorial = validate_editorial_package(
        workspace=workspace,
        blocks=blocks,
        clarifications=clarifications,
        assignments=assignments,
        confirmations=confirmations,
        reconciliations=reconciliations,
        expected_version=expected_version,
    )
    for issue in editorial.issues:
        if issue.code in {"OO213"}:
            if not any(existing.code == "OO305" for existing in issues):
                issues.append(
                    ValidationIssue(
                        code="OO305",
                        severity=ValidationSeverity.ERROR,
                        message=issue.message,
                        field_path=issue.field_path,
                    )
                )
            continue
        if issue.code.startswith("OO2") and not any(existing.code == issue.code for existing in issues):
            mapped = {
                "OO201": "OO302",
                "OO202": "OO302",
                "OO203": "OO308",
                "OO204": "OO308",
                "OO205": "OO303",
                "OO206": "OO303",
                "OO207": "OO303",
                "OO208": "OO304",
                "OO209": "OO310",
                "OO210": "OO309",
            }.get(issue.code, issue.code)
            issues.append(
                ValidationIssue(
                    code=mapped,
                    severity=issue.severity,
                    message=issue.message,
                    field_path=issue.field_path,
                )
            )

    computed_ws_fp = workspace_fingerprint(
        workspace_version=int(workspace.get("version") or 0),
        blocks=blocks,
        reconciliations=reconciliations,
    )
    if not computed_ws_fp:
        issues.append(
            ValidationIssue(
                code="OO307",
                severity=ValidationSeverity.ERROR,
                message="Workspace fingerprint could not be computed.",
                field_path="workspace.fingerprint",
            )
        )

    return ValidationResult.from_issues(issues)
