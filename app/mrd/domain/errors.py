"""MRD domain invariant violations."""
from __future__ import annotations


class MrdDomainError(Exception):
    """Base class for MRD domain errors."""


class MrdInvariantViolationError(MrdDomainError):
    """Raised when a business invariant is violated."""


class DifferenceLifecycleError(MrdInvariantViolationError):
    """Invalid Detected Difference lifecycle transition."""


class MrdMutationForbiddenError(MrdInvariantViolationError):
    """Mutation blocked because MRD version is CLOSED or not ACTIVE."""


class DifferenceOriginError(MrdInvariantViolationError):
    """Invalid or inactive Difference Origin."""


class MrdNotFoundError(MrdDomainError):
    """Requested MRD version or ACTIVE pointer was not found."""


class DifferenceNotFoundError(MrdDomainError):
    """Detected Difference not found."""


class MrdOptimisticConcurrencyConflictError(MrdInvariantViolationError):
    """Optimistic concurrency token mismatch."""


class DifferenceStateConflictError(MrdInvariantViolationError):
    """Operation forbidden for current Detected Difference lifecycle status."""


class DifferenceConfirmForbiddenError(MrdInvariantViolationError):
    """Confirm blocked by business policy (e.g. CONFLICT technical class)."""


class ActiveMrdMissingError(MrdNotFoundError):
    """No ACTIVE MRD exists for the requested report_period."""


class ActiveMrdAmbiguousError(MrdInvariantViolationError):
    """More than one ACTIVE MRD exists for the requested report_period."""


class ForkForbiddenError(MrdInvariantViolationError):
    """Fork operation blocked by business rules."""


class MrdPeriodExistsError(MrdInvariantViolationError):
    """Target report_period already has an MRD version."""


class MrdCommandConflictError(MrdInvariantViolationError):
    """command_id reused with a different request fingerprint."""


class MrdVersionDuplicateError(MrdInvariantViolationError):
    """Target MRD version already exists for the period."""


class MrdPeriodWindowError(MrdDomainError):
    """Target report_period is outside the allowed creation window."""
