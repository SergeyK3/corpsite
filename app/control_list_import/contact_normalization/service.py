"""Contact normalization service: staging + profile + match → ContactCandidate (WP-CL-007).

Pure in-memory transformation — no PPR database access or contact merge/update.
"""
from __future__ import annotations

from typing import Any, Optional

from app.control_list_import.contact_normalization.address import normalize_contact_address
from app.control_list_import.contact_normalization.email import normalize_contact_email
from app.control_list_import.domain.contact_candidate import (
    ContactCandidate,
    ContactReadinessStatus,
    NormalizedEmail,
)
from app.control_list_import.domain.models import MappingProfileSnapshot
from app.control_list_import.domain.person_candidate import NormalizedField, NormalizedPhone, NormalizedPlainText
from app.control_list_import.domain.person_match_models import MatchReason, MatchStatus, PersonMatchResult
from app.control_list_import.domain.staging_models import StagingRowInput, StagingRunInput
from app.control_list_import.domain.vocabulary import (
    PARSER_CODE_CONTACT_ADDRESS,
    PARSER_CODE_CONTACT_EMAIL,
    PARSER_CODE_CONTACT_PHONE,
    PARSER_CODE_IDENTITY_PHONE,
    PARSER_CODE_TEXT_PLAIN,
    SEMANTIC_FIELD_CONTACT_EMAIL,
    SEMANTIC_FIELD_CONTACT_PHONE,
    SEMANTIC_FIELD_CONTACT_REGISTRATION_ADDRESS,
    SEMANTIC_FIELD_CONTACT_RESIDENCE_ADDRESS,
)
from app.control_list_import.normalization.phone import normalize_phone

ROW_KIND_DATA = "data"

_CONTACT_SEMANTIC_FIELDS = (
    SEMANTIC_FIELD_CONTACT_PHONE,
    SEMANTIC_FIELD_CONTACT_EMAIL,
    SEMANTIC_FIELD_CONTACT_RESIDENCE_ADDRESS,
    SEMANTIC_FIELD_CONTACT_REGISTRATION_ADDRESS,
)


def _empty_phone() -> NormalizedPhone:
    return NormalizedPhone(raw=None)


def _empty_email() -> NormalizedEmail:
    return NormalizedEmail(raw=None)


def _empty_address() -> NormalizedPlainText:
    return NormalizedPlainText(raw=None)


def _normalize_by_parser(parser_code: str, semantic_field: str, value: Any) -> NormalizedField:
    if parser_code in {PARSER_CODE_CONTACT_PHONE, PARSER_CODE_IDENTITY_PHONE} or semantic_field == SEMANTIC_FIELD_CONTACT_PHONE:
        return normalize_phone(value)
    if parser_code == PARSER_CODE_CONTACT_EMAIL or semantic_field == SEMANTIC_FIELD_CONTACT_EMAIL:
        return normalize_contact_email(value)
    if parser_code in {PARSER_CODE_CONTACT_ADDRESS, PARSER_CODE_TEXT_PLAIN} and semantic_field in {
        SEMANTIC_FIELD_CONTACT_RESIDENCE_ADDRESS,
        SEMANTIC_FIELD_CONTACT_REGISTRATION_ADDRESS,
    }:
        return normalize_contact_address(value)
    if semantic_field == SEMANTIC_FIELD_CONTACT_RESIDENCE_ADDRESS:
        return normalize_contact_address(value)
    if semantic_field == SEMANTIC_FIELD_CONTACT_REGISTRATION_ADDRESS:
        return normalize_contact_address(value)
    return normalize_contact_address(value)


def _matched_person_id(person_match: PersonMatchResult) -> Optional[int]:
    if person_match.status in {MatchStatus.EXACT, MatchStatus.PROBABLE}:
        return person_match.recommended_person_id
    return None


def _append_issues(
    field_issues: dict[str, tuple[str, ...]],
    semantic_field: str,
    issues: tuple[str, ...],
) -> None:
    if not issues:
        return
    existing = field_issues.get(semantic_field, ())
    field_issues[semantic_field] = tuple(dict.fromkeys(existing + issues))


def _field_has_content(field: NormalizedField) -> bool:
    if field.is_empty and not (field.raw or "").strip():
        return False
    if isinstance(field, NormalizedPhone):
        return field.is_valid or bool((field.raw or "").strip())
    if isinstance(field, NormalizedEmail):
        return field.is_valid or bool((field.raw or "").strip())
    if isinstance(field, NormalizedPlainText):
        if field.text:
            return True
        raw = (field.raw or "").strip()
        return bool(raw) and "contact_address_technical_empty" not in field.issues
    return not field.is_empty


def _has_any_contact_content(
    *,
    phone: NormalizedPhone,
    email: NormalizedEmail,
    residence_address: NormalizedPlainText,
    registration_address: NormalizedPlainText,
) -> bool:
    return any(
        _field_has_content(field)
        for field in (phone, email, residence_address, registration_address)
    )


def _collect_validation_issues(
    *,
    phone: NormalizedPhone,
    email: NormalizedEmail,
    residence_address: NormalizedPlainText,
    registration_address: NormalizedPlainText,
    field_issues: dict[str, tuple[str, ...]],
) -> None:
    if (phone.raw or "").strip() and not phone.is_valid:
        _append_issues(field_issues, SEMANTIC_FIELD_CONTACT_PHONE, phone.issues or ("phone_invalid_length",))
    if (email.raw or "").strip() and not email.is_valid:
        _append_issues(field_issues, SEMANTIC_FIELD_CONTACT_EMAIL, email.issues or ("contact_email_unrecognized_format",))
    for semantic_field, address in (
        (SEMANTIC_FIELD_CONTACT_RESIDENCE_ADDRESS, residence_address),
        (SEMANTIC_FIELD_CONTACT_REGISTRATION_ADDRESS, registration_address),
    ):
        if address.issues:
            _append_issues(field_issues, semantic_field, address.issues)


