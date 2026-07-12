"""Shared validation result contracts (UDE-001)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence, Tuple


class ValidationSeverity(str, Enum):
    """Issue severity for validation aggregation."""

    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """Single validation finding."""

    code: str
    severity: ValidationSeverity
    message: str
    field_path: str | None = None
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        normalized_code = str(self.code or "").strip()
        if not normalized_code:
            raise ValueError("ValidationIssue.code must be non-empty")
        object.__setattr__(self, "code", normalized_code)

        normalized_message = str(self.message or "").strip()
        if not normalized_message:
            raise ValueError("ValidationIssue.message must be non-empty")
        object.__setattr__(self, "message", normalized_message)

        if self.field_path is not None:
            object.__setattr__(self, "field_path", str(self.field_path).strip() or None)

        if self.metadata is not None:
            object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Aggregated validation outcome."""

    issues: Tuple[ValidationIssue, ...] = field(default_factory=tuple)

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == ValidationSeverity.ERROR for issue in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(issue.severity == ValidationSeverity.WARNING for issue in self.issues)

    @property
    def is_valid(self) -> bool:
        return not self.has_errors

    @classmethod
    def from_issues(cls, issues: Sequence[ValidationIssue]) -> ValidationResult:
        return cls(issues=tuple(issues))
