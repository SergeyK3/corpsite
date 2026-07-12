"""Readiness policy — editorial and metadata gates (UDE-011)."""
from __future__ import annotations

from typing import Any, Mapping, Sequence, Tuple

from app.document_engine.contracts.validation import ValidationIssue, ValidationResult, ValidationSeverity
from app.document_engine.editorial.editorial_models import (
    EditorialBlock,
    EditorialDocument,
    OfficialDraftLocaleBlock,
    OfficialDraftSnapshot,
    ReviewState,
)
from app.document_engine.lifecycle.lifecycle_models import LifecycleGate, LifecycleViolation
from app.document_engine.value_objects.localization import LocaleCode, StalenessState

MANDATORY_LOCALES: tuple[LocaleCode, ...] = (LocaleCode.RU, LocaleCode.KK)

_BLOCKING_REVIEW_STATES: frozenset[ReviewState] = frozenset({
    ReviewState.STALE,
    ReviewState.REVIEW_REQUIRED,
    ReviewState.UNKNOWN,
})

_BLOCKING_STALENESS: frozenset[StalenessState] = frozenset({
    StalenessState.STALE_SEMANTIC_CHANGE,
    StalenessState.STALE_RU_CHANGE_AFTER_KK,
    StalenessState.STALE_FINGERPRINT_MISMATCH,
    StalenessState.REVIEW_REQUIRED,
})