def _compute_readiness(
    *,
    person_match: PersonMatchResult,
    field_issues: dict[str, tuple[str, ...]],
) -> ContactReadinessStatus:
    if person_match.status == MatchStatus.INVALID:
        return ContactReadinessStatus.PERSON_MATCH_INVALID
    if person_match.status == MatchStatus.NOT_FOUND:
        return ContactReadinessStatus.PERSON_UNMATCHED
    if person_match.status == MatchStatus.AMBIGUOUS or person_match.recommended_person_id is None:
        return ContactReadinessStatus.REVIEW_REQUIRED
    if _has_normalization_blocking_issues(field_issues):
        return ContactReadinessStatus.REVIEW_REQUIRED
    return ContactReadinessStatus.NORMALIZATION_READY


def _has_normalization_blocking_issues(field_issues: dict[str, tuple[str, ...]]) -> bool:
    blocking = {
        "phone_invalid_length",
        "contact_email_unrecognized_format",
        "required_field_missing",
    }
    return any(issue in blocking for issues in field_issues.values() for issue in issues)


class ContactNormalizationService:
    """Map staging rows and person match results into Contact Candidate objects."""

    def normalize_row(
        self,
        *,
        row: StagingRowInput,
        profile: MappingProfileSnapshot,
        person_match: PersonMatchResult,
        import_run_id: Optional[int] = None,
    ) -> Optional[ContactCandidate]:
        if row.row_kind != ROW_KIND_DATA:
            return None

        profile_sheet = next((sheet for sheet in profile.sheets if sheet.sheet_name == row.sheet_name), None)
        if profile_sheet is None:
            return None

        contact_columns = [column for column in profile_sheet.columns if column.semantic_field in _CONTACT_SEMANTIC_FIELDS]
        if not contact_columns:
            return None

        cell_values: dict[int, Any] = {cell.column_index: cell.raw_value for cell in row.cells}
        fields: dict[str, NormalizedField] = {
            SEMANTIC_FIELD_CONTACT_PHONE: _empty_phone(),
            SEMANTIC_FIELD_CONTACT_EMAIL: _empty_email(),
            SEMANTIC_FIELD_CONTACT_RESIDENCE_ADDRESS: _empty_address(),
            SEMANTIC_FIELD_CONTACT_REGISTRATION_ADDRESS: _empty_address(),
        }
        field_issues: dict[str, tuple[str, ...]] = {}

        for column in contact_columns:
            raw_value = cell_values.get(column.column_index)
            if raw_value is None or (isinstance(raw_value, str) and not raw_value.strip()):
                if column.is_required:
                    _append_issues(field_issues, column.semantic_field, ("required_field_missing",))
                continue

            normalized = _normalize_by_parser(column.parser_code, column.semantic_field, raw_value)
            fields[column.semantic_field] = normalized
            if normalized.issues and "contact_address_technical_empty" not in normalized.issues:
                _append_issues(field_issues, column.semantic_field, normalized.issues)

        phone = fields[SEMANTIC_FIELD_CONTACT_PHONE]  # type: ignore[assignment]
        email = fields[SEMANTIC_FIELD_CONTACT_EMAIL]  # type: ignore[assignment]
        residence_address = fields[SEMANTIC_FIELD_CONTACT_RESIDENCE_ADDRESS]  # type: ignore[assignment]
        registration_address = fields[SEMANTIC_FIELD_CONTACT_REGISTRATION_ADDRESS]  # type: ignore[assignment]

        if not _has_any_contact_content(
            phone=phone,
            email=email,
            residence_address=residence_address,
            registration_address=registration_address,
        ):
            return None

        _collect_validation_issues(
            phone=phone,
            email=email,
            residence_address=residence_address,
            registration_address=registration_address,
            field_issues=field_issues,
        )

        readiness_status = _compute_readiness(
            person_match=person_match,
            field_issues=field_issues,
        )

        return ContactCandidate(
            import_run_id=import_run_id,
            profile_id=profile.profile_id,
            profile_code=profile.profile_code,
            profile_version=profile.profile_version,
            source_row_id=row.row_id,
            source_sheet_name=row.sheet_name,
            source_excel_row_number=row.excel_row_number,
            matched_person_id=_matched_person_id(person_match),
            phone=phone,
            email=email,
            residence_address=residence_address,
            registration_address=registration_address,
            field_issues=field_issues,
            readiness_status=readiness_status,
        )

    def normalize_run(
        self,
        *,
        staging: StagingRunInput,
        profile: MappingProfileSnapshot,
        person_matches: dict[int, PersonMatchResult],
    ) -> list[ContactCandidate]:
        candidates: list[ContactCandidate] = []
        for sheet in staging.sheets:
            for row in sheet.rows:
                person_match = person_matches.get(
                    row.row_id,
                    PersonMatchResult(
                        import_run_id=staging.import_run_id,
                        source_row_id=row.row_id,
                        status=MatchStatus.NOT_FOUND,
                        match_candidates=(),
                        primary_reason=MatchReason.NO_MATCH,
                        reasons=(MatchReason.NO_MATCH,),
                        confidence=0.0,
                        recommended_person_id=None,
                    ),
                )
                candidate = self.normalize_row(
                    row=row,
                    profile=profile,
                    person_match=person_match,
                    import_run_id=staging.import_run_id,
                )
                if candidate is not None:
                    candidates.append(candidate)
        return candidates
