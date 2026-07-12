"""Editorial package validation rules (OO-IMP-002)."""
from __future__ import annotations

from typing import Any, Sequence

from app.db.models.operational_orders import (
    ASSIGNMENT_ACTIVE_STATUSES,
    ASSIGNMENT_STATUS_COMPLETED,
    CLARIFICATION_SEVERITY_ERROR,
    CLARIFICATION_STATUS_OPEN,
    CONFIRMATION_ROLE_CONTENT_AUTHOR,
    CONFIRMATION_ROLE_TRANSLATOR,
    CONFIRMATION_STATUS_CONFIRMED,
    LOCALE_KK,
    LOCALE_RU,
    RECONCILIATION_STATUS_RECONCILED,
    STALENESS_REVIEW_REQUIRED,
    STALENESS_STALE,
)
from app.document_engine import ValidationIssue, ValidationResult, ValidationSeverity
from app.operational_orders.domain import content_fingerprint


def block_effective_text(block: dict[str, Any]) -> str:
    effective = block.get("workspace_effective_text")
    if effective is not None and str(effective).strip():
        return str(effective)
    return str(block.get("submitted_text") or "")


def block_pair_key(block: dict[str, Any]) -> tuple[str, int]:
    return (str(block["block_type"]), int(block["sequence"]))


def matched_block_pairs(blocks: Sequence[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    ru_by_key = {
        block_pair_key(b): b for b in blocks if str(b["locale"]) == LOCALE_RU
    }
    kk_by_key = {
        block_pair_key(b): b for b in blocks if str(b["locale"]) == LOCALE_KK
    }
    keys = sorted(set(ru_by_key.keys()) & set(kk_by_key.keys()))
    return [(ru_by_key[key], kk_by_key[key]) for key in keys]


def locale_present(blocks: Sequence[dict[str, Any]], locale: str) -> bool:
    return any(str(b["locale"]) == locale for b in blocks)


def locale_has_effective_text(blocks: Sequence[dict[str, Any]], locale: str) -> bool:
    return any(str(b["locale"]) == locale and block_effective_text(b).strip() for b in blocks)


def requires_translator_confirmation(locale: str, assignments: Sequence[dict[str, Any]]) -> bool:
    return any(
        str(a["target_locale"]) == locale and str(a["status"]) == ASSIGNMENT_STATUS_COMPLETED
        for a in assignments
    )


def required_roles_for_block(
    *,
    locale: str,
    assignments: Sequence[dict[str, Any]],
) -> set[str]:
    roles = {CONFIRMATION_ROLE_CONTENT_AUTHOR}
    if requires_translator_confirmation(locale, assignments):
        roles.add(CONFIRMATION_ROLE_TRANSLATOR)
    return roles


def _confirmed(
    confirmations: Sequence[dict[str, Any]],
    *,
    block_id: int,
    fingerprint: str,
    role: str,
) -> bool:
    return any(
        int(c["block_id"]) == int(block_id)
        and str(c["content_fingerprint"]) == fingerprint
        and str(c["confirmation_role"]) == role
        and str(c["status"]) == CONFIRMATION_STATUS_CONFIRMED
        for c in confirmations
    )


def validate_editorial_package(
    *,
    workspace: dict[str, Any],
    blocks: Sequence[dict[str, Any]],
    clarifications: Sequence[dict[str, Any]],
    assignments: Sequence[dict[str, Any]],
    confirmations: Sequence[dict[str, Any]],
    reconciliations: Sequence[dict[str, Any]],
    expected_version: int | None = None,
) -> ValidationResult:
    issues: list[ValidationIssue] = []

    if expected_version is not None and int(workspace.get("version") or 0) != int(expected_version):
        issues.append(
            ValidationIssue(
                code="OO213",
                severity=ValidationSeverity.ERROR,
                message="Workspace version conflict.",
                field_path="workspace.version",
            )
        )

    if not locale_has_effective_text(blocks, LOCALE_RU):
        issues.append(
            ValidationIssue(
                code="OO201",
                severity=ValidationSeverity.ERROR,
                message="Russian effective text is missing.",
                field_path="blocks.ru",
            )
        )

    if not locale_has_effective_text(blocks, LOCALE_KK):
        issues.append(
            ValidationIssue(
                code="OO202",
                severity=ValidationSeverity.ERROR,
                message="Kazakh effective text is missing.",
                field_path="blocks.kk",
            )
        )

    active_assignments = [a for a in assignments if str(a["status"]) in ASSIGNMENT_ACTIVE_STATUSES]
    if active_assignments:
        for assignment in active_assignments:
            if str(assignment["status"]) == "REQUESTED":
                issues.append(
                    ValidationIssue(
                        code="OO203",
                        severity=ValidationSeverity.ERROR,
                        message="Active translation assignment is required to be accepted and completed.",
                        field_path=f"translation_assignments.{assignment['id']}",
                    )
                )
            else:
                issues.append(
                    ValidationIssue(
                        code="OO204",
                        severity=ValidationSeverity.ERROR,
                        message="Translation assignment is incomplete.",
                        field_path=f"translation_assignments.{assignment['id']}",
                    )
                )

    for block in blocks:
        text = block_effective_text(block)
        if not text.strip():
            continue
        fp = content_fingerprint(text)
        locale = str(block["locale"])
        for role in required_roles_for_block(locale=locale, assignments=assignments):
            if _confirmed(confirmations, block_id=int(block["block_id"]), fingerprint=fp, role=role):
                continue
            if role == CONFIRMATION_ROLE_CONTENT_AUTHOR and locale == LOCALE_RU:
                code = "OO205"
            elif role == CONFIRMATION_ROLE_CONTENT_AUTHOR and locale == LOCALE_KK:
                code = "OO206"
            elif role == CONFIRMATION_ROLE_TRANSLATOR:
                code = "OO207"
            else:
                code = "OO206" if locale == LOCALE_KK else "OO205"
            issues.append(
                ValidationIssue(
                    code=code,
                    severity=ValidationSeverity.ERROR,
                    message=f"Missing {role} confirmation for block {block['block_id']}.",
                    field_path=f"blocks.{block['block_id']}.confirmations.{role}",
                )
            )

        review_state = str(block.get("review_state") or "")
        if review_state in {STALENESS_STALE, STALENESS_REVIEW_REQUIRED}:
            issues.append(
                ValidationIssue(
                    code="OO209",
                    severity=ValidationSeverity.ERROR,
                    message=f"Block {block['block_id']} has stale localization state.",
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
            code = "OO209" if stale else "OO208"
            message = (
                "Bilingual reconciliation is stale for block pair."
                if stale
                else "Bilingual reconciliation is missing for block pair."
            )
            issues.append(
                ValidationIssue(
                    code=code,
                    severity=ValidationSeverity.ERROR,
                    message=message,
                    field_path=f"reconciliations.{ru_block['block_id']}-{kk_block['block_id']}",
                )
            )

    for clarification in clarifications:
        if (
            str(clarification.get("status")) == CLARIFICATION_STATUS_OPEN
            and str(clarification.get("severity")) == CLARIFICATION_SEVERITY_ERROR
        ):
            issues.append(
                ValidationIssue(
                    code="OO210",
                    severity=ValidationSeverity.ERROR,
                    message="Blocking clarification is open.",
                    field_path=f"clarifications.{clarification.get('clarification_id')}",
                )
            )

    return ValidationResult.from_issues(issues)
