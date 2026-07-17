"""Person Candidate domain model and normalized value objects (WP-CL-004).

Person Candidate is a temporary normalized import model — not canonical PPR Person.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class NormalizedField:
    """Base normalized field with raw source and issue codes."""

    raw: Optional[str]
    issues: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not (self.raw or "").strip()

    @property
    def has_issues(self) -> bool:
        return bool(self.issues)


@dataclass(frozen=True)
class NormalizedFullName(NormalizedField):
    display: Optional[str] = None
    normalized_key: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        return bool(self.display) and not self.has_issues


@dataclass(frozen=True)
class NormalizedIin(NormalizedField):
    digits: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        return self.digits is not None and len(self.digits) == 12 and not self.has_issues


@dataclass(frozen=True)
class NormalizedPhone(NormalizedField):
    digits: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        return (
            self.digits is not None
            and len(self.digits) in (10, 11, 12)
            and not self.has_issues
        )


@dataclass(frozen=True)
class NormalizedBirthDate(NormalizedField):
    value: Optional[date] = None

    @property
    def is_valid(self) -> bool:
        return self.value is not None and not self.has_issues


@dataclass(frozen=True)
class NormalizedSex(NormalizedField):
    code: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        return self.code in {"M", "F"} and not self.has_issues


@dataclass(frozen=True)
class NormalizedPlainText(NormalizedField):
    text: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        return bool(self.text) and not self.has_issues


@dataclass(frozen=True)
class PersonCandidate:
    """Temporary normalized person slice from one staging data row."""

    import_run_id: Optional[int]
    profile_id: Optional[int]
    profile_code: Optional[str]
    profile_version: Optional[int]
    source_row_id: Optional[int]
    source_sheet_name: str
    source_excel_row_number: int
    personnel_category: str
    employment_mode: str
    full_name: NormalizedFullName
    iin: NormalizedIin
    birth_date: NormalizedBirthDate
    phone: NormalizedPhone
    sex: NormalizedSex
    department_name: NormalizedPlainText
    position_title: NormalizedPlainText
    field_issues: dict[str, tuple[str, ...]] = field(default_factory=dict)

    @property
    def has_blocking_issues(self) -> bool:
        return any(
            self.field_issues.get(field, ())
            for field in ("person.full_name", "person.iin")
        )

    @property
    def all_issues(self) -> tuple[str, ...]:
        seen: list[str] = []
        for issues in self.field_issues.values():
            for issue in issues:
                if issue not in seen:
                    seen.append(issue)
        return tuple(seen)