class ReadinessPolicy:
    """Evaluates editorial and structural readiness — no write commands."""

    @staticmethod
    def _violation(
        code: str,
        message: str,
        *,
        gate: LifecycleGate | None = None,
        field_path: str | None = None,
    ) -> LifecycleViolation:
        return LifecycleViolation(
            code=code,
            message=message,
            gate=gate,
            field_path=field_path,
        )

    @staticmethod
    def _issues_from_violations(
        violations: Sequence[LifecycleViolation],
    ) -> Tuple[ValidationIssue, ...]:
        return tuple(
            ValidationIssue(
                code=violation.code,
                severity=ValidationSeverity.ERROR,
                message=violation.message,
                field_path=violation.field_path,
            )
            for violation in violations
        )

    @staticmethod
    def check_review_states(blocks: Sequence[OfficialDraftLocaleBlock | EditorialBlock]) -> list[LifecycleViolation]:
        violations: list[LifecycleViolation] = []
        for block in blocks:
            review = block.review_state
            if review in _BLOCKING_REVIEW_STATES:
                violations.append(
                    ReadinessPolicy._violation(
                        code=f"E_REVIEW_{review.value}",
                        message=f"Block review state {review.value} blocks readiness",
                        gate=LifecycleGate.PROMOTION,
                        field_path=f"blocks[{getattr(block, 'block_id', block.block_type)}].review_state",
                    )
                )
            staleness = block.staleness_state
            if staleness in _BLOCKING_STALENESS:
                violations.append(
                    ReadinessPolicy._violation(
                        code=f"E_STALENESS_{staleness.value}",
                        message=f"Block staleness {staleness.value} blocks readiness",
                        gate=LifecycleGate.PROMOTION,
                        field_path=f"blocks.staleness_state",
                    )
                )
        return violations

    @staticmethod
    def check_mandatory_locales(
        blocks: Sequence[OfficialDraftLocaleBlock],
    ) -> list[LifecycleViolation]:
        present = {block.locale for block in blocks}
        violations: list[LifecycleViolation] = []
        for locale in MANDATORY_LOCALES:
            if locale not in present:
                violations.append(
                    ReadinessPolicy._violation(
                        code="E_LOCALE_MISSING",
                        message=f"Mandatory locale {locale.value} is missing",
                        gate=LifecycleGate.PROMOTION,
                        field_path=f"locale.{locale.value}",
                    )
                )
        return violations

    @staticmethod
    def check_effective_text(blocks: Sequence[OfficialDraftLocaleBlock]) -> list[LifecycleViolation]:
        violations: list[LifecycleViolation] = []
        for block in blocks:
            if not str(block.effective_text or "").strip():
                violations.append(
                    ReadinessPolicy._violation(
                        code="E_EFFECTIVE_EMPTY",
                        message="Effective text is required for all locale blocks",
                        gate=LifecycleGate.PROMOTION,
                        field_path=f"blocks.{block.block_type}.{block.locale.value}",
                    )
                )
        return violations

    @staticmethod
    def check_metadata(metadata: Mapping[str, Any]) -> list[LifecycleViolation]:
        violations: list[LifecycleViolation] = []
        if not str(metadata.get("order_number") or "").strip():
            violations.append(
                ReadinessPolicy._violation(
                    code="E_METADATA_ORDER_NUMBER",
                    message="Order number is required in draft metadata",
                    gate=LifecycleGate.PROMOTION,
                    field_path="draft_metadata.order_number",
                )
            )
        if not str(metadata.get("order_date") or "").strip():
            violations.append(
                ReadinessPolicy._violation(
                    code="E_METADATA_ORDER_DATE",
                    message="Order date is required in draft metadata",
                    gate=LifecycleGate.PROMOTION,
                    field_path="draft_metadata.order_date",
                )
            )
        return violations

    @staticmethod
    def check_items(item_count: int) -> list[LifecycleViolation]:
        if item_count > 0:
            return []
        return [
            ReadinessPolicy._violation(
                code="E_ITEMS_REQUIRED",
                message="At least one order item is required",
                gate=LifecycleGate.PROMOTION,
                field_path="item_count",
            )
        ]

    @staticmethod
    def check_editorial_sections(editorial: EditorialDocument) -> list[LifecycleViolation]:
        if editorial.sections:
            return []
        return [
            ReadinessPolicy._violation(
                code="E_SECTIONS_REQUIRED",
                message="At least one editorial section is required",
                gate=LifecycleGate.PROMOTION,
                field_path="editorial.sections",
            )
        ]

    @staticmethod
    def evaluate_official_draft(draft: OfficialDraftSnapshot) -> Tuple[list[LifecycleViolation], ValidationResult]:
        violations: list[LifecycleViolation] = []
        violations.extend(ReadinessPolicy.check_mandatory_locales(draft.locale_blocks))
        violations.extend(ReadinessPolicy.check_effective_text(draft.locale_blocks))
        violations.extend(ReadinessPolicy.check_review_states(draft.locale_blocks))
        violations.extend(ReadinessPolicy.check_metadata(draft.draft_metadata))
        violations.extend(ReadinessPolicy.check_items(draft.item_count))
        if not str(draft.workspace_reference or "").strip():
            violations.append(
                ReadinessPolicy._violation(
                    code="E_WORKSPACE_REF",
                    message="Workspace reference is required for activation",
                    gate=LifecycleGate.ACTIVATION,
                    field_path="workspace_reference",
                )
            )
        if not str(draft.order_type_code or "").strip():
            violations.append(
                ReadinessPolicy._violation(
                    code="E_ORDER_TYPE",
                    message="Order type code is required",
                    gate=LifecycleGate.PROMOTION,
                    field_path="order_type_code",
                )
            )
        issues = ReadinessPolicy._issues_from_violations(violations)
        return violations, ValidationResult.from_issues(issues)

    @staticmethod
    def evaluate_mark_ready(editorial: EditorialDocument) -> Tuple[list[LifecycleViolation], ValidationResult]:
        violations: list[LifecycleViolation] = []
        for locale in editorial.locales:
            violations.extend(ReadinessPolicy.check_review_states(locale.blocks))
        violations.extend(ReadinessPolicy.check_editorial_sections(editorial))
        issues = ReadinessPolicy._issues_from_violations(violations)
        return violations, ValidationResult.from_issues(issues)
