"""PPR domain and infrastructure errors (R1 envelope persistence)."""
from __future__ import annotations


class PprError(RuntimeError):
    code: str = "PPR_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


class PprEnvelopeNotFoundError(LookupError):
    code = "PPR_ENVELOPE_NOT_FOUND"


class PprEnvelopeAlreadyExistsError(PprError):
    code = "PPR_ENVELOPE_ALREADY_EXISTS"


class PprOptimisticConcurrencyConflictError(PprError):
    code = "PPR_OPTIMISTIC_CONCURRENCY_CONFLICT"


class PprPersonNotFoundError(LookupError):
    code = "PPR_PERSON_NOT_FOUND"


class PprEmployeeNotFoundError(LookupError):
    code = "PPR_EMPLOYEE_NOT_FOUND"


class PprEmployeePersonLinkMissingError(PprError):
    code = "PPR_EMPLOYEE_PERSON_LINK_MISSING"


class PprIdentityResolutionError(PprError):
    code = "PPR_IDENTITY_RESOLUTION_ERROR"


class PprMergeTargetMissingError(PprIdentityResolutionError):
    code = "PPR_MERGE_TARGET_MISSING"


class PprMergeCycleError(PprIdentityResolutionError):
    code = "PPR_MERGE_CYCLE"


class PprMergeDepthExceededError(PprIdentityResolutionError):
    code = "PPR_MERGE_DEPTH_EXCEEDED"


class PprEventValidationError(PprError):
    code = "PPR_EVENT_VALIDATION_ERROR"


class PprEventTypeUnknownError(PprError):
    code = "PPR_EVENT_TYPE_UNKNOWN"


class PprLegacyEventMappingError(PprError):
    code = "PPR_LEGACY_EVENT_MAPPING_ERROR"


class PprLegacyEventMappingAmbiguousError(PprLegacyEventMappingError):
    code = "PPR_LEGACY_EVENT_MAPPING_AMBIGUOUS"
