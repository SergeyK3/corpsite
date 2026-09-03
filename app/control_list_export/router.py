"""Single safe download endpoint for the control-list XLSX export."""
from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.auth import get_current_user
from app.control_list_export.audit import (
    ControlListAuditScope,
    ControlListExportAuditResult,
    write_control_list_export_audit,
)
from app.db.engine import engine
from app.directory.rbac import compute_scope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/personnel/control-list", tags=["control-list-export"])

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_SCHEMA_VERSION = "CONTROL_LIST_EXPORT_V1"
_XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_SECURITY_HEADERS = {
    "Cache-Control": "private, no-store, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
    "X-Content-Type-Options": "nosniff",
}


def _request_id(request: Request) -> str:
    candidate = (request.headers.get("x-request-id") or "").strip()
    return candidate if _REQUEST_ID_PATTERN.fullmatch(candidate) else uuid4().hex


def _headers(request_id: str) -> dict[str, str]:
    return {**_SECURITY_HEADERS, "X-Request-ID": request_id}


def _content_disposition(filename: str, *, ascii_filename: str) -> str:
    return (
        f'attachment; filename="{ascii_filename}"; '
        f"filename*=UTF-8''{quote(filename, safe='')}"
    )


def _actor_user_id(user: dict[str, Any]) -> int | None:
    try:
        value = int(user["user_id"])
    except (KeyError, TypeError, ValueError):
        return None
    return value if value > 0 else None


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client is not None else None


def build_control_list_projection(*args, **kwargs):
    """Lazy call boundary avoiding a directory/projection import cycle."""

    from app.control_list_projection import build_control_list_projection as implementation

    return implementation(*args, **kwargs)


def build_control_list_workbook(*args, **kwargs):
    """Lazy call boundary avoiding a directory/projection import cycle."""

    from app.control_list_export.workbook import build_control_list_workbook as implementation

    return implementation(*args, **kwargs)


def _resolved_scope_for_audit(user: dict[str, Any]) -> ControlListAuditScope:
    """Resolve scope only for auditing an already-authorized failed operation."""

    actor_user_id = _actor_user_id(user)
    if actor_user_id is None:
        return ControlListAuditScope.unresolved()
    try:
        raw_scope = compute_scope(actor_user_id, user, include_inactive=False)
        if not raw_scope.get("privileged") and not raw_scope.get(
            "has_personnel_visibility"
        ):
            return ControlListAuditScope.unresolved()
        scope_unit_ids = raw_scope.get("scope_unit_ids")
        return ControlListAuditScope(
            organization_wide=scope_unit_ids is None,
            org_unit_ids=(
                None
                if scope_unit_ids is None
                else tuple(sorted({int(value) for value in scope_unit_ids}))
            ),
            resolution="RESOLVED",
        )
    except Exception:
        return ControlListAuditScope.unresolved()


def _audit_or_fail(
    request: Request,
    *,
    request_id: str,
    user: dict[str, Any],
    result: ControlListExportAuditResult,
    scope: ControlListAuditScope,
    as_of_date: date | None = None,
    row_count: int | None = None,
    error_code: str | None = None,
    sha256: str | None = None,
) -> None:
    try:
        write_control_list_export_audit(
            engine,
            actor_user_id=_actor_user_id(user),
            request_id=request_id,
            result=result,
            scope=scope,
            schema_version=_SCHEMA_VERSION,
            as_of_date=as_of_date,
            row_count=row_count,
            error_code=error_code,
            sha256=sha256,
            ip_address=_client_ip(request),
        )
    except Exception as exc:
        logger.error(
            "Mandatory control-list export audit failed request_id=%s",
            request_id,
        )
        raise HTTPException(
            status_code=500,
            detail={
                "code": "CONTROL_LIST_AUDIT_ERROR",
                "message": "The export operation could not be audited.",
            },
            headers=_headers(request_id),
        ) from exc


def _safe_http_error(
    *, request_id: str, status_code: int, code: str, message: str
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
        headers=_headers(request_id),
    )


