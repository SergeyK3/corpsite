"""Map service payloads to API response models."""
from __future__ import annotations

from typing import Any

from app.document_engine import ValidationResult
from app.operational_orders.schemas.draft_workspace import (
    AuditSummaryOut,
    ClarificationOut,
    DraftBlockOut,
    DraftWorkspaceDetailOut,
    DraftWorkspaceListOut,
    DraftWorkspaceSummaryOut,
    LocaleCompletenessOut,
    ProvenanceSummaryOut,
    ValidationIssueOut,
    ValidationResultOut,
)
from app.operational_orders.schemas.document_aggregate import (
    DocumentDetailOut,
    DocumentLocalizationListOut,
    DocumentSummaryOut,
    DocumentVersionDetailOut,
    DocumentVersionOut,
    PromotionResultOut,
    PromotionSummaryOut,
)
from app.operational_orders.schemas.editorial_workflow import (
    BilingualReconciliationOut,
    ContentConfirmationOut,
    TranslationAssignmentOut,
)


def _validation_out(result: ValidationResult) -> ValidationResultOut:
    return ValidationResultOut(
        is_valid=result.is_valid,
        has_errors=result.has_errors,
        has_warnings=result.has_warnings,
        issues=[
            ValidationIssueOut(
                code=issue.code,
                severity=issue.severity.value,
                message=issue.message,
                field_path=issue.field_path,
                metadata=dict(issue.metadata) if issue.metadata else None,
            )
            for issue in result.issues
        ],
    )


def _workspace_summary(row: dict[str, Any]) -> DraftWorkspaceSummaryOut:
    return DraftWorkspaceSummaryOut(
        workspace_id=int(row["workspace_id"]),
        organization_id=int(row["organization_id"]),
        drafting_path=str(row["drafting_path"]),
        stage=str(row["stage"]),
        submitting_org_unit_id=int(row["submitting_org_unit_id"]),
        record_creator_user_id=int(row["record_creator_user_id"]),
        content_author_reference=str(row["content_author_reference"]),
        content_author_type=str(row["content_author_type"]),
        proposed_title=row.get("proposed_title"),
        submitted_at=row["submitted_at"],
        accepted_at=row.get("accepted_at"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        version=int(row["version"]),
        ru_present=row.get("ru_present"),
        kk_present=row.get("kk_present"),
    )


def to_detail_out(detail: dict[str, Any]) -> DraftWorkspaceDetailOut:
    validation = detail["validation"]
    if not isinstance(validation, ValidationResult):
        validation = ValidationResult.from_issues([])
    return DraftWorkspaceDetailOut(
        workspace=_workspace_summary(detail["workspace"]),
        blocks=[DraftBlockOut.model_validate(item) for item in detail["blocks"]],
        provenance=[ProvenanceSummaryOut.model_validate(item) for item in detail["provenance"]],
        clarifications=[ClarificationOut.model_validate(item) for item in detail["clarifications"]],
        audit=[AuditSummaryOut.model_validate(item) for item in detail["audit"]],
        validation=_validation_out(validation),
        locale_completeness=LocaleCompletenessOut.model_validate(detail["locale_completeness"]),
        readiness_for_editorial=bool(detail["readiness_for_editorial"]),
        readiness_for_editorial_package=bool(detail.get("readiness_for_editorial_package")),
        translation_assignments=[
            TranslationAssignmentOut.model_validate(item).model_dump()
            for item in detail.get("translation_assignments", [])
        ],
        content_confirmations=[
            ContentConfirmationOut.model_validate(item).model_dump()
            for item in detail.get("content_confirmations", [])
        ],
        bilingual_reconciliations=[
            BilingualReconciliationOut.model_validate(item).model_dump()
            for item in detail.get("bilingual_reconciliations", [])
        ],
    )


def to_list_out(result: dict[str, Any]) -> DraftWorkspaceListOut:
    return DraftWorkspaceListOut(
        items=[_workspace_summary(item) for item in result["items"]],
        total=int(result["total"]),
        limit=int(result["limit"]),
        offset=int(result["offset"]),
    )


def to_document_detail_out(detail: dict[str, Any]) -> DocumentDetailOut:
    current_version = detail.get("current_version")
    promotion = detail.get("promotion")
    return DocumentDetailOut(
        document=DocumentSummaryOut.model_validate(detail["document"]),
        current_version=DocumentVersionOut.model_validate(current_version) if current_version else None,
        promotion=PromotionSummaryOut.model_validate(promotion) if promotion else None,
    )


def to_promotion_result_out(result: dict[str, Any]) -> PromotionResultOut:
    validation = result["validation"]
    if not isinstance(validation, ValidationResult):
        validation = ValidationResult.from_issues([])
    return PromotionResultOut(
        workspace_id=int(result["workspace_id"]),
        document=to_document_detail_out(result["document"]),
        validation=_validation_out(validation),
        idempotent_replay=bool(result.get("idempotent_replay")),
        workspace_frozen=bool(result.get("workspace_frozen")),
        workspace_drift_detected=bool(result.get("workspace_drift_detected")),
        revision_recommended=bool(result.get("revision_recommended")),
        document_id=int(result["document_id"]) if result.get("document_id") is not None else None,
        promotion_id=int(result["promotion_id"]) if result.get("promotion_id") is not None else None,
    )
