"""ADR-043 Phase C4.1 — personnel lifecycle REST API."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.personnel_admin_schemas import (
    EffectivePersonResponse,
    IdentityReconciliationExecuteRequest,
    IdentityReconciliationExecuteResponse,
    IdentityReconciliationPreviewRequest,
    IdentityReconciliationReportResponse,
    UserLinkagePreviewResponse,
    LifecycleRunDetail,
    LifecycleRunListResponse,
    LifecycleRunReportResponse,
    LifecycleRunRequest,
    OverrideActionRequest,
    OverrideCreateRequest,
    OverrideDetail,
    OverrideListResponse,
    OverrideSummary,
    PersonnelEventDetail,
    PersonnelEventListResponse,
    ValidationResponse,
)
from app.db.engine import engine
from app.security.personnel_admin_guard import (
    evaluate_hr_governance_access,
    require_hr_governance_api,
    require_personnel_admin_api,
)
from app.services.hr_effective_canonical_service import (
    EffectiveCanonicalError,
    resolve_effective_person_tx,
)
from app.services.hr_personnel_lifecycle_service import (
    PersonnelLifecycleError,
    run_monthly_personnel_lifecycle,
    run_post_lifecycle_validation,
)
from app.services.hr_override_stewardship_service import StewardshipRuleNotFoundError
from app.services.hr_review_override_service import (
    InvalidOverrideTransitionError,
    ReviewOverrideError,
    ReviewOverrideNotFoundError,
    approve_override_tx,
    create_override_tx,
    reconfirm_override_tx,
    reject_override_tx,
    revoke_override_tx,
)
from app.services.identity_reconciliation_service import (
    IdentityReconciliationError,
    run_r1a_dry_run,
    run_r1a_execute,
)
from app.services.user_linkage_preview_service import run_user_linkage_preview
from app.services.personnel_admin_query_service import (
    get_lifecycle_run,
    get_override,
    get_override_tier,
    get_personnel_event,
    list_lifecycle_runs,
    list_overrides,
    list_personnel_events,
)

router = APIRouter(prefix="/admin/personnel", tags=["personnel-admin"])


def _value_error_to_http(exc: ValueError) -> HTTPException:
    msg = str(exc)
    if "not found" in msg.lower():
        return HTTPException(status_code=404, detail=msg)
    return HTTPException(status_code=400, detail=msg)


def _override_error_to_http(exc: ReviewOverrideError) -> HTTPException:
    if isinstance(exc, ReviewOverrideNotFoundError):
        return HTTPException(status_code=404, detail=exc.message)
    return HTTPException(status_code=400, detail=exc.message)


def _ensure_tier2_governance(user_ctx: Dict[str, Any], override_id: int) -> None:
    try:
        tier = get_override_tier(int(override_id))
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
    if tier >= 2 and not evaluate_hr_governance_access(user_ctx):
        raise HTTPException(
            status_code=403,
            detail="HR governance permission required for Tier 2 override actions.",
        )


@router.get("/lifecycle/runs", response_model=LifecycleRunListResponse)
def admin_list_lifecycle_runs(
    previous_snapshot_id: Optional[int] = Query(default=None, ge=1),
    snapshot_id: Optional[int] = Query(default=None, ge=1),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="started_at"),
    sort_dir: str = Query(default="desc"),
    _admin: Dict[str, Any] = Depends(require_personnel_admin_api),
) -> Dict[str, Any]:
    return list_lifecycle_runs(
        previous_snapshot_id=previous_snapshot_id,
        snapshot_id=snapshot_id,
        status=status,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


@router.get("/lifecycle/runs/{run_id}", response_model=LifecycleRunDetail)
def admin_get_lifecycle_run(
    run_id: int,
    _admin: Dict[str, Any] = Depends(require_personnel_admin_api),
) -> Dict[str, Any]:
    try:
        return get_lifecycle_run(int(run_id))
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.post("/lifecycle/run-preview", response_model=LifecycleRunReportResponse)
def admin_preview_lifecycle_run(
    body: LifecycleRunRequest,
    admin: Dict[str, Any] = Depends(require_personnel_admin_api),
) -> Dict[str, Any]:
    try:
        return run_monthly_personnel_lifecycle(
            previous_snapshot_id=body.previous_snapshot_id,
            snapshot_id=body.snapshot_id,
            dry_run=True,
            refresh_cache=body.refresh_cache,
            enqueue=body.enqueue,
            sync_persons=body.sync_persons,
            actor_user_id=int(admin["user_id"]),
        )
    except PersonnelLifecycleError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@router.post("/lifecycle/run", response_model=LifecycleRunReportResponse)
def admin_execute_lifecycle_run(
    body: LifecycleRunRequest,
    admin: Dict[str, Any] = Depends(require_personnel_admin_api),
) -> Dict[str, Any]:
    try:
        return run_monthly_personnel_lifecycle(
            previous_snapshot_id=body.previous_snapshot_id,
            snapshot_id=body.snapshot_id,
            dry_run=False,
            refresh_cache=body.refresh_cache,
            enqueue=body.enqueue,
            sync_persons=body.sync_persons,
            actor_user_id=int(admin["user_id"]),
        )
    except PersonnelLifecycleError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@router.get("/lifecycle/validation", response_model=ValidationResponse)
def admin_lifecycle_validation(
    previous_snapshot_id: int = Query(..., ge=1),
    snapshot_id: int = Query(..., ge=1),
    _admin: Dict[str, Any] = Depends(require_personnel_admin_api),
) -> Dict[str, Any]:
    if int(previous_snapshot_id) == int(snapshot_id):
        raise HTTPException(
            status_code=400,
            detail="previous_snapshot_id must differ from snapshot_id",
        )
    with engine.connect() as conn:
        result = run_post_lifecycle_validation(
            conn,
            previous_snapshot_id=int(previous_snapshot_id),
            snapshot_id=int(snapshot_id),
        )
    return {
        "previous_snapshot_id": int(previous_snapshot_id),
        "snapshot_id": int(snapshot_id),
        **result,
    }


@router.get("/events", response_model=PersonnelEventListResponse)
def admin_list_personnel_events(
    snapshot_id: Optional[int] = Query(default=None, ge=1),
    event_type: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    person_key: Optional[str] = Query(default=None),
    assignment_key: Optional[str] = Query(default=None),
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="detected_at"),
    sort_dir: str = Query(default="desc"),
    _admin: Dict[str, Any] = Depends(require_personnel_admin_api),
) -> Dict[str, Any]:
    return list_personnel_events(
        snapshot_id=snapshot_id,
        event_type=event_type,
        status=status,
        person_key=person_key,
        assignment_key=assignment_key,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


@router.get("/events/{event_id}", response_model=PersonnelEventDetail)
def admin_get_personnel_event(
    event_id: int,
    _admin: Dict[str, Any] = Depends(require_personnel_admin_api),
) -> Dict[str, Any]:
    try:
        return get_personnel_event(int(event_id))
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.get("/overrides", response_model=OverrideListResponse)
def admin_list_overrides(
    status: Optional[str] = Query(default=None),
    scope_type: Optional[str] = Query(default=None),
    person_key: Optional[str] = Query(default=None),
    assignment_key: Optional[str] = Query(default=None),
    field_path: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="created_at"),
    sort_dir: str = Query(default="desc"),
    _admin: Dict[str, Any] = Depends(require_personnel_admin_api),
) -> Dict[str, Any]:
    return list_overrides(
        status=status,
        scope_type=scope_type,
        person_key=person_key,
        assignment_key=assignment_key,
        field_path=field_path,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


@router.get("/overrides/{override_id}", response_model=OverrideDetail)
def admin_get_override(
    override_id: int,
    _admin: Dict[str, Any] = Depends(require_personnel_admin_api),
) -> Dict[str, Any]:
    try:
        return get_override(int(override_id))
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.post("/overrides", response_model=OverrideDetail)
def admin_create_override(
    body: OverrideCreateRequest,
    admin: Dict[str, Any] = Depends(require_personnel_admin_api),
) -> Dict[str, Any]:
    try:
        created = create_override_tx(
            scope_type=body.scope_type,
            scope_key=body.scope_key,
            field_path=body.field_path,
            override_value=body.override_value,
            created_by_user_id=int(admin["user_id"]),
            tier=body.tier,
            owner_domain=body.owner_domain,
            canonical_value=body.canonical_value,
            justification=body.justification,
            evidence_url=body.evidence_url,
            person_key=body.person_key,
            assignment_key=body.assignment_key,
            person_id=body.person_id,
            assignment_id=body.assignment_id,
            supersedes_override_id=body.supersedes_override_id,
            metadata=body.metadata,
        )
        return get_override(int(created["override_id"]))
    except ReviewOverrideError as exc:
        raise _override_error_to_http(exc) from exc
    except StewardshipRuleNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/overrides/{override_id}/approve", response_model=OverrideSummary)
def admin_approve_override(
    override_id: int,
    body: OverrideActionRequest,
    admin: Dict[str, Any] = Depends(require_hr_governance_api),
) -> Dict[str, Any]:
    _ensure_tier2_governance(admin, int(override_id))
    try:
        return approve_override_tx(
            override_id=int(override_id),
            approved_by_user_id=int(admin["user_id"]),
            approval_comment=body.comment,
        )
    except ReviewOverrideError as exc:
        raise _override_error_to_http(exc) from exc


@router.post("/overrides/{override_id}/reject", response_model=OverrideSummary)
def admin_reject_override(
    override_id: int,
    body: OverrideActionRequest,
    admin: Dict[str, Any] = Depends(require_hr_governance_api),
) -> Dict[str, Any]:
    _ensure_tier2_governance(admin, int(override_id))
    reason = (body.reason or body.comment or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="reason or comment is required")
    try:
        return reject_override_tx(
            override_id=int(override_id),
            rejected_by_user_id=int(admin["user_id"]),
            reject_reason=reason,
        )
    except ReviewOverrideError as exc:
        raise _override_error_to_http(exc) from exc


@router.post("/overrides/{override_id}/revoke", response_model=OverrideSummary)
def admin_revoke_override(
    override_id: int,
    body: OverrideActionRequest,
    admin: Dict[str, Any] = Depends(require_personnel_admin_api),
) -> Dict[str, Any]:
    reason = (body.reason or body.comment or "").strip()
    if len(reason) < 10:
        raise HTTPException(status_code=400, detail="revoke reason must be at least 10 characters")
    try:
        return revoke_override_tx(
            override_id=int(override_id),
            revoked_by_user_id=int(admin["user_id"]),
            revoke_reason=reason,
        )
    except (ReviewOverrideError, InvalidOverrideTransitionError) as exc:
        raise _override_error_to_http(exc) from exc


@router.post("/overrides/{override_id}/reconfirm", response_model=OverrideSummary)
def admin_reconfirm_override(
    override_id: int,
    body: OverrideActionRequest,
    admin: Dict[str, Any] = Depends(require_personnel_admin_api),
) -> Dict[str, Any]:
    try:
        return reconfirm_override_tx(
            override_id=int(override_id),
            reconfirmed_by_user_id=int(admin["user_id"]),
            reason=body.reason or body.comment,
        )
    except ReviewOverrideError as exc:
        raise _override_error_to_http(exc) from exc


@router.get("/effective-person", response_model=EffectivePersonResponse)
def admin_get_effective_person(
    person_key: str = Query(..., min_length=1),
    assignment_key: Optional[str] = Query(default=None),
    snapshot_id: Optional[int] = Query(default=None, ge=1),
    _admin: Dict[str, Any] = Depends(require_personnel_admin_api),
) -> Dict[str, Any]:
    try:
        return resolve_effective_person_tx(
            person_key=person_key.strip(),
            assignment_key=assignment_key.strip() if assignment_key else None,
            snapshot_id=snapshot_id,
        )
    except EffectiveCanonicalError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@router.post(
    "/identity/reconciliation/r1a/preview",
    response_model=IdentityReconciliationReportResponse,
)
def admin_preview_identity_reconciliation_r1a(
    body: IdentityReconciliationPreviewRequest,
    _admin: Dict[str, Any] = Depends(require_personnel_admin_api),
) -> Dict[str, Any]:
    """ADR-044 B1 — read-only R1a identity materialization preview."""
    try:
        with engine.connect() as conn:
            return run_r1a_dry_run(conn, snapshot_id=body.snapshot_id)
    except IdentityReconciliationError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@router.get(
    "/identity/reconciliation/r1a/preview",
    response_model=IdentityReconciliationReportResponse,
)
def admin_preview_identity_reconciliation_r1a_get(
    snapshot_id: Optional[int] = Query(default=None, ge=1),
    _admin: Dict[str, Any] = Depends(require_personnel_admin_api),
) -> Dict[str, Any]:
    """ADR-044 B1 — read-only R1a preview (GET convenience)."""
    try:
        with engine.connect() as conn:
            return run_r1a_dry_run(conn, snapshot_id=snapshot_id)
    except IdentityReconciliationError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@router.post(
    "/identity/reconciliation/r1a/execute",
    response_model=IdentityReconciliationExecuteResponse,
)
def admin_execute_identity_reconciliation_r1a(
    body: IdentityReconciliationExecuteRequest,
    admin: Dict[str, Any] = Depends(require_personnel_admin_api),
) -> Dict[str, Any]:
    """ADR-044 B2 — R1a identity materialization execute (admin only; not for production without approval)."""
    actor_user_id = int(admin["user_id"])
    try:
        with engine.connect() as conn:
            return run_r1a_execute(
                conn,
                actor_user_id=actor_user_id,
                snapshot_id=body.snapshot_id,
                person_id=body.person_id,
                limit=body.limit,
            )
    except IdentityReconciliationError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@router.get(
    "/identity/user-linkage/preview",
    response_model=UserLinkagePreviewResponse,
)
def admin_preview_user_linkage(
    _admin: Dict[str, Any] = Depends(require_personnel_admin_api),
) -> Dict[str, Any]:
    """ADR-044 R2.2 — read-only User → Employee linkage preview (no writes)."""
    with engine.connect() as conn:
        return run_user_linkage_preview(conn)
