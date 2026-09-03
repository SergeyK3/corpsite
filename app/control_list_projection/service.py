"""Canonical, read-only active-personnel projection for WP-CL-002."""
from __future__ import annotations

import json
import os
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.config import env
from app.control_list_projection.schemas import (
    ControlListAcademicDegreeItem,
    ControlListAssignmentConflictDetail,
    ControlListAssignmentConflictItem,
    ControlListAwardItem,
    ControlListEducationItem,
    ControlListPhoneItem,
    ControlListProjectionMetadata,
    ControlListProjectionResponse,
    ControlListProjectionRow,
    ControlListProjectionScope,
    ControlListTrainingItem,
)
from app.directory.rbac import compute_scope
from app.security.admin_permissions import (
    CONTROL_LIST_EXPORT_PERMISSION,
    has_admin_permission,
)

CONTROL_LIST_SCHEMA_VERSION = "CONTROL_LIST_EXPORT_V1"
DEFAULT_ORGANIZATION_TIMEZONE = "Asia/Almaty"


class ControlListConfigurationError(RuntimeError):
    """The configured organization timezone is not a valid IANA zone."""


class ControlListAuthorizationError(PermissionError):
    """Stable, non-sensitive failure raised before projection data is read."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ControlListAssignmentConflict(RuntimeError):
    """Fail-closed result when the one-primary-assignment invariant is broken."""

    def __init__(self, detail: ControlListAssignmentConflictDetail) -> None:
        super().__init__(detail.message)
        self.detail = detail


def organization_timezone() -> tuple[str, ZoneInfo]:
    raw_name = os.getenv("ORGANIZATION_TIMEZONE")
    if raw_name is None:
        raw_name = env("ORGANIZATION_TIMEZONE", DEFAULT_ORGANIZATION_TIMEZONE)
    name = raw_name.strip() if isinstance(raw_name, str) else ""
    if not name:
        raise ControlListConfigurationError(
            "Organization timezone configuration is invalid."
        )
    try:
        return name, ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ControlListConfigurationError(
            "Organization timezone configuration is invalid."
        ) from exc


def _now(timezone: ZoneInfo) -> datetime:
    return datetime.now(timezone)


def _text_or_none(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).split())
    return normalized or None


def _required_text(value: Any, *, fallback: str = "") -> str:
    return _text_or_none(value) or fallback


def _sort_text(value: Any) -> str:
    return _required_text(value).casefold()


def _date_ascending(value: date | None) -> tuple[bool, date]:
    return value is None, value or date.max


def _date_descending(value: date | None) -> tuple[bool, int]:
    return value is None, -(value.toordinal()) if value is not None else 0


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _normalized_phone(value: Any) -> str | None:
    raw = _text_or_none(value)
    if raw is None:
        return None
    digits = "".join(character for character in raw if character.isdigit())
    if not digits:
        return None
    return digits


_BASE_QUERY = text(
    """
    /* control_list:base */
    WITH active_employees AS (
        SELECT
            e.employee_id,
            e.person_id,
            p.full_name,
            p.birth_date,
            p.iin
        FROM public.employees e
        JOIN public.persons p ON p.person_id = e.person_id
        WHERE COALESCE(e.is_active, TRUE) IS TRUE
          AND e.operational_status = 'active'
          AND (e.date_from IS NULL OR e.date_from <= :as_of_date)
          AND (e.date_to IS NULL OR e.date_to >= :as_of_date)
          AND p.person_status = 'active'
    ),
    current_primary_assignments AS (
        SELECT
            pa.assignment_id,
            pa.person_id,
            pa.org_unit_id,
            pa.position_id,
            pa.rate,
            pa.start_date
        FROM public.person_assignments pa
        WHERE pa.active_flag IS TRUE
          AND pa.is_primary IS TRUE
          AND pa.lifecycle_status = 'active'
          AND pa.start_date <= :as_of_date
          AND (pa.end_date IS NULL OR pa.end_date >= :as_of_date)
    ),
    scoped_employees AS (
        SELECT ae.*
        FROM active_employees ae
        WHERE :organization_wide IS TRUE
           OR EXISTS (
                SELECT 1
                FROM current_primary_assignments scoped_pa
                WHERE scoped_pa.person_id = ae.person_id
                  AND scoped_pa.org_unit_id = ANY(:scope_unit_ids)
           )
    )
    SELECT
        se.employee_id,
        se.person_id,
        se.full_name,
        se.birth_date,
        se.iin,
        pa.assignment_id,
        pa.org_unit_id,
        ou.name AS org_unit_name,
        ou.group_id,
        dg.group_name,
        pa.position_id,
        pos.name AS position_name,
        pos.category AS position_category,
        pa.rate,
        pa.start_date AS assignment_start_date
    FROM scoped_employees se
    LEFT JOIN current_primary_assignments pa ON pa.person_id = se.person_id
    LEFT JOIN public.org_units ou ON ou.unit_id = pa.org_unit_id
    LEFT JOIN public.deps_group dg ON dg.group_id = ou.group_id
    LEFT JOIN public.positions pos ON pos.position_id = pa.position_id
    ORDER BY se.employee_id, pa.assignment_id
    """
)

_EDUCATION_QUERY = text(
    """
    /* control_list:education */
    SELECT
        education_id,
        person_id,
        institution_name,
        specialty,
        started_at,
        completed_at
    FROM public.person_education
    WHERE person_id = ANY(:person_ids)
      AND lifecycle_status = 'active'
      AND verification_status = 'verified'
    """
)

_TRAINING_QUERY = text(
    """
    /* control_list:training */
    SELECT
        training_id,
        person_id,
        title,
        organization_name,
        hours,
        started_at,
        completed_at,
        certificate_number
    FROM public.person_training
    WHERE person_id = ANY(:person_ids)
      AND lifecycle_status = 'active'
      AND verification_status = 'verified'
    """
)

_CONTACT_QUERY = text(
    """
    /* control_list:contacts */
    SELECT contact_id, person_id, phone
    FROM public.contacts
    WHERE person_id = ANY(:person_ids)
      AND COALESCE(is_deleted, FALSE) IS FALSE
      AND NULLIF(BTRIM(phone), '') IS NOT NULL
    """
)

_ADDITIONAL_QUERY = text(
    """
    /* control_list:additional */
    SELECT person_id, additional_profile
    FROM public.personnel_record_metadata
    WHERE person_id = ANY(:person_ids)
      AND additional_profile IS NOT NULL
    """
)


def _group_base_rows(rows: Iterable[Mapping[str, Any]]) -> dict[int, list[Mapping[str, Any]]]:
    grouped: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[int(row["employee_id"])].append(row)
    return dict(grouped)


def _assignment_conflicts(
    grouped: Mapping[int, list[Mapping[str, Any]]],
) -> list[ControlListAssignmentConflictItem]:
    conflicts: list[ControlListAssignmentConflictItem] = []
    for employee_id in sorted(grouped):
        assignment_count = sum(
            1 for row in grouped[employee_id] if row.get("assignment_id") is not None
        )
        if assignment_count == 0:
            conflicts.append(
                ControlListAssignmentConflictItem(
                    employee_id=employee_id,
                    violation="MISSING_PRIMARY_ASSIGNMENT",
                )
            )
        elif assignment_count > 1:
            conflicts.append(
                ControlListAssignmentConflictItem(
                    employee_id=employee_id,
                    violation="MULTIPLE_PRIMARY_ASSIGNMENTS",
                )
            )
    return conflicts


def _education_by_person(
    rows: Iterable[Mapping[str, Any]],
) -> dict[int, list[ControlListEducationItem]]:
    grouped: dict[int, list[ControlListEducationItem]] = defaultdict(list)
    for row in rows:
        completed_at = row.get("completed_at")
        grouped[int(row["person_id"])].append(
            ControlListEducationItem(
                record_id=int(row["education_id"]),
                institution_name=_text_or_none(row.get("institution_name")),
                graduation_year=completed_at.year if isinstance(completed_at, date) else None,
                specialty=_text_or_none(row.get("specialty")),
                started_at=row.get("started_at"),
                completed_at=completed_at,
            )
        )
    for items in grouped.values():
        items.sort(
            key=lambda item: (
                _date_ascending(item.completed_at),
                _date_ascending(item.started_at),
                _sort_text(item.institution_name),
                item.record_id,
            )
        )
    return dict(grouped)


def _training_by_person(
    rows: Iterable[Mapping[str, Any]],
) -> dict[int, list[ControlListTrainingItem]]:
    grouped: dict[int, list[ControlListTrainingItem]] = defaultdict(list)
    for row in rows:
        grouped[int(row["person_id"])].append(
            ControlListTrainingItem(
                record_id=int(row["training_id"]),
                title=_text_or_none(row.get("title")),
                organization_name=_text_or_none(row.get("organization_name")),
                hours=row.get("hours"),
                started_at=row.get("started_at"),
                completed_at=row.get("completed_at"),
                certificate_number=_text_or_none(row.get("certificate_number")),
            )
        )
    for items in grouped.values():
        items.sort(
            key=lambda item: (
                _date_descending(item.completed_at),
                _date_descending(item.started_at),
                _sort_text(item.title),
                item.record_id,
            )
        )
    return dict(grouped)


def _phones_by_person(rows: Iterable[Mapping[str, Any]]) -> dict[int, list[ControlListPhoneItem]]:
    candidates: dict[int, list[tuple[str, int, str]]] = defaultdict(list)
    for row in rows:
        normalized = _normalized_phone(row.get("phone"))
        value = _text_or_none(row.get("phone"))
        if normalized is None or value is None:
            continue
        candidates[int(row["person_id"])].append(
            (normalized, int(row["contact_id"]), value)
        )

    result: dict[int, list[ControlListPhoneItem]] = {}
    for person_id, values in candidates.items():
        seen: set[str] = set()
        items: list[ControlListPhoneItem] = []
        for normalized, contact_id, value in sorted(values, key=lambda item: (item[0], item[1])):
            if normalized in seen:
                continue
            seen.add(normalized)
            items.append(ControlListPhoneItem(contact_id=contact_id, value=value))
        result[person_id] = items
    return result


def _profile_items(
    rows: Iterable[Mapping[str, Any]],
) -> tuple[
    dict[int, list[ControlListAcademicDegreeItem]],
    dict[int, list[ControlListAwardItem]],
    dict[int, bool],
    dict[int, bool],
]:
    degrees: dict[int, list[ControlListAcademicDegreeItem]] = {}
    awards: dict[int, list[ControlListAwardItem]] = {}
    degrees_none: dict[int, bool] = {}
    awards_none: dict[int, bool] = {}
    for row in rows:
        person_id = int(row["person_id"])
        profile = _json_object(row.get("additional_profile"))
        raw_degrees = profile.get("academic_degrees")
        raw_awards = profile.get("awards")
        degrees_none[person_id] = profile.get("academic_degrees_none") is True
        awards_none[person_id] = profile.get("awards_none") is True
        degrees[person_id] = [
            ControlListAcademicDegreeItem(
                ordinal=ordinal,
                degree=_text_or_none(item.get("degree")),
                degree_other=_text_or_none(item.get("degree_other")),
                field_of_science=_text_or_none(item.get("field_of_science")),
                completed_at=_text_or_none(item.get("completed_at")),
                document_number=_text_or_none(item.get("document_number")),
                label=_text_or_none(item.get("label")),
                degree_type=_text_or_none(item.get("degree_type")),
            )
            for ordinal, item in enumerate(raw_degrees if isinstance(raw_degrees, list) else [])
            if isinstance(item, dict)
        ]
        awards[person_id] = [
            ControlListAwardItem(
                ordinal=ordinal,
                category=_text_or_none(item.get("category")),
                name=_text_or_none(item.get("name") or item.get("title")),
                issued_by=_text_or_none(item.get("issued_by")),
                awarded_at=_text_or_none(item.get("awarded_at")),
                document_number=_text_or_none(item.get("document_number")),
            )
            for ordinal, item in enumerate(raw_awards if isinstance(raw_awards, list) else [])
            if isinstance(item, dict)
        ]
    return degrees, awards, degrees_none, awards_none


def _missing_fields(row: ControlListProjectionRow) -> list[str]:
    missing: list[str] = []
    for field_name in (
        "org_group",
        "birth_date",
        "iin",
        "position",
        "position_category",
        "employment_rate",
    ):
        if getattr(row, field_name) is None:
            missing.append(field_name)

    if not row.education:
        missing.extend(("education", "education_graduation_year", "diploma_specialty"))
    else:
        if all(item.institution_name is None for item in row.education):
            missing.append("education")
        if all(item.graduation_year is None for item in row.education):
            missing.append("education_graduation_year")
        if all(item.specialty is None for item in row.education):
            missing.append("diploma_specialty")
    if not row.training:
        missing.append("training")
    if not row.academic_degrees and not row.academic_degrees_none:
        missing.append("academic_degrees")
    if not row.awards and not row.awards_none:
        missing.append("awards")
    if not row.phones:
        missing.append("phones")
    return missing


def _build_control_list_projection(
    db_engine: Engine,
    *,
    initiator_user_id: int,
    scope_unit_ids: list[int] | None,
    clock: Callable[[ZoneInfo], datetime] = _now,
) -> ControlListProjectionResponse:
    """Build the complete projection or raise before returning any partial result.

    The query count is fixed at five for a non-empty valid projection, avoiding
    per-person section reads. ``None`` scope means organization-wide; an empty
    list means the caller has no visible organizational units.
    """

    timezone_name, timezone = organization_timezone()
    generated_at = clock(timezone)
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=timezone)
    else:
        generated_at = generated_at.astimezone(timezone)
    as_of_date = generated_at.date()
    normalized_scope = (
        None
        if scope_unit_ids is None
        else sorted({int(value) for value in scope_unit_ids})
    )
    metadata = ControlListProjectionMetadata(
        schema_version=CONTROL_LIST_SCHEMA_VERSION,
        as_of_date=as_of_date,
        generated_at=generated_at,
        timezone=timezone_name,
        initiator_user_id=int(initiator_user_id),
        scope=ControlListProjectionScope(
            organization_wide=normalized_scope is None,
            org_unit_ids=normalized_scope,
        ),
    )

    if normalized_scope == []:
        return ControlListProjectionResponse(metadata=metadata, total=0, items=[])

    params = {
        "as_of_date": as_of_date,
        "organization_wide": normalized_scope is None,
        "scope_unit_ids": normalized_scope or [],
    }
    with db_engine.connect() as conn:
        with conn.begin():
            conn.exec_driver_sql(
                "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
            )
            base_rows = conn.execute(_BASE_QUERY, params).mappings().all()
            grouped = _group_base_rows(base_rows)
            conflicts = _assignment_conflicts(grouped)
            if conflicts:
                raise ControlListAssignmentConflict(
                    ControlListAssignmentConflictDetail(
                        code="CONTROL_LIST_ASSIGNMENT_CONFLICT",
                        message="Active primary assignment invariant is violated.",
                        schema_version=CONTROL_LIST_SCHEMA_VERSION,
                        as_of_date=as_of_date,
                        conflicts=conflicts,
                    )
                )

            selected = [rows[0] for rows in grouped.values()]
            person_ids = sorted({int(row["person_id"]) for row in selected})
            if not person_ids:
                return ControlListProjectionResponse(metadata=metadata, total=0, items=[])

            collection_params = {"person_ids": person_ids}
            education = _education_by_person(
                conn.execute(_EDUCATION_QUERY, collection_params).mappings().all()
            )
            training = _training_by_person(
                conn.execute(_TRAINING_QUERY, collection_params).mappings().all()
            )
            phones = _phones_by_person(
                conn.execute(_CONTACT_QUERY, collection_params).mappings().all()
            )
            degrees, awards, degrees_none, awards_none = _profile_items(
                conn.execute(_ADDITIONAL_QUERY, collection_params).mappings().all()
            )

    items: list[ControlListProjectionRow] = []
    for base in selected:
        person_id = int(base["person_id"])
        item = ControlListProjectionRow(
            number=1,
            org_group=_text_or_none(base.get("group_name")),
            org_unit=_required_text(base.get("org_unit_name")),
            full_name=_required_text(base.get("full_name")),
            birth_date=base.get("birth_date"),
            iin=_text_or_none(base.get("iin")),
            position=_text_or_none(base.get("position_name")),
            position_category=_text_or_none(base.get("position_category")),
            employment_rate=(
                Decimal(str(base["rate"])) if base.get("rate") is not None else None
            ),
            assignment_start_date=base["assignment_start_date"],
            education=education.get(person_id, []),
            training=training.get(person_id, []),
            academic_degrees=degrees.get(person_id, []),
            academic_degrees_none=degrees_none.get(person_id, False),
            awards=awards.get(person_id, []),
            awards_none=awards_none.get(person_id, False),
            phones=phones.get(person_id, []),
            employee_id=int(base["employee_id"]),
        )
        item.missing_fields = _missing_fields(item)
        items.append(item)

    items.sort(
        key=lambda item: (
            item.org_group is None,
            _sort_text(item.org_group),
            _sort_text(item.org_unit),
            _sort_text(item.full_name),
            item.employee_id,
        )
    )
    for number, item in enumerate(items, start=1):
        item.number = number

    return ControlListProjectionResponse(metadata=metadata, total=len(items), items=items)


def build_control_list_projection(
    db_engine: Engine,
    *,
    user_context: Mapping[str, Any],
    clock: Callable[[ZoneInfo], datetime] = _now,
) -> ControlListProjectionResponse:
    """Authorize and build the internal projection for a current user.

    This is the only public service entry point. The full-IIN/full-phone
    projection cannot be built through it without the dedicated permission.
    """

    try:
        initiator_user_id = int(user_context["user_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ControlListAuthorizationError(
            "CONTROL_LIST_EXPORT_FORBIDDEN",
            "Control-list export permission is required.",
        ) from exc

    if not has_admin_permission(
        initiator_user_id,
        CONTROL_LIST_EXPORT_PERMISSION,
    ):
        raise ControlListAuthorizationError(
            "CONTROL_LIST_EXPORT_FORBIDDEN",
            "Control-list export permission is required.",
        )

    try:
        scope = compute_scope(
            initiator_user_id,
            dict(user_context),
            include_inactive=False,
        )
    except Exception as exc:
        raise ControlListAuthorizationError(
            "CONTROL_LIST_SCOPE_UNAVAILABLE",
            "Personnel scope could not be established.",
        ) from exc

    if not scope.get("privileged") and not scope.get("has_personnel_visibility"):
        raise ControlListAuthorizationError(
            "CONTROL_LIST_SCOPE_FORBIDDEN",
            "Personnel scope is not granted.",
        )

    return _build_control_list_projection(
        db_engine,
        initiator_user_id=initiator_user_id,
        scope_unit_ids=scope.get("scope_unit_ids"),
        clock=clock,
    )
