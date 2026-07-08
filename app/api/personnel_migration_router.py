"""PMF-3A/3B — Personnel Migration Framework REST API."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from app.api.personnel_migration_schemas import (
    AddDraftItemRequest,
    AddDraftItemResponse,
    CommitRunRequest,
    CommitRunResponse,
    CreateDraftRunRequest,
    CreateDraftRunResponse,
    MigrationDomainListResponse,
    MigrationRunOut,
    PersonnelRecordEventOut,
    RecordEventListResponse,
    SupersedeRecordRequest,
    SupersedeRecordResponse,
    VoidRunRequest,
    VoidRunResponse,
)
from app.auth import get_current_user
from app.directory.common import as_http500, call_service
from app.directory.rbac import require_hr_import_admin_or_403
from app.services.personnel_migration_commit_service import (
    add_draft_item_tx,
    commit_run_tx,
    create_draft_run_tx,
    supersede_record_tx,
    void_run_tx,
)
from app.services.personnel_migration_query_service import (
    get_migration_run_tx,
    list_migration_domains,
)
from app.services.personnel_migration_record_events_query_service import (
    get_record_event_tx,
    list_record_events_for_run_tx,
    list_record_events_tx,
)
from app.services.personnel_migration_types import (
    PersonnelMigrationConflictError,
    PersonnelMigrationNotFoundError,
    PersonnelMigrationValidationError,
)

router = APIRouter(prefix="/personnel-migration", tags=["personnel-migration"])


def _require_actor_id(user: Dict[str, Any]) -> str:
    uid = user.get("user_id") or user.get("id")
    if uid is None:
        raise HTTPException(status_code=401, detail="Unauthorized.")
    return str(uid)


def _validation_http422(exc: PersonnelMigrationValidationError) -> HTTPException:
    if exc.item_errors:
        return HTTPException(
            status_code=422,
            detail={
                "message": exc.message,
                "items": exc.item_errors,
            },
        )
    return HTTPException(status_code=422, detail=exc.message)


def _not_found_http404(exc: PersonnelMigrationNotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


def _conflict_http409(exc: PersonnelMigrationConflictError) -> HTTPException:
    return HTTPException(status_code=409, detail=str(exc))


@router.get("/domains", response_model=MigrationDomainListResponse)
def list_personnel_migration_domains_route(
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """List registered PMF domain plugins."""
    try:
        require_hr_import_admin_or_403(user)
        return call_service(list_migration_domains)
    except PersonnelMigrationValidationError as exc:
        raise _validation_http422(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post("/runs/draft", response_model=CreateDraftRunResponse, status_code=201)
def create_personnel_migration_draft_run_route(
    payload: CreateDraftRunRequest,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Create a draft migration run for an employee context."""
    try:
        require_hr_import_admin_or_403(user)
        created = call_service(
            create_draft_run_tx,
            domain_code=payload.domain_code,
            employee_context_id=payload.employee_context_id,
            actor_id=_require_actor_id(user),
            metadata=payload.metadata,
        )
        run = call_service(get_migration_run_tx, run_id=int(created["run_id"]))
        return {"run": run}
    except PersonnelMigrationValidationError as exc:
        raise _validation_http422(exc)
    except PersonnelMigrationNotFoundError as exc:
        raise _not_found_http404(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.get("/runs/{run_id}/record-events", response_model=RecordEventListResponse)
def list_personnel_migration_run_record_events_route(
    run_id: int = Path(..., ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """List business record events linked to a migration run."""
    try:
        require_hr_import_admin_or_403(user)
        return call_service(
            list_record_events_for_run_tx,
            run_id=run_id,
            limit=limit,
            offset=offset,
        )
    except PersonnelMigrationValidationError as exc:
        raise _validation_http422(exc)
    except PersonnelMigrationNotFoundError as exc:
        raise _not_found_http404(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.get("/runs/{run_id}", response_model=MigrationRunOut)
def get_personnel_migration_run_route(
    run_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Fetch a migration run with draft items."""
    try:
        require_hr_import_admin_or_403(user)
        return call_service(get_migration_run_tx, run_id=run_id)
    except PersonnelMigrationValidationError as exc:
        raise _validation_http422(exc)
    except PersonnelMigrationNotFoundError as exc:
        raise _not_found_http404(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post("/runs/{run_id}/commit", response_model=CommitRunResponse)
def commit_personnel_migration_run_route(
    run_id: int = Path(..., ge=1),
    payload: CommitRunRequest = CommitRunRequest(),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Commit a draft migration run via Commit Engine."""
    try:
        require_hr_import_admin_or_403(user)
        if not payload.confirm:
            raise PersonnelMigrationValidationError("Commit confirmation is required.")
        result = call_service(
            commit_run_tx,
            run_id=run_id,
            actor_id=_require_actor_id(user),
        )
        run = call_service(get_migration_run_tx, run_id=run_id)
        return {
            "run": run,
            "committed_items": result["committed_items"],
            "event_ids": result["event_ids"],
        }
    except PersonnelMigrationConflictError as exc:
        raise _conflict_http409(exc)
    except PersonnelMigrationValidationError as exc:
        raise _validation_http422(exc)
    except PersonnelMigrationNotFoundError as exc:
        raise _not_found_http404(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post("/runs/{run_id}/void", response_model=VoidRunResponse)
def void_personnel_migration_run_route(
    payload: VoidRunRequest,
    run_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Void a committed migration run (rollback without DELETE)."""
    try:
        require_hr_import_admin_or_403(user)
        result = call_service(
            void_run_tx,
            run_id=run_id,
            actor_id=_require_actor_id(user),
            void_reason=payload.void_reason,
        )
        run = call_service(get_migration_run_tx, run_id=run_id)
        return {
            "run": run,
            "voided_items": result["voided_items"],
            "event_ids": result["event_ids"],
        }
    except PersonnelMigrationConflictError as exc:
        raise _conflict_http409(exc)
    except PersonnelMigrationValidationError as exc:
        raise _validation_http422(exc)
    except PersonnelMigrationNotFoundError as exc:
        raise _not_found_http404(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post("/runs/{run_id}/items", response_model=AddDraftItemResponse, status_code=201)
def add_personnel_migration_draft_item_route(
    payload: AddDraftItemRequest,
    run_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Append a draft migration item to an existing draft run."""
    try:
        require_hr_import_admin_or_403(user)
        item = call_service(
            add_draft_item_tx,
            run_id=run_id,
            source_kind=payload.source_kind,
            source_record_id=payload.source_record_id,
            import_batch_id=payload.import_batch_id,
            import_row_id=payload.import_row_id,
            record_kind=payload.record_kind,
            draft_payload=payload.draft_payload,
            source_payload=payload.source_payload,
        )
        run = call_service(get_migration_run_tx, run_id=run_id)
        matched = next(
            (row for row in run["items"] if row["item_id"] == int(item["item_id"])),
            None,
        )
        if matched is None:
            raise PersonnelMigrationNotFoundError(
                f"Draft item {item['item_id']} not found after insert."
            )
        return {"item": matched, "run": run}
    except PersonnelMigrationConflictError as exc:
        raise _conflict_http409(exc)
    except PersonnelMigrationValidationError as exc:
        raise _validation_http422(exc)
    except PersonnelMigrationNotFoundError as exc:
        raise _not_found_http404(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.get("/record-events", response_model=RecordEventListResponse)
def list_personnel_record_events_route(
    person_id: Optional[int] = Query(default=None, ge=1),
    employee_context_id: Optional[int] = Query(default=None, ge=1),
    domain_code: Optional[str] = Query(default=None, max_length=100),
    record_table_name: Optional[str] = Query(default=None, max_length=100),
    record_id: Optional[int] = Query(default=None, ge=1),
    event_type: Optional[str] = Query(default=None, max_length=100),
    migration_run_id: Optional[int] = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """List personnel business record events (filtered)."""
    try:
        require_hr_import_admin_or_403(user)
        return call_service(
            list_record_events_tx,
            person_id=person_id,
            employee_context_id=employee_context_id,
            domain_code=domain_code,
            record_table_name=record_table_name,
            record_id=record_id,
            event_type=event_type,
            migration_run_id=migration_run_id,
            limit=limit,
            offset=offset,
        )
    except PersonnelMigrationValidationError as exc:
        raise _validation_http422(exc)
    except PersonnelMigrationNotFoundError as exc:
        raise _not_found_http404(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.get("/record-events/{event_id}", response_model=PersonnelRecordEventOut)
def get_personnel_record_event_route(
    event_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Fetch a single personnel business record event."""
    try:
        require_hr_import_admin_or_403(user)
        return call_service(get_record_event_tx, event_id=event_id)
    except PersonnelMigrationValidationError as exc:
        raise _validation_http422(exc)
    except PersonnelMigrationNotFoundError as exc:
        raise _not_found_http404(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)


@router.post("/records/supersede", response_model=SupersedeRecordResponse)
def supersede_personnel_record_route(
    payload: SupersedeRecordRequest,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Supersede an active person-owned record with a replacement row."""
    try:
        require_hr_import_admin_or_403(user)
        return call_service(
            supersede_record_tx,
            domain_code=payload.domain_code,
            employee_context_id=payload.employee_context_id,
            record_table_name=payload.record_table_name,
            record_id=payload.record_id,
            replacement_payload=payload.replacement_payload,
            actor_id=_require_actor_id(user),
            provenance=payload.provenance,
        )
    except PersonnelMigrationValidationError as exc:
        raise _validation_http422(exc)
    except PersonnelMigrationNotFoundError as exc:
        raise _not_found_http404(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)
