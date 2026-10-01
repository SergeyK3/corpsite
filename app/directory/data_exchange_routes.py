"""Registered, auditable import/export API.

This is intentionally separate from the legacy control-list import API.  A
package is only data until its registered scenario completes preview, dry-run
and an echoed confirmation.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.auth import get_current_user
from app.data_exchange.order_scenario import build_employee_reference_workbook
from app.data_exchange.permissions import (
    DATA_EXCHANGE_CONFIRM_APPLY,
    DATA_EXCHANGE_DRY_RUN,
    DATA_EXCHANGE_EXPORT_REFERENCE,
    DATA_EXCHANGE_UPLOAD_PREVIEW,
    DATA_EXCHANGE_VIEW,
    require_exchange_permission,
)
from app.data_exchange.service import (
    ExchangeConflict,
    ExchangeError,
    apply_package,
    cancel_package,
    confirm_package,
    dry_run_package,
    list_scenarios,
    mark_failed,
    preview_package,
    upload_package,
)
from app.db.engine import engine
from app.directory.rbac import compute_scope, require_personnel_visibility_or_403

router = APIRouter(prefix="/personnel/data-exchange", tags=["data-exchange"])
_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class UploadMetadata(BaseModel):
    scenario_code: str = Field(..., min_length=1, max_length=100)


class Confirmation(BaseModel):
    expected_sha256: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    expected_schema_version: str = Field(..., min_length=1, max_length=100)
    expected_target_fingerprint: str = Field(..., pattern=r"^[0-9a-f]{64}$")


def _actor(user: dict[str, Any]) -> int:
    try:
        value = int(user["user_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Authenticated user is required.") from exc
    if value <= 0:
        raise HTTPException(status_code=401, detail="Authenticated user is required.")
    return value


def _raise_exchange(exc: ExchangeError) -> None:
    status = 409 if isinstance(exc, ExchangeConflict) else 400
    # Scenario messages deliberately contain no values from the uploaded file.
    raise HTTPException(status_code=status, detail=str(exc)) from exc


def _scope(user: dict[str, Any]) -> set[int] | None:
    """Resolve the same organisational perimeter used by personnel APIs."""
    scope = compute_scope(_actor(user), user, include_inactive=False)
    require_personnel_visibility_or_403(user, scope)
    units = scope.get("scope_unit_ids")
    return None if units is None else {int(value) for value in units}


def _record_unexpected_failure(package_id: int, user: dict[str, Any], stage: str) -> None:
    try:
        with engine.begin() as conn:
            mark_failed(conn, package_id=package_id, actor_user_id=_actor(user), stage=stage)
    except Exception:
        # Do not substitute an audit/storage exception for the original error.
        pass


@router.get("/scenarios")
def get_scenarios(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    require_exchange_permission(user, DATA_EXCHANGE_VIEW)
    return {"items": list_scenarios()}


@router.post("/packages")
async def post_package(
    scenario_code: str,
    file: UploadFile = File(...),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_exchange_permission(user, DATA_EXCHANGE_UPLOAD_PREVIEW)
    # UploadFile is streamed by Starlette; the registered size ceiling is
    # rechecked before storing bytes in the database.
    try:
        content = await file.read(25 * 1024 * 1024 + 1)
        with engine.begin() as conn:
            return upload_package(
                conn, scenario_code=scenario_code, filename=file.filename or "",
                content=content, media_type=file.content_type, actor_user_id=_actor(user),
            )
    except ExchangeError as exc:
        _raise_exchange(exc)


@router.post("/packages/{package_id}/preview")
def post_preview(package_id: int, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    require_exchange_permission(user, DATA_EXCHANGE_UPLOAD_PREVIEW)
    try:
        with engine.begin() as conn:
            return preview_package(conn, package_id=package_id, actor_user_id=_actor(user), scope_unit_ids=_scope(user))
    except ExchangeError as exc:
        _raise_exchange(exc)
    except Exception as exc:
        _record_unexpected_failure(package_id, user, "PREVIEW")
        raise HTTPException(status_code=500, detail="Package preview failed.") from exc


@router.post("/packages/{package_id}/dry-run")
def post_dry_run(package_id: int, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    require_exchange_permission(user, DATA_EXCHANGE_DRY_RUN)
    try:
        with engine.begin() as conn:
            return dry_run_package(conn, package_id=package_id, actor_user_id=_actor(user), scope_unit_ids=_scope(user))
    except ExchangeError as exc:
        _raise_exchange(exc)
    except Exception as exc:
        _record_unexpected_failure(package_id, user, "DRY_RUN")
        raise HTTPException(status_code=500, detail="Package dry-run failed.") from exc


@router.post("/packages/{package_id}/confirm")
def post_confirm(
    package_id: int, body: Confirmation = Body(...), user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_exchange_permission(user, DATA_EXCHANGE_CONFIRM_APPLY)
    try:
        with engine.begin() as conn:
            return confirm_package(conn, package_id=package_id, actor_user_id=_actor(user), **body.model_dump())
    except ExchangeError as exc:
        _raise_exchange(exc)
    except Exception as exc:
        _record_unexpected_failure(package_id, user, "CONFIRM")
        raise HTTPException(status_code=500, detail="Package confirmation failed.") from exc


@router.post("/packages/{package_id}/apply")
def post_apply(package_id: int, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    require_exchange_permission(user, DATA_EXCHANGE_CONFIRM_APPLY)
    try:
        with engine.begin() as conn:
            return apply_package(conn, package_id=package_id, actor_user_id=_actor(user), scope_unit_ids=_scope(user))
    except ExchangeError as exc:
        _raise_exchange(exc)
    except Exception as exc:
        _record_unexpected_failure(package_id, user, "APPLY")
        raise HTTPException(status_code=500, detail="Package apply failed.") from exc


@router.post("/packages/{package_id}/cancel")
def post_cancel(package_id: int, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    require_exchange_permission(user, DATA_EXCHANGE_UPLOAD_PREVIEW)
    try:
        with engine.begin() as conn:
            return cancel_package(conn, package_id=package_id, actor_user_id=_actor(user))
    except ExchangeError as exc:
        _raise_exchange(exc)


@router.get("/employee-reference", response_class=Response)
def get_employee_reference(user: dict[str, Any] = Depends(get_current_user)) -> Response:
    require_exchange_permission(user, DATA_EXCHANGE_EXPORT_REFERENCE)
    with engine.connect() as conn:
        content = build_employee_reference_workbook(conn, scope_unit_ids=_scope(user))
    return Response(
        content=content, media_type=_XLSX,
        headers={
            "Content-Disposition": 'attachment; filename="corpsite_employee_reference.xlsx"',
            "Cache-Control": "private, no-store, max-age=0",
            "X-Content-Type-Options": "nosniff",
        },
    )
