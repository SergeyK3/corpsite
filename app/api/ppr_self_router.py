"""Authenticated, self-owned PPR read endpoints.

This namespace is intentionally separate from ``/api/ppr/persons/*``: it is
not an alternative personnel-visibility path and accepts no subject ID.
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import text

from app.api.ppr_mappers import composite_to_response
from app.api.ppr_errors import map_ppr_mutation_error
from app.api.ppr_self_schemas import (
    PprSelfCardDataResponse,
    PprSelfCardResponse,
    PprSelfOperationalAssignmentDataResponse,
    PprSelfOperationalAssignmentResponse,
    SelfContactsCommand,
    SelfEducationCreateCommand,
    SelfEducationSupersedeCommand,
    SelfEducationVoidCommand,
    SelfExternalEmploymentCreateCommand,
    SelfExternalEmploymentSupersedeCommand,
    SelfExternalEmploymentVoidCommand,
    SelfForeignLanguagesCommand,
)
from app.auth import get_current_user
from app.db.engine import engine
from app.ppr.application.authorization import SelfPersonalCardAuthorizationAdapter
from app.ppr.application.command_models import MaterializePprPayload, PprCommandEnvelope
from app.ppr.application.config import assert_ppr_read_path_activation_allowed
from app.ppr.application.lifecycle_service import PprLifecycleApplicationService
from app.ppr.application.section_service import PprSectionApplicationService
from app.ppr.domain.errors import PprNotMaterializedError
from app.services.personnel_record_event_service import emit_personnel_record_event
from app.services.self_personal_card_access_service import SelfPersonalCardAccessService


router = APIRouter(prefix="/api/ppr", tags=["ppr-self"])
_self_access_service = SelfPersonalCardAccessService()
_SELF_AUDIT_SOURCE = "EMPLOYEE_SELF_SERVICE"


@router.get("/me", response_model=PprSelfCardResponse)
def get_my_ppr_card(
    user: dict[str, Any] = Depends(get_current_user),
) -> PprSelfCardResponse:
    """Read the caller's own card without personnel visibility or HR grants."""
    assert_ppr_read_path_activation_allowed()
    resolution = _self_access_service.resolve_for_user(user)
    if resolution.status != "READY" or resolution.composite is None:
        return PprSelfCardResponse(status=resolution.status)

    # Reuse canonical PPR mappers, but omit identity linkage, event history and
    # read metadata from the browser contract. Full IIN, status facts and
    # restricted military fields remain subject to the existing non-HR policy.
    mapped = composite_to_response(
        resolution.composite,
        read_mode="ppr_self",
        source="self_personal_card",
        include_sensitive_identity=False,
        include_military_restricted=False,
        include_status_facts=False,
    )
    return PprSelfCardResponse(
        status="READY",
        card=PprSelfCardDataResponse(
            materialization=mapped.materialization,
            general=mapped.general,
            sections=mapped.sections,
            additional=mapped.additional,
        ),
    )


