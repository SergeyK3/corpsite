"""Pre-signature readiness validation (OO-IMP-004)."""
from __future__ import annotations

from typing import Any, Sequence

from app.db.models.operational_orders import (
    DOCUMENT_STATUS_CREATED,
    DOCUMENT_STATUS_READY_FOR_SIGNATURE,
    LOCALE_KK,
    LOCALE_RU,
    PARTY_REFERENCE_TYPES,
    PROMOTION_STATUS_COMPLETED,
    SIGNING_AUTHORITY_STATUS_ACTIVE,
    WORKSPACE_STAGE_DOCUMENT_PROMOTED,
)
from app.document_engine import ValidationIssue, ValidationResult, ValidationSeverity
from app.operational_orders.domain import content_fingerprint
from app.operational_orders.validation.promotion_validation import snapshot_fingerprint


def _locale_has_official_text(localizations: Sequence[dict[str, Any]], locale: str) -> bool:
    return any(
        str(item.get("locale")) == locale and str(item.get("official_text") or "").strip()
        for item in localizations
    )


def validate_signature_readiness(
    *,
    document: dict[str, Any],
    current_versions: Sequence[dict[str, Any]],
    localizations: Sequence[dict[str, Any]],
    promotion: dict[str, Any] | None,
    workspace: dict[str, Any] | None,
    signing_authority: dict[str, Any] | None,
    expected_document_version: int | None = None,
    workspace_drift_detected: bool = False,
    for_mark_ready: bool = False,
) -> ValidationResult:
    issues: list[ValidationIssue] = []
    status = str(document.get("status") or "")

    if status not in {DOCUMENT_STATUS_CREATED, DOCUMENT_STATUS_READY_FOR_SIGNATURE}:
        issues.append(
            ValidationIssue(
                code="OO412",
                severity=ValidationSeverity.ERROR,
                message="Document status does not allow signature readiness.",
                field_path="document.status",
            )
        )

    if status == DOCUMENT_STATUS_READY_FOR_SIGNATURE and for_mark_ready:
        issues.append(
            ValidationIssue(
                code="OO411",
                severity=ValidationSeverity.ERROR,
                message="Document is already ready for signature.",
                field_path="document.status",
            )
        )

    if status != DOCUMENT_STATUS_CREATED and for_mark_ready is False and status != DOCUMENT_STATUS_READY_FOR_SIGNATURE:
        issues.append(
            ValidationIssue(
                code="OO401",
                severity=ValidationSeverity.ERROR,
                message="Document is not in CREATED status.",
                field_path="document.status",
            )
        )
    elif status != DOCUMENT_STATUS_CREATED and for_mark_ready:
        if status != DOCUMENT_STATUS_READY_FOR_SIGNATURE:
            issues.append(
                ValidationIssue(
                    code="OO401",
                    severity=ValidationSeverity.ERROR,
                    message="Document is not in CREATED status.",
                    field_path="document.status",
                )
            )

    current = [v for v in current_versions if bool(v.get("is_current"))]
    if not current:
        issues.append(
            ValidationIssue(
                code="OO402",
                severity=ValidationSeverity.ERROR,
                message="Current document version is missing.",
                field_path="document.current_version",
            )
        )
    elif len(current) > 1:
        issues.append(
            ValidationIssue(
                code="OO403",
                severity=ValidationSeverity.ERROR,
                message="Current document version is ambiguous.",
                field_path="document.current_version",
            )
        )

    current_version = current[0] if current else None

    if expected_document_version is not None and int(document.get("version") or 0) != int(
        expected_document_version
    ):
        issues.append(
            ValidationIssue(
                code="OO410",
                severity=ValidationSeverity.ERROR,
                message="Document aggregate version is stale.",
                field_path="document.version",
            )
        )

    if not _locale_has_official_text(localizations, LOCALE_RU):
        issues.append(
            ValidationIssue(
                code="OO404",
                severity=ValidationSeverity.ERROR,
                message="Russian localization is missing.",
                field_path="localizations.ru",
            )
        )

    if not _locale_has_official_text(localizations, LOCALE_KK):
        issues.append(
            ValidationIssue(
                code="OO405",
                severity=ValidationSeverity.ERROR,
                message="Kazakh localization is missing.",
                field_path="localizations.kk",
            )
        )

    for loc in localizations:
        text = str(loc.get("official_text") or "")
        stored_fp = str(loc.get("content_fingerprint") or "")
        if stored_fp and stored_fp != content_fingerprint(text):
            issues.append(
                ValidationIssue(
                    code="OO406",
                    severity=ValidationSeverity.ERROR,
                    message="Localization fingerprint mismatch.",
                    field_path=f"localizations.{loc.get('locale')}.{loc.get('block_type')}",
                )
            )

    if current_version is not None:
        computed_fp = snapshot_fingerprint(localizations)
        stored_snapshot_fp = str(current_version.get("snapshot_fingerprint") or "")
        if stored_snapshot_fp and stored_snapshot_fp != computed_fp:
            issues.append(
                ValidationIssue(
                    code="OO407",
                    severity=ValidationSeverity.ERROR,
                    message="Document snapshot integrity failed.",
                    field_path="document.current_version.snapshot_fingerprint",
                )
            )
        if int(current_version.get("document_id") or 0) != int(document.get("id") or 0):
            issues.append(
                ValidationIssue(
                    code="OO413",
                    severity=ValidationSeverity.ERROR,
                    message="Current version does not belong to document.",
                    field_path="document.current_version.document_id",
                )
            )

    if signing_authority is None:
        issues.append(
            ValidationIssue(
                code="OO408",
                severity=ValidationSeverity.ERROR,
                message="Signing authority is missing.",
                field_path="signing_authority",
            )
        )
    else:
        party_type = str(signing_authority.get("authority_party_type") or "")
        party_ref = str(signing_authority.get("authority_party_reference") or "").strip()
        if party_type not in PARTY_REFERENCE_TYPES or not party_ref:
            issues.append(
                ValidationIssue(
                    code="OO409",
                    severity=ValidationSeverity.ERROR,
                    message="Signing authority is invalid.",
                    field_path="signing_authority.authority_party_reference",
                )
            )
        if str(signing_authority.get("status")) != SIGNING_AUTHORITY_STATUS_ACTIVE:
            issues.append(
                ValidationIssue(
                    code="OO409",
                    severity=ValidationSeverity.ERROR,
                    message="Signing authority is not active.",
                    field_path="signing_authority.status",
                )
            )
        if current_version is not None and int(signing_authority.get("document_version_id") or 0) != int(
            current_version.get("id") or 0
        ):
            issues.append(
                ValidationIssue(
                    code="OO409",
                    severity=ValidationSeverity.ERROR,
                    message="Signing authority does not match current version.",
                    field_path="signing_authority.document_version_id",
                )
            )

    if workspace is None:
        issues.append(
            ValidationIssue(
                code="OO415",
                severity=ValidationSeverity.ERROR,
                message="Workspace provenance link is missing.",
                field_path="document.workspace_id",
            )
        )
    elif str(workspace.get("stage")) != WORKSPACE_STAGE_DOCUMENT_PROMOTED:
        issues.append(
            ValidationIssue(
                code="OO415",
                severity=ValidationSeverity.ERROR,
                message="Workspace is not in DOCUMENT_PROMOTED stage.",
                field_path="workspace.stage",
            )
        )
    elif int(workspace.get("workspace_id") or 0) != int(document.get("workspace_id") or 0):
        issues.append(
            ValidationIssue(
                code="OO415",
                severity=ValidationSeverity.ERROR,
                message="Workspace document link is inconsistent.",
                field_path="document.workspace_id",
            )
        )

    if promotion is None:
        issues.append(
            ValidationIssue(
                code="OO414",
                severity=ValidationSeverity.ERROR,
                message="Promotion record is missing.",
                field_path="document.promotion_id",
            )
        )
    else:
        if str(promotion.get("status")) != PROMOTION_STATUS_COMPLETED:
            issues.append(
                ValidationIssue(
                    code="OO414",
                    severity=ValidationSeverity.ERROR,
                    message="Promotion is not completed.",
                    field_path="promotion.status",
                )
            )
        if int(promotion.get("document_id") or 0) != int(document.get("id") or 0):
            issues.append(
                ValidationIssue(
                    code="OO414",
                    severity=ValidationSeverity.ERROR,
                    message="Promotion document link is inconsistent.",
                    field_path="promotion.document_id",
                )
            )

    if workspace_drift_detected:
        issues.append(
            ValidationIssue(
                code="OO416",
                severity=ValidationSeverity.ERROR,
                message="Workspace drift detected; revision required before signature readiness.",
                field_path="workspace.drift",
            )
        )

    return ValidationResult.from_issues(issues)
