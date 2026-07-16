"""HTTP adapter for PPR employment biography mutations (WP-PR-016)."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.api.ppr_command_schemas import (
    PprCommandMutationResponse,
    PprExternalEmploymentCreateRequest,
    PprExternalEmploymentSupersedeRequest,
    PprExternalEmploymentVoidRequest,
)
from app.ppr.application.authorization import HrImportAdminAuthorizationAdapter
from app.ppr.application.command_models import (
    COMMAND_TYPE_ADD_EXTERNAL_EMPLOYMENT,
    COMMAND_TYPE_SUPERSEDE_EXTERNAL_EMPLOYMENT,
    COMMAND_TYPE_VOID_EXTERNAL_EMPLOYMENT,
    PprCommandEnvelope,
)
from app.ppr.application.command_service import PprCommandApplicationService
from app.ppr.application.results import PprApplicationResult
from app.ppr.application.section_service import PprSectionApplicationService
from app.ppr.domain.section_models import SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY


def _command_service(user_ctx: dict[str, Any]) -> PprCommandApplicationService:
    return PprSectionApplicationService(authorization=HrImportAdminAuthorizationAdapter(user_ctx))


def _actor_id(user_ctx: dict[str, Any]) -> str:
    uid = user_ctx.get("user_id") or user_ctx.get("id")
    if uid is None:
        raise ValueError("Authenticated user id is required.")
    return str(uid)


def _envelope(
    *,
    user_ctx: dict[str, Any],
    body_command_id: str,
    command_type: str,
    payload: dict[str, Any],
    correlation_id: str | None,
    person_id: int | None = None,
    employee_id: int | None = None,
) -> PprCommandEnvelope:
    return PprCommandEnvelope(
        command_id=body_command_id,
        command_type=command_type,
        actor_id=_actor_id(user_ctx),
        requested_at=datetime.now(UTC),
        payload=payload,
        person_id=person_id,
        employee_id=employee_id,
        correlation_id=correlation_id,
    )


def _to_response(result: PprApplicationResult) -> PprCommandMutationResponse:
    return PprCommandMutationResponse(
        command_id=result.command_id,
        command_type=result.command_type,
        status=result.status,
        resolved_person_id=result.resolved_person_id,
        section_code=SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY,
        section_record_id=result.section_record_id,
        section_mutation_kind=result.section_mutation_kind,
        event_ids=list(result.event_ids),
        envelope_version=result.envelope_version,
        correlation_id=result.correlation_id,
    )


def create_external_employment_by_person(
    user_ctx: dict[str, Any],
    *,
    person_id: int,
    body: PprExternalEmploymentCreateRequest,
) -> PprCommandMutationResponse:
    service = _command_service(user_ctx)
    envelope = _envelope(
        user_ctx=user_ctx,
        body_command_id=body.command_id,
        command_type=COMMAND_TYPE_ADD_EXTERNAL_EMPLOYMENT,
        payload=body.record.model_dump(),
        correlation_id=body.correlation_id,
        person_id=person_id,
    )
    result = service.add_external_employment(envelope)  # type: ignore[attr-defined]
    return _to_response(result)


def create_external_employment_by_employee(
    user_ctx: dict[str, Any],
    *,
    employee_id: int,
    body: PprExternalEmploymentCreateRequest,
) -> PprCommandMutationResponse:
    service = _command_service(user_ctx)
    envelope = _envelope(
        user_ctx=user_ctx,
        body_command_id=body.command_id,
        command_type=COMMAND_TYPE_ADD_EXTERNAL_EMPLOYMENT,
        payload=body.record.model_dump(),
        correlation_id=body.correlation_id,
        employee_id=employee_id,
    )
    result = service.add_external_employment(envelope)  # type: ignore[attr-defined]
    return _to_response(result)


def void_external_employment_by_person(
    user_ctx: dict[str, Any],
    *,
    person_id: int,
    record_id: int,
    body: PprExternalEmploymentVoidRequest,
) -> PprCommandMutationResponse:
    service = _command_service(user_ctx)
    envelope = _envelope(
        user_ctx=user_ctx,
        body_command_id=body.command_id,
        command_type=COMMAND_TYPE_VOID_EXTERNAL_EMPLOYMENT,
        payload={
            "record_id": record_id,
            "reason": body.reason,
            "expected_updated_at": body.expected_updated_at,
        },
        correlation_id=body.correlation_id,
        person_id=person_id,
    )
    result = service.void_external_employment(envelope)  # type: ignore[attr-defined]
    return _to_response(result)


def void_external_employment_by_employee(
    user_ctx: dict[str, Any],
    *,
    employee_id: int,
    record_id: int,
    body: PprExternalEmploymentVoidRequest,
) -> PprCommandMutationResponse:
    service = _command_service(user_ctx)
    envelope = _envelope(
        user_ctx=user_ctx,
        body_command_id=body.command_id,
        command_type=COMMAND_TYPE_VOID_EXTERNAL_EMPLOYMENT,
        payload={
            "record_id": record_id,
            "reason": body.reason,
            "expected_updated_at": body.expected_updated_at,
        },
        correlation_id=body.correlation_id,
        employee_id=employee_id,
    )
    result = service.void_external_employment(envelope)  # type: ignore[attr-defined]
    return _to_response(result)


def supersede_external_employment_by_person(
    user_ctx: dict[str, Any],
    *,
    person_id: int,
    record_id: int,
    body: PprExternalEmploymentSupersedeRequest,
) -> PprCommandMutationResponse:
    service = _command_service(user_ctx)
    envelope = _envelope(
        user_ctx=user_ctx,
        body_command_id=body.command_id,
        command_type=COMMAND_TYPE_SUPERSEDE_EXTERNAL_EMPLOYMENT,
        payload={
            "record_id": record_id,
            "expected_updated_at": body.expected_updated_at,
            "replacement": body.replacement.model_dump(),
        },
        correlation_id=body.correlation_id,
        person_id=person_id,
    )
    result = service.supersede_external_employment(envelope)  # type: ignore[attr-defined]
    return _to_response(result)


def supersede_external_employment_by_employee(
    user_ctx: dict[str, Any],
    *,
    employee_id: int,
    record_id: int,
    body: PprExternalEmploymentSupersedeRequest,
) -> PprCommandMutationResponse:
    service = _command_service(user_ctx)
    envelope = _envelope(
        user_ctx=user_ctx,
        body_command_id=body.command_id,
        command_type=COMMAND_TYPE_SUPERSEDE_EXTERNAL_EMPLOYMENT,
        payload={
            "record_id": record_id,
            "expected_updated_at": body.expected_updated_at,
            "replacement": body.replacement.model_dump(),
        },
        correlation_id=body.correlation_id,
        employee_id=employee_id,
    )
    result = service.supersede_external_employment(envelope)  # type: ignore[attr-defined]
    return _to_response(result)
