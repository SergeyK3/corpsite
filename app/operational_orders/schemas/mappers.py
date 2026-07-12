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
    )


def to_list_out(result: dict[str, Any]) -> DraftWorkspaceListOut:
    return DraftWorkspaceListOut(
        items=[_workspace_summary(item) for item in result["items"]],
        total=int(result["total"]),
        limit=int(result["limit"]),
        offset=int(result["offset"]),
    )
