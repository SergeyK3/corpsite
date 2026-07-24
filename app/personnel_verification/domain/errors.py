"""Domain errors for personnel verification foundation."""
from __future__ import annotations


class PersonnelVerificationError(Exception):
    """Base error for verification domain."""


class ControlPointNotAllowedError(PersonnelVerificationError):
    """Control point is outside the programmatic catalog."""


class CanonicalRecordUnavailableError(PersonnelVerificationError):
    """Task cannot be created because typed canonical record is missing."""


class PolicyValidationError(PersonnelVerificationError):
    """Policy fields or lifecycle violate invariants."""


class PolicyNotFoundError(PersonnelVerificationError):
    """Requested policy version does not exist."""


class TaskValidationError(PersonnelVerificationError):
    """Task creation or transition violates invariants."""


class TaskNotFoundError(PersonnelVerificationError):
    """Requested verification task does not exist."""


class AttestationValidationError(PersonnelVerificationError):
    """Attestation payload does not match task/policy/record."""


class AttestationImmutableError(PersonnelVerificationError):
    """Attestation mutation/delete is forbidden."""


class ControlledRecordNotFoundError(PersonnelVerificationError):
    """Referenced controlled record/version does not exist for person."""


class RevisionConflictError(PersonnelVerificationError):
    """Confirm/reject lost a race or violated revision preconditions (full rollback)."""