@router.post(
    "/export",
    response_class=Response,
    responses={200: {"content": {_XLSX_MEDIA_TYPE: {}}}},
)
def export_control_list(
    request: Request,
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    """Build and return one complete XLSX after authorization, scope and audit."""

    request_id = _request_id(request)
    unresolved_scope = ControlListAuditScope.unresolved()

    from app.control_list_export.workbook import (
        ControlListExportLimitError,
        ControlListWorkbookError,
    )
    from app.control_list_projection import (
        ControlListAssignmentConflict,
        ControlListAuthorizationError,
    )
    from app.control_list_projection.service import ControlListConfigurationError

    try:
        projection = build_control_list_projection(engine, user_context=user)
    except ControlListAuthorizationError as exc:
        _audit_or_fail(
            request,
            request_id=request_id,
            user=user,
            result="FORBIDDEN",
            scope=unresolved_scope,
            error_code=exc.code,
        )
        raise _safe_http_error(
            request_id=request_id,
            status_code=403,
            code=exc.code,
            message="Control-list export is not permitted.",
        ) from exc
    except ControlListAssignmentConflict as exc:
        scope = _resolved_scope_for_audit(user)
        _audit_or_fail(
            request,
            request_id=request_id,
            user=user,
            result="CONFLICT",
            scope=scope,
            as_of_date=exc.detail.as_of_date,
            error_code="CONTROL_LIST_ASSIGNMENT_CONFLICT",
        )
        raise HTTPException(
            status_code=409,
            detail=exc.detail.model_dump(mode="json"),
            headers=_headers(request_id),
        ) from exc
    except ControlListConfigurationError as exc:
        _audit_or_fail(
            request,
            request_id=request_id,
            user=user,
            result="ERROR",
            scope=_resolved_scope_for_audit(user),
            error_code="CONTROL_LIST_CONFIGURATION_ERROR",
        )
        raise _safe_http_error(
            request_id=request_id,
            status_code=500,
            code="CONTROL_LIST_CONFIGURATION_ERROR",
            message="The export configuration is invalid.",
        ) from exc
    except Exception as exc:
        _audit_or_fail(
            request,
            request_id=request_id,
            user=user,
            result="ERROR",
            scope=_resolved_scope_for_audit(user),
            error_code="CONTROL_LIST_PROJECTION_ERROR",
        )
        logger.error("Control-list projection failed request_id=%s", request_id)
        raise _safe_http_error(
            request_id=request_id,
            status_code=500,
            code="CONTROL_LIST_PROJECTION_ERROR",
            message="The control-list projection could not be created.",
        ) from exc

    scope = ControlListAuditScope.from_projection_scope(projection.metadata.scope)
    try:
        artifact = build_control_list_workbook(projection, request_id=request_id)
    except ControlListExportLimitError as exc:
        _audit_or_fail(
            request,
            request_id=request_id,
            user=user,
            result="ERROR",
            scope=scope,
            as_of_date=projection.metadata.as_of_date,
            error_code="CONTROL_LIST_EXPORT_TOO_LARGE",
        )
        raise _safe_http_error(
            request_id=request_id,
            status_code=413,
            code="CONTROL_LIST_EXPORT_TOO_LARGE",
            message="The complete export exceeds the configured size limit.",
        ) from exc
    except ControlListWorkbookError as exc:
        _audit_or_fail(
            request,
            request_id=request_id,
            user=user,
            result="ERROR",
            scope=scope,
            as_of_date=projection.metadata.as_of_date,
            error_code="CONTROL_LIST_XLSX_BUILD_ERROR",
        )
        raise _safe_http_error(
            request_id=request_id,
            status_code=500,
            code="CONTROL_LIST_XLSX_BUILD_ERROR",
            message="The Excel file could not be created.",
        ) from exc
    except Exception as exc:
        _audit_or_fail(
            request,
            request_id=request_id,
            user=user,
            result="ERROR",
            scope=scope,
            as_of_date=projection.metadata.as_of_date,
            error_code="CONTROL_LIST_XLSX_BUILD_ERROR",
        )
        logger.error("Control-list workbook build failed request_id=%s", request_id)
        raise _safe_http_error(
            request_id=request_id,
            status_code=500,
            code="CONTROL_LIST_XLSX_BUILD_ERROR",
            message="The Excel file could not be created.",
        ) from exc

    response = Response(
        content=artifact.content,
        media_type=artifact.media_type,
        headers={
            **_headers(request_id),
            "Content-Disposition": _content_disposition(
                artifact.filename,
                ascii_filename=(
                    f"control-list-{projection.metadata.as_of_date.isoformat()}.xlsx"
                ),
            ),
            "X-Content-SHA256": artifact.sha256,
        },
    )
    _audit_or_fail(
        request,
        request_id=request_id,
        user=user,
        result="SUCCESS",
        scope=scope,
        as_of_date=projection.metadata.as_of_date,
        row_count=projection.total,
        sha256=artifact.sha256,
    )
    return response
