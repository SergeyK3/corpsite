"""Contact Candidate domain model (WP-CL-007).

Temporary normalized contact slice — not canonical Person contact record.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Optional

from app.control_list_import.domain.person_candidate import NormalizedField, NormalizedPhone, NormalizedPlainText


class ContactReadinessStatus(StrEnum):
    """Normalization-layer readiness — does not authorize PPR contact writes."""

    NORMALIZATION_READY = "normalization_ready"
    REVIEW_REQUIRED = "review_required"
    PERSON_UNMATCHED = "person_unmatched"
    PERSON_MATCH_INVALID = "person_match_invalid"


@dataclass(frozen=True)
class NormalizedEmail(NormalizedField):
    address: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        return bool(self.address) and not self.has_issues


@dataclass(frozen=True)
class ContactCandidate:
    """Temporary normalized contact slice from one staging data row."""

    import_run_id: Optional[int]
    profile_id: Optional[int]
    profile_code: Optional[str]
    profile_version: Optional[int]
    source_row_id: Optional[int]
    source_sheet_name: str
    source_excel_row_number: int
    matched_person_id: Optional[int]
    phone: NormalizedPhone
    email: NormalizedEmail
    residence_address: NormalizedPlainText
    registration_address: NormalizedPlainText
    field_issues: dict[str, tuple[str, ...]] = field(default_factory=dict)
    readiness_status: ContactReadinessStatus = ContactReadinessStatus.REVIEW_REQUIRED

    @property
    def is_normalization_ready(self) -> bool:
        """True when person is matched/recommended and contact fields normalized cleanly.

        Does not authorize merge/update of canonical Person contacts — downstream WP only.
        """
        return self.readiness_status == ContactReadinessStatus.NORMALIZATION_READY

    @property
    def all_issues(self) -> tuple[str, ...]:
        seen: list[str] = []
        for issues in self.field_issues.values():
            for issue in issues:
                if issue not in seen:
                    seen.append(issue)
        return tuple(seen)
