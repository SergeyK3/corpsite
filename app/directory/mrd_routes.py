"""Monthly Reference Dataset REST API (WP-MRD-004)."""
from __future__ import annotations

from datetime import date
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.auth import get_current_user
from app.db.engine import engine
from app.directory.common import as_http500
from app.directory.mrd_command_api import (
    fetch_active_mrd,
    fetch_all_versions,
    fetch_fork_sources,
    fetch_period_versions,
    fork_result_to_dict,
    run_fork_period,
    run_fork_version,
)
from app.directory.mrd_errors import map_mrd_error
from app.directory.mrd_schemas import (
    ActiveMrdResponse,
    CreationWindowResponse,
    ForkMutationResponse,
    ForkMutationResult,
    ForkPeriodRequest,
    ForkSourcesResponse,
    ForkVersionRequest,
    MonthlyReferenceListResponse,
    MrdWorkspaceResponse,
    HrReviewResponse,
)
from app.mrd.application.hr_review_service import fetch_hr_review, hr_review_to_dict
from app.mrd.application.workspace_service import fetch_creation_window, fetch_mrd_workspace, workspace_to_dict
from app.directory.rbac import require_personnel_admin_or_403
from app.mrd.infrastructure.repository import mrd_tables_available

router = APIRouter()


def _require_mrd_schema(conn) -> None:
    if not mrd_tables_available(conn):
        raise HTTPException(status_code=503, detail="MRD schema is not available")


def _with_conn(fn: Callable, /, **kwargs):
    with engine.begin() as conn:
        _require_mrd_schema(conn)
        return fn(conn, **kwargs)


def _user_id(user: dict[str, Any]) -> int:
    return int(user["user_id"])


def _parse_report_period(value: str) -> date:
    raw = value.strip()
    if len(raw) == 7 and raw[4] == "-":
        return date.fromisoformat(f"{raw}-01")
    return date.fromisoformat(raw)


def _run_mutation(handler: Callable[[], tuple[str, Any]], *, response: Response) -> ForkMutationResponse:
    try:
        mutation_status, result = handler()
        response.status_code = (
            status.HTTP_200_OK
            if mutation_status == "idempotent_replay"
            else status.HTTP_201_CREATED
        )
        return ForkMutationResponse(
            status=mutation_status,
            result=ForkMutationResult(**fork_result_to_dict(result)),
        )
    except HTTPException:
        raise
    except Exception as exc:
        mapped = map_mrd_error(exc)
        if mapped is not None:
            raise mapped
        raise as_http500(exc)


@router.get("/personnel/monthly-references/creation-window", response_model=CreationWindowResponse)
def get_monthly_reference_creation_window(
    user: dict[str, Any] = Depends(get_current_user),
) -> CreationWindowResponse:
    require_personnel_admin_or_403(user)
    payload = _with_conn(fetch_creation_window)
    return CreationWindowResponse.model_validate(payload)


@router.get("/personnel/monthly-references/{mrd_id}/hr-review", response_model=HrReviewResponse)
def get_monthly_reference_hr_review(
    mrd_id: int,
    org_group_id: int | None = Query(default=None, ge=1),
    effective_log_group: str | None = Query(default=None),
    org_unit_id: int | None = Query(default=None, ge=1),
    changed_only: bool = Query(default=True),
    search: str | None = Query(default=None),
    review_status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: dict[str, Any] = Depends(get_current_user),
) -> HrReviewResponse:
    require_personnel_admin_or_403(user)

    def _handler(conn):
        snapshot = fetch_hr_review(
            conn,
            mrd_id=mrd_id,
            org_group_id=org_group_id,
            effective_log_group=effective_log_group,
            org_unit_id=org_unit_id,
            changed_only=changed_only,
            search=search,
            review_status=review_status,
            limit=limit,
            offset=offset,
        )
        return hr_review_to_dict(snapshot)

    try:
        payload = _with_conn(_handler)
        return HrReviewResponse.model_validate(payload)
    except HTTPException:
        raise
    except Exception as exc:
        mapped = map_mrd_error(exc)
        if mapped is not None:
            raise mapped
        raise as_http500(exc)