@router.get("/me/operational-assignment", response_model=PprSelfOperationalAssignmentResponse)
def get_my_operational_assignment(
    user: dict[str, Any] = Depends(get_current_user),
) -> PprSelfOperationalAssignmentResponse:
    """Return the caller's current Employee assignment, resolved server-side.

    Unlike the personnel read API this deliberately does not invoke personnel
    visibility and does not look at ``person_assignments``.  The Employee ID is
    obtained solely through the self resolver and is never exposed in response.
    """
    assert_ppr_read_path_activation_allowed()
    resolution = _self_access_service.resolve_for_user(user)
    if resolution.status != "READY" or resolution.composite is None:
        return PprSelfOperationalAssignmentResponse(status=resolution.status)

    employee_id = int(resolution.composite.employee_id)
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT dg.group_name AS department_group_name,
                       ou.name AS org_unit_name,
                       pos.name AS position_name,
                       e.operational_status,
                       e.employment_rate,
                       (
                           SELECT ei.identity_value
                           FROM public.employee_identities ei
                           WHERE ei.employee_id = e.employee_id
                             AND ei.identity_type = 'IIN'
                             AND ei.valid_to IS NULL
                           ORDER BY ei.is_primary DESC, ei.identity_id ASC
                           LIMIT 1
                       ) AS iin
                FROM public.employees e
                LEFT JOIN public.org_units ou ON ou.unit_id = e.org_unit_id
                LEFT JOIN public.deps_group dg ON dg.group_id = ou.group_id
                LEFT JOIN public.positions pos ON pos.position_id = e.position_id
                WHERE e.employee_id = :employee_id
                """
            ),
            {"employee_id": employee_id},
        ).mappings().one_or_none()

    if row is None:
        # The resolver just established this link, so avoid leaking an internal
        # identifier if the operational row disappears concurrently.
        return PprSelfOperationalAssignmentResponse(status="IDENTITY_AMBIGUOUS")
    return PprSelfOperationalAssignmentResponse(
        status="READY",
        operational_assignment=PprSelfOperationalAssignmentDataResponse(
            department_group_name=row["department_group_name"],
            org_unit_name=row["org_unit_name"],
            position_name=row["position_name"],
            operational_status=row["operational_status"],
            employment_rate=float(row["employment_rate"]) if row["employment_rate"] is not None else None,
            iin=row["iin"],
        ),
    )


def _resolved_subject(user: dict[str, Any]):
    """Resolve the write subject exactly once, never from request data."""
    resolution = _self_access_service.resolve_for_user(user)
    if resolution.status != "READY" or resolution.composite is None:
        raise HTTPException(status_code=403, detail="Self personal card is unavailable")
    return int(resolution.composite.person_id), int(resolution.composite.employee_id)


def _section_service(user: dict[str, Any], person_id: int) -> PprSectionApplicationService:
    return PprSectionApplicationService(
        authorization=SelfPersonalCardAuthorizationAdapter(user, person_id=person_id),
    )


def _envelope(
    user: dict[str, Any], person_id: int, employee_id: int, body: Any, command_type: str, payload: dict[str, Any],
) -> PprCommandEnvelope:
    return PprCommandEnvelope(
        command_id=body.command_id,
        command_type=command_type,
        actor_id=str(user["user_id"]),
        requested_at=datetime.now(UTC),
        payload=payload,
        person_id=person_id,
        employee_context_id=employee_id,
        correlation_id=body.correlation_id,
        audit_source=_SELF_AUDIT_SOURCE,
    )


def _run_mutation(action):
    try:
        return action()
    except HTTPException:
        raise
    except Exception as exc:
        mapped = map_ppr_mutation_error(exc)
        if mapped is not None:
            raise mapped
        raise


def _materialize_then_retry(user: dict[str, Any], person_id: int, employee_id: int, body: Any, action):
    """Turn first self-edit into a controlled lifecycle flow, never raw 409."""
    try:
        return action()
    except PprNotMaterializedError:
        PprLifecycleApplicationService(authorization=SelfPersonalCardAuthorizationAdapter(user, person_id=person_id)).materialize_ppr(
            PprCommandEnvelope(command_id=f"{body.command_id}:materialize", command_type="MaterializePPR", actor_id=str(user["user_id"]), requested_at=datetime.now(UTC), payload=MaterializePprPayload(), person_id=person_id, employee_context_id=employee_id, correlation_id=body.correlation_id, audit_source=_SELF_AUDIT_SOURCE)
        )
        return action()
    except Exception as exc:
        mapped = map_ppr_mutation_error(exc)
        if mapped:
            raise mapped
        raise


def _clean(value: str | None) -> str | None:
    value = " ".join((value or "").split())
    return value or None


def _phone(value: str | None) -> str | None:
    value = _clean(value)
    if value is None:
        return None
    normalized = re.sub(r"[^0-9+]", "", value)
    digits = normalized[1:] if normalized.startswith("+") else normalized
    if len(digits) < 7 or len(digits) > 15:
        raise HTTPException(422, "Invalid mobile_phone")
    return "+" + digits


@router.get("/me/contacts")
def get_my_contacts(user: dict[str, Any] = Depends(get_current_user)):
    person_id, _ = _resolved_subject(user)
    with engine.connect() as conn:
        row = conn.execute(text("""SELECT mobile_phone,email,registration_address,residence_address,version,updated_at
            FROM person_contacts WHERE person_id=:person_id"""), {"person_id": person_id}).mappings().one_or_none()
    return {"canonical": dict(row) if row else None, "fallback": None}


@router.put("/me/contacts")
def save_my_contacts(body: SelfContactsCommand, user: dict[str, Any] = Depends(get_current_user)):
    person_id, employee_id = _resolved_subject(user)
    after = {
        "mobile_phone": _phone(body.mobile_phone),
        "email": str(body.email).lower() if body.email else None,
        "registration_address": _clean(body.registration_address),
        "residence_address": _clean(body.residence_address),
    }
    if not any(after.values()):
        raise HTTPException(422, "At least one contact value is required")
    with engine.begin() as conn:
        replay = conn.execute(text("""SELECT event_payload FROM personnel_record_events
            WHERE person_id=:person_id AND event_type='PPR_CONTACTS_SELF_UPDATED'
              AND event_payload->>'command_id'=:command_id ORDER BY event_id DESC LIMIT 1"""),
            {"person_id": person_id, "command_id": body.command_id}).mappings().one_or_none()
        if replay:
            payload = dict(replay["event_payload"] or {})
            if payload.get("after") != after:
                raise HTTPException(409, "command_id was already used with another payload")
            return {**after, "version": payload.get("version"), "updated_at": payload.get("updated_at"), "idempotent": True}
        before = conn.execute(text("""SELECT mobile_phone,email,registration_address,residence_address,version
            FROM person_contacts WHERE person_id=:person_id FOR UPDATE"""), {"person_id": person_id}).mappings().one_or_none()
        if before and body.expected_version != int(before["version"]):
            raise HTTPException(409, "Contacts were changed; reload the card")
        if not before and body.expected_version not in (None, 0):
            raise HTTPException(409, "Contacts were created; reload the card")
        row = conn.execute(text("""INSERT INTO person_contacts(person_id,mobile_phone,email,registration_address,residence_address,version,created_by_user_id,updated_by_user_id)
            VALUES(:person_id,:mobile_phone,:email,:registration_address,:residence_address,1,:user_id,:user_id)
            ON CONFLICT(person_id) DO UPDATE SET mobile_phone=EXCLUDED.mobile_phone,email=EXCLUDED.email,
            registration_address=EXCLUDED.registration_address,residence_address=EXCLUDED.residence_address,
            version=person_contacts.version+1,updated_at=now(),updated_by_user_id=:user_id RETURNING version,updated_at"""),
            {"person_id": person_id, "user_id": int(user["user_id"]), **after}).mappings().one()
        payload = {"section": "contacts", "action": "upsert", "before": dict(before) if before else None,
                   "after": after, "command_id": body.command_id, "correlation_id": body.correlation_id,
                   "source": _SELF_AUDIT_SOURCE, "version": row["version"], "updated_at": row["updated_at"].isoformat()}
        emit_personnel_record_event(conn, person_id=person_id, employee_context_id=employee_id, domain_code="general_information",
            record_table_name="person_contacts", record_id=person_id, event_type="PPR_CONTACTS_SELF_UPDATED",
            actor_id=str(user["user_id"]), event_payload=payload)
    return {**after, "version": row["version"], "updated_at": row["updated_at"], "idempotent": False}


@router.post("/me/education/records")
def add_my_education(body: SelfEducationCreateCommand, user: dict[str, Any] = Depends(get_current_user)):
    person_id, employee_id = _resolved_subject(user)
    return _run_mutation(lambda: _materialize_then_retry(user, person_id, employee_id, body, lambda: _section_service(user, person_id).add_education(
        _envelope(user, person_id, employee_id, body, "SelfAddEducation", body.record.model_dump()))))


@router.post("/me/education/records/{record_id}/supersede")
def supersede_my_education(record_id: int = Path(ge=1), body: SelfEducationSupersedeCommand = None, user: dict[str, Any] = Depends(get_current_user)):
    person_id, employee_id = _resolved_subject(user)
    return _run_mutation(lambda: _section_service(user, person_id).supersede_education(
        _envelope(user, person_id, employee_id, body, "SelfSupersedeEducation", {"record_id": record_id, "expected_updated_at": body.expected_updated_at, "replacement": body.replacement.model_dump()})))


@router.post("/me/education/records/{record_id}/void")
def void_my_education(record_id: int = Path(ge=1), body: SelfEducationVoidCommand = None, user: dict[str, Any] = Depends(get_current_user)):
    person_id, employee_id = _resolved_subject(user)
    return _run_mutation(lambda: _section_service(user, person_id).void_education(
        _envelope(user, person_id, employee_id, body, "SelfVoidEducation", {"record_id": record_id, "expected_updated_at": body.expected_updated_at, "reason": body.reason})))


@router.post("/me/employment-biography/records")
def add_my_external_employment(body: SelfExternalEmploymentCreateCommand, user: dict[str, Any] = Depends(get_current_user)):
    """Create employee-owned external employment history, resolved from session only."""
    person_id, employee_id = _resolved_subject(user)
    result = _run_mutation(lambda: _section_service(user, person_id).add_external_employment(
        _envelope(user, person_id, employee_id, body, "SelfAddExternalEmployment", body.record.model_dump())))
    # Do not expose the resolved Person/Employee identifiers from the canonical result.
    return {"status": result.status, "command_id": body.command_id, "section": "employment_biography"}


@router.post("/me/employment-biography/records/{record_id}/supersede")
def supersede_my_external_employment(
    record_id: int = Path(ge=1),
    body: SelfExternalEmploymentSupersedeCommand = None,
    user: dict[str, Any] = Depends(get_current_user),
):
    """Create a versioned self-service replacement; never update the prior row in place."""
    person_id, employee_id = _resolved_subject(user)
    result = _run_mutation(lambda: _section_service(user, person_id).supersede_external_employment(
        _envelope(user, person_id, employee_id, body, "SelfSupersedeExternalEmployment", {
            "record_id": record_id,
            "expected_updated_at": body.expected_updated_at,
            "replacement": body.replacement.model_dump(),
        })))
    return {"status": result.status, "command_id": body.command_id, "section": "employment_biography"}


@router.post("/me/employment-biography/records/{record_id}/void")
def void_my_external_employment(record_id: int = Path(ge=1), body: SelfExternalEmploymentVoidCommand = None, user: dict[str, Any] = Depends(get_current_user)):
    person_id, employee_id = _resolved_subject(user)
    result = _run_mutation(lambda: _section_service(user, person_id).void_external_employment(
        _envelope(user, person_id, employee_id, body, "SelfVoidExternalEmployment", {"record_id": record_id, "expected_updated_at": body.expected_updated_at, "reason": body.reason})))
    return {"status": result.status, "command_id": body.command_id, "section": "employment_biography"}


@router.get("/me/foreign-languages")
def get_my_foreign_languages(user: dict[str, Any] = Depends(get_current_user)):
    person_id, _ = _resolved_subject(user)
    with engine.connect() as conn:
        row = conn.execute(text("SELECT additional_profile,updated_at FROM personnel_record_metadata WHERE person_id=:person_id"), {"person_id": person_id}).mappings().one_or_none()
    profile = dict((row or {}).get("additional_profile") or {})
    return {"foreign_languages": profile.get("foreign_languages", []), "updated_at": (row or {}).get("updated_at")}


@router.put("/me/foreign-languages")
def save_my_foreign_languages(body: SelfForeignLanguagesCommand, user: dict[str, Any] = Depends(get_current_user)):
    person_id, employee_id = _resolved_subject(user)
    after = [item.model_dump() for item in body.foreign_languages]
    keys = [item["language"].casefold() for item in after]
    if len(keys) != len(set(keys)):
        raise HTTPException(422, "Duplicate foreign language")
    with engine.begin() as conn:
        replay = conn.execute(text("""SELECT event_payload FROM personnel_record_events WHERE person_id=:person_id
            AND event_type='PPR_FOREIGN_LANGUAGES_SELF_UPDATED' AND event_payload->>'command_id'=:command_id
            ORDER BY event_id DESC LIMIT 1"""), {"person_id": person_id, "command_id": body.command_id}).mappings().one_or_none()
        if replay:
            payload = dict(replay["event_payload"] or {})
            if payload.get("after") != after:
                raise HTTPException(409, "command_id was already used with another payload")
            return {"foreign_languages": after, "updated_at": payload.get("updated_at"), "idempotent": True}
        row = conn.execute(text("SELECT additional_profile,updated_at FROM personnel_record_metadata WHERE person_id=:person_id FOR UPDATE"), {"person_id": person_id}).mappings().one_or_none()
        if row and body.expected_updated_at and body.expected_updated_at != row["updated_at"]:
            raise HTTPException(409, "Foreign languages were changed; reload the card")
        if not row and body.expected_updated_at is not None:
            raise HTTPException(409, "Foreign languages were created; reload the card")
        profile = dict(row["additional_profile"] or {}) if row else {}
        before = profile.get("foreign_languages", [])
        profile["foreign_languages"] = after
        profile["foreign_languages_none"] = not after
        updated = conn.execute(text("""INSERT INTO personnel_record_metadata(person_id,additional_profile) VALUES(:person_id,CAST(:profile AS jsonb))
            ON CONFLICT(person_id) DO UPDATE SET additional_profile=EXCLUDED.additional_profile,updated_at=now() RETURNING updated_at"""),
            {"person_id": person_id, "profile": json.dumps(profile, ensure_ascii=False)}).scalar_one()
        emit_personnel_record_event(conn, person_id=person_id, employee_context_id=employee_id, domain_code="general_information",
            record_table_name="personnel_record_metadata", record_id=person_id, event_type="PPR_FOREIGN_LANGUAGES_SELF_UPDATED",
            actor_id=str(user["user_id"]), event_payload={"section": "foreign_languages", "action": "replace", "before": before, "after": after,
            "command_id": body.command_id, "correlation_id": body.correlation_id, "source": _SELF_AUDIT_SOURCE, "updated_at": updated.isoformat()})
    return {"foreign_languages": after, "updated_at": updated, "idempotent": False}
