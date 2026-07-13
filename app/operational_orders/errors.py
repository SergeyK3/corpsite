"""Domain-level errors for Operational Orders intake."""
from __future__ import annotations


class OperationalOrderError(RuntimeError):
    code: str = "OO_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


class OperationalOrderWorkspaceNotFoundError(LookupError):
    code = "OO_WORKSPACE_NOT_FOUND"


class OperationalOrderBlockNotFoundError(LookupError):
    code = "OO_BLOCK_NOT_FOUND"


class OperationalOrderVersionConflictError(OperationalOrderError):
    code = "OO_WORKSPACE_VERSION_CONFLICT"


class OperationalOrderSubmittedTextImmutableError(OperationalOrderError):
    code = "OO_SUBMITTED_TEXT_IMMUTABLE"


class OperationalOrderInvalidWorkspaceStageError(OperationalOrderError):
    code = "OO_INVALID_WORKSPACE_STAGE"


class OperationalOrderValidationBlockedError(OperationalOrderError):
    code = "OO_VALIDATION_BLOCKED"


class OperationalOrderClarificationRequiredError(OperationalOrderError):
    code = "OO_CLARIFICATION_REQUIRED"


class OperationalOrderForbiddenError(PermissionError):
    code = "OO_FORBIDDEN"


class OperationalOrderClarificationNotFoundError(LookupError):
    code = "OO_CLARIFICATION_NOT_FOUND"


class OperationalOrderProvenanceRequiredError(OperationalOrderError):
    code = "OO_PROVENANCE_REQUIRED"


class OperationalOrderValidationError(ValueError):
    """Input validation failure before persistence."""


class OperationalOrderTranslationAssignmentNotFoundError(LookupError):
    code = "OO_TRANSLATION_ASSIGNMENT_NOT_FOUND"


class OperationalOrderTranslationAssignmentConflictError(OperationalOrderError):
    code = "OO_TRANSLATION_ASSIGNMENT_CONFLICT"


class OperationalOrderTranslationSourceStaleError(OperationalOrderError):
    code = "OO_TRANSLATION_SOURCE_STALE"


class OperationalOrderConfirmationNotFoundError(LookupError):
    code = "OO_CONFIRMATION_NOT_FOUND"


class OperationalOrderConfirmationPartyMismatchError(OperationalOrderError):
    code = "OO_CONFIRMATION_PARTY_MISMATCH"


class OperationalOrderConfirmationStaleTextError(OperationalOrderError):
    code = "OO_CONFIRMATION_STALE_TEXT"


class OperationalOrderConfirmationConflictError(OperationalOrderError):
    code = "OO_CONFIRMATION_CONFLICT"


class OperationalOrderReconciliationNotFoundError(LookupError):
    code = "OO_RECONCILIATION_NOT_FOUND"


class OperationalOrderReconciliationStaleError(OperationalOrderError):
    code = "OO_RECONCILIATION_STALE"


class OperationalOrderEditorialPackageNotReadyError(OperationalOrderError):
    code = "OO_EDITORIAL_PACKAGE_NOT_READY"


class OperationalOrderDocumentNotFoundError(LookupError):
    code = "OO_DOCUMENT_NOT_FOUND"


class OperationalOrderDocumentVersionNotFoundError(LookupError):
    code = "OO_DOCUMENT_VERSION_NOT_FOUND"


class OperationalOrderPromotionNotReadyError(OperationalOrderError):
    code = "OO_PROMOTION_NOT_READY"


class OperationalOrderPromotionAlreadyExistsError(OperationalOrderError):
    code = "OO_PROMOTION_ALREADY_EXISTS"


class OperationalOrderPromotionVersionConflictError(OperationalOrderError):
    code = "OO_PROMOTION_VERSION_CONFLICT"


class OperationalOrderWorkspaceFrozenError(OperationalOrderError):
    code = "OO_WORKSPACE_FROZEN"


class OperationalOrderDocumentVersionConflictError(OperationalOrderError):
    code = "OO_DOCUMENT_VERSION_CONFLICT"


class OperationalOrderDocumentStatusConflictError(OperationalOrderError):
    code = "OO_DOCUMENT_STATUS_CONFLICT"


class OperationalOrderDocumentAlreadyReadyError(OperationalOrderError):
    code = "OO_DOCUMENT_ALREADY_READY_FOR_SIGNATURE"


class OperationalOrderDocumentNotReadyError(OperationalOrderError):
    code = "OO_DOCUMENT_NOT_READY_FOR_SIGNATURE"


class OperationalOrderSigningAuthorityNotFoundError(LookupError):
    code = "OO_SIGNING_AUTHORITY_NOT_FOUND"


class OperationalOrderSigningAuthorityInvalidError(OperationalOrderError):
    code = "OO_SIGNING_AUTHORITY_INVALID"


class OperationalOrderSigningAuthorityConflictError(OperationalOrderError):
    code = "OO_SIGNING_AUTHORITY_CONFLICT"


class OperationalOrderSnapshotIntegrityError(OperationalOrderError):
    code = "OO_SNAPSHOT_INTEGRITY_FAILED"


class OperationalOrderRevisionRequiredError(OperationalOrderError):
    code = "OO_REVISION_REQUIRED"


class OperationalOrderLifecycleTransitionForbiddenError(OperationalOrderError):
    code = "OO_LIFECYCLE_TRANSITION_FORBIDDEN"


class OperationalOrderDocumentAlreadySignedError(OperationalOrderError):
    code = "OO_DOCUMENT_ALREADY_SIGNED"


class OperationalOrderSignAuthorityMismatchError(PermissionError):
    code = "OO_SIGN_AUTHORITY_MISMATCH"


class OperationalOrderSignIdempotencyConflictError(OperationalOrderError):
    code = "OO_SIGN_IDEMPOTENCY_CONFLICT"


class OperationalOrderSignOverrideReasonRequiredError(OperationalOrderValidationError):
    code = "OO_SIGN_OVERRIDE_REASON_REQUIRED"


class OperationalOrderDocumentScopeForbiddenError(PermissionError):
    code = "OO_DOCUMENT_SCOPE_FORBIDDEN"