@router.get("/personnel/monthly-references/{mrd_id}/workspace", response_model=MrdWorkspaceResponse)
def get_monthly_reference_workspace(
    mrd_id: int,
    entries_limit: int = Query(default=50, ge=1, le=200),
    entries_offset: int = Query(default=0, ge=0),
    confirmed_limit: int = Query(default=20, ge=0, le=200),
    confirmed_offset: int = Query(default=0, ge=0),
    user: dict[str, Any] = Depends(get_current_user),
) -> MrdWorkspaceResponse:
    require_personnel_admin_or_403(user)

    def _handler(conn):
        snapshot = fetch_mrd_workspace(
            conn,
            mrd_id=mrd_id,
            entries_limit=entries_limit,
            entries_offset=entries_offset,
            confirmed_limit=confirmed_limit,
            confirmed_offset=confirmed_offset,
        )
        return workspace_to_dict(snapshot)

    try:
        payload = _with_conn(_handler)
        return MrdWorkspaceResponse.model_validate(payload)
    except HTTPException:
        raise
    except Exception as exc:
        mapped = map_mrd_error(exc)
        if mapped is not None:
            raise mapped
        raise as_http500(exc)


@router.get("/personnel/monthly-references/active", response_model=ActiveMrdResponse)
def get_active_monthly_reference(
    report_period: str = Query(..., description="Report period YYYY-MM or YYYY-MM-DD"),
    user: dict[str, Any] = Depends(get_current_user),
) -> ActiveMrdResponse:
    require_personnel_admin_or_403(user)
    period = _parse_report_period(report_period)
    payload = _with_conn(fetch_active_mrd, report_period=period)
    return ActiveMrdResponse.model_validate(payload)


@router.get("/personnel/monthly-references", response_model=MonthlyReferenceListResponse)
def list_monthly_references(
    report_period: str | None = Query(default=None),
    user: dict[str, Any] = Depends(get_current_user),
) -> MonthlyReferenceListResponse:
    require_personnel_admin_or_403(user)
    if report_period:
        period = _parse_report_period(report_period)
        payload = _with_conn(fetch_period_versions, report_period=period)
    else:
        payload = _with_conn(fetch_all_versions)
    return MonthlyReferenceListResponse.model_validate(payload)


@router.get("/personnel/monthly-references/fork-sources", response_model=ForkSourcesResponse)
def list_monthly_reference_fork_sources(
    user: dict[str, Any] = Depends(get_current_user),
) -> ForkSourcesResponse:
    require_personnel_admin_or_403(user)
    payload = _with_conn(fetch_fork_sources)
    return ForkSourcesResponse.model_validate(payload)


@router.post("/personnel/monthly-references/fork-version", response_model=ForkMutationResponse)
def fork_monthly_reference_version(
    body: ForkVersionRequest,
    response: Response,
    user: dict[str, Any] = Depends(get_current_user),
) -> ForkMutationResponse:
    require_personnel_admin_or_403(user)
    performed_by = _user_id(user)

    def _handler():
        with engine.begin() as conn:
            _require_mrd_schema(conn)
            return run_fork_version(
                conn,
                command_id=body.command_id,
                source_mrd_id=body.source_mrd_id,
                performed_by=performed_by,
                expected_active_row_version=body.expected_active_row_version,
                notes=body.notes,
            )

    return _run_mutation(_handler, response=response)


@router.post("/personnel/monthly-references/fork-period", response_model=ForkMutationResponse)
def fork_monthly_reference_period(
    body: ForkPeriodRequest,
    response: Response,
    user: dict[str, Any] = Depends(get_current_user),
) -> ForkMutationResponse:
    require_personnel_admin_or_403(user)
    performed_by = _user_id(user)

    def _handler():
        with engine.begin() as conn:
            _require_mrd_schema(conn)
            return run_fork_period(
                conn,
                command_id=body.command_id,
                source_mrd_id=body.source_mrd_id,
                target_report_period=body.target_report_period,
                performed_by=performed_by,
                notes=body.notes,
            )

    return _run_mutation(_handler, response=response)
