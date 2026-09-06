"""Read-only WP-TD-006B User/Role search and relationship preview API."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.security.admin_permissions import (
    TEST_SYSTEM_IDENTITY_DELETION_REQUEST,
    has_test_system_identity_deletion_request_permission,
)
from app.services import test_system_identity_preview_service as service

from .test_system_identity_deletion_schemas import (
    TestSystemIdentityPreviewIn,
    TestSystemIdentitySearchIn,
)


router = APIRouter(
    prefix="/test-system-identity-deletion",
    tags=["test-system-identity-deletion"],
)


def _require(user: dict[str, Any]) -> int:
    user_id = int(user["user_id"])
    if not has_test_system_identity_deletion_request_permission(user_id):
        raise HTTPException(status_code=403, detail={
            "code": "TD_SYSTEM_PERMISSION_REQUIRED",
            "permission": TEST_SYSTEM_IDENTITY_DELETION_REQUEST,
        })
    return user_id


def _error(exc: service.SystemIdentityPreviewError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": exc.message},
    )


@router.post("/search")
def search(
    body: TestSystemIdentitySearchIn,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    _require(user)
    try:
        return service.search_candidates(
            object_type=body.object_type,
            field=body.field,
            mask=body.mask,
            object_ids=body.object_ids,
        )
    except service.SystemIdentityPreviewError as exc:
        raise _error(exc) from exc


@router.post("/preview")
def preview(
    body: TestSystemIdentityPreviewIn,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    _require(user)
    try:
        return service.preview_targets(
            targets=[target.model_dump() for target in body.targets],
        )
    except service.SystemIdentityPreviewError as exc:
        raise _error(exc) from exc
