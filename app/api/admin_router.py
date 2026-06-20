"""ADR-042 Phase B4 — sysadmin REST API (no UI, no enforcement)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.admin_schemas import (
    AccessGrantCreate,
    AccessGrantResponse,
    AccessRoleRefResponse,
    AccessTargetSearchResponse,
    AdminUserResponse,
    AssignmentDriftResponse,
    EffectiveAccessResponse,
    EnrollmentDecisionRequest,
    EnrollmentDetectRequest,
    EnrollmentQueueItemResponse,
    GuardModeResponse,
    SecurityAuditEventResponse,
)
from app.security.admin_guard import require_sysadmin_api
from app.services.access_grant_service import grant_access, list_access_grants, revoke_access
from app.services.access_resolver_service import explain_effective_access, resolve_effective_access
from app.services.admin_users_service import (
    force_password_change,
    get_admin_user,
    list_admin_users,
    lock_user,
    unlock_user,
)
from app.services.assignment_reconciliation_service import (
    list_assignment_drift,
    reconcile_employee_primary_assignment,
)
from app.services.enrollment_detector_service import detect_enrollment_candidates
from app.services.enrollment_service import (
    apply_enrollment,
    approve_enrollment,
    list_enrollment_queue,
    reject_enrollment,
)
from app.services.admin_reference_service import (
    get_guard_mode_info,
    list_access_roles,
    search_access_targets,
)
from app.services.security_audit_service import list_security_events

router = APIRouter(prefix="/admin", tags=["admin"])


def _value_error_to_http(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


@router.get("/access/roles", response_model=List[AccessRoleRefResponse])
def admin_list_access_roles(
    active_only: bool = Query(default=True),
    _admin: Dict[str, Any] = Depends(require_sysadmin_api),
) -> List[Dict[str, Any]]:
    return list_access_roles(active_only=active_only)


@router.get("/access/guard-mode", response_model=GuardModeResponse)
def admin_get_guard_mode(
    _admin: Dict[str, Any] = Depends(require_sysadmin_api),
) -> Dict[str, Any]:
    return get_guard_mode_info()


@router.get("/access/targets/search", response_model=AccessTargetSearchResponse)
def admin_search_access_targets(
    target_type: str = Query(..., min_length=1),
    q: str = Query(default=""),
    limit: int = Query(default=20, ge=1, le=50),
    _admin: Dict[str, Any] = Depends(require_sysadmin_api),
) -> Dict[str, Any]:
    try:
        return search_access_targets(q=q, target_type=target_type, limit=limit)
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.get("/access/effective", response_model=List[EffectiveAccessResponse])
def admin_list_effective_access(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _admin: Dict[str, Any] = Depends(require_sysadmin_api),
) -> List[Dict[str, Any]]:
    users = list_admin_users(limit=limit, offset=offset)
    items: List[Dict[str, Any]] = []
    for user in users["items"]:
        uid = int(user["user_id"])
        try:
            resolved = explain_effective_access(user_id=uid)
        except ValueError:
            continue
        items.append(resolved)
    return items


@router.get("/access/effective/{user_id}", response_model=EffectiveAccessResponse)
def admin_get_effective_access(
    user_id: int,
    _admin: Dict[str, Any] = Depends(require_sysadmin_api),
) -> Dict[str, Any]:
    try:
        return explain_effective_access(user_id=int(user_id))
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.get("/access/grants")
def admin_list_access_grants(
    target_type: Optional[str] = Query(default=None),
    target_id: Optional[int] = Query(default=None, ge=1),
    active_only: bool = Query(default=True),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _admin: Dict[str, Any] = Depends(require_sysadmin_api),
) -> Dict[str, Any]:
    return list_access_grants(
        target_type=target_type,
        target_id=target_id,
        active_only=active_only,
        limit=limit,
        offset=offset,
    )


@router.post("/access/grants", response_model=AccessGrantResponse)
def admin_create_access_grant(
    body: AccessGrantCreate,
    admin: Dict[str, Any] = Depends(require_sysadmin_api),
) -> Dict[str, Any]:
    try:
        return grant_access(
            access_role_id=body.access_role_id,
            target_type=body.target_type,
            target_id=body.target_id,
            granted_by_user_id=int(admin["user_id"]),
            resource_key=body.resource_key,
            scope_type=body.scope_type,
            scope_id=body.scope_id,
            include_subtree=body.include_subtree,
            starts_at=body.starts_at,
            ends_at=body.ends_at,
            reason=body.reason,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.delete("/access/grants/{grant_id}", response_model=AccessGrantResponse)
def admin_revoke_access_grant(
    grant_id: int,
    admin: Dict[str, Any] = Depends(require_sysadmin_api),
    reason: Optional[str] = Query(default=None, max_length=500),
) -> Dict[str, Any]:
    try:
        return revoke_access(
            grant_id=int(grant_id),
            revoked_by_user_id=int(admin["user_id"]),
            reason=reason,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.get("/enrollment/queue")
def admin_list_enrollment_queue(
    queue_status: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _admin: Dict[str, Any] = Depends(require_sysadmin_api),
) -> Dict[str, Any]:
    return list_enrollment_queue(queue_status=queue_status, limit=limit, offset=offset)


@router.post("/enrollment/detect")
def admin_detect_enrollment(
    body: EnrollmentDetectRequest,
    _admin: Dict[str, Any] = Depends(require_sysadmin_api),
) -> Dict[str, Any]:
    return detect_enrollment_candidates(
        batch_id=body.batch_id,
        dry_run=body.dry_run,
        limit=body.limit,
    )


@router.post("/enrollment/queue/{queue_id}/approve", response_model=EnrollmentQueueItemResponse)
def admin_approve_enrollment(
    queue_id: int,
    body: EnrollmentDecisionRequest,
    admin: Dict[str, Any] = Depends(require_sysadmin_api),
) -> Dict[str, Any]:
    try:
        return approve_enrollment(
            queue_id=int(queue_id),
            actor_user_id=int(admin["user_id"]),
            comment=body.comment,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.post("/enrollment/queue/{queue_id}/reject", response_model=EnrollmentQueueItemResponse)
def admin_reject_enrollment(
    queue_id: int,
    body: EnrollmentDecisionRequest,
    admin: Dict[str, Any] = Depends(require_sysadmin_api),
) -> Dict[str, Any]:
    try:
        return reject_enrollment(
            queue_id=int(queue_id),
            actor_user_id=int(admin["user_id"]),
            comment=body.comment,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.post("/enrollment/queue/{queue_id}/apply")
def admin_apply_enrollment(
    queue_id: int,
    admin: Dict[str, Any] = Depends(require_sysadmin_api),
) -> Dict[str, Any]:
    try:
        return apply_enrollment(
            queue_id=int(queue_id),
            actor_user_id=int(admin["user_id"]),
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.get("/assignments/drift", response_model=AssignmentDriftResponse)
def admin_list_assignment_drift(
    limit: int = Query(default=100, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    _admin: Dict[str, Any] = Depends(require_sysadmin_api),
) -> Dict[str, Any]:
    return list_assignment_drift(limit=limit, offset=offset)


@router.post("/assignments/reconcile/{employee_id}")
def admin_reconcile_assignment(
    employee_id: int,
    dry_run: bool = Query(default=True),
    admin: Dict[str, Any] = Depends(require_sysadmin_api),
) -> Dict[str, Any]:
    try:
        return reconcile_employee_primary_assignment(
            int(employee_id),
            dry_run=dry_run,
            actor_user_id=int(admin["user_id"]),
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.get("/security-audit")
def admin_list_security_audit(
    event_type: Optional[str] = Query(default=None),
    actor_user_id: Optional[int] = Query(default=None, ge=1),
    target_user_id: Optional[int] = Query(default=None, ge=1),
    target_person_id: Optional[int] = Query(default=None, ge=1),
    target_employee_id: Optional[int] = Query(default=None, ge=1),
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _admin: Dict[str, Any] = Depends(require_sysadmin_api),
) -> Dict[str, Any]:
    return list_security_events(
        event_type=event_type,
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
        target_person_id=target_person_id,
        target_employee_id=target_employee_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )


@router.get("/users", response_model=List[AdminUserResponse])
def admin_list_users(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _admin: Dict[str, Any] = Depends(require_sysadmin_api),
) -> List[Dict[str, Any]]:
    result = list_admin_users(limit=limit, offset=offset)
    return result["items"]


@router.get("/users/{user_id}", response_model=AdminUserResponse)
def admin_get_user(
    user_id: int,
    _admin: Dict[str, Any] = Depends(require_sysadmin_api),
) -> Dict[str, Any]:
    try:
        return get_admin_user(int(user_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/users/{user_id}/lock", response_model=AdminUserResponse)
def admin_lock_user(
    user_id: int,
    admin: Dict[str, Any] = Depends(require_sysadmin_api),
    reason: str = Query(default="admin"),
) -> Dict[str, Any]:
    try:
        return lock_user(
            user_id=int(user_id),
            actor_user_id=int(admin["user_id"]),
            reason=reason,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.post("/users/{user_id}/unlock", response_model=AdminUserResponse)
def admin_unlock_user(
    user_id: int,
    admin: Dict[str, Any] = Depends(require_sysadmin_api),
) -> Dict[str, Any]:
    try:
        return unlock_user(
            user_id=int(user_id),
            actor_user_id=int(admin["user_id"]),
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.post("/users/{user_id}/force-password-change", response_model=AdminUserResponse)
def admin_force_password_change(
    user_id: int,
    admin: Dict[str, Any] = Depends(require_sysadmin_api),
) -> Dict[str, Any]:
    try:
        return force_password_change(
            user_id=int(user_id),
            actor_user_id=int(admin["user_id"]),
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
