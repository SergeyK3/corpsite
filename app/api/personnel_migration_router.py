"""PMF-3A — Personnel Migration Framework draft-layer REST API."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Path

from app.api.personnel_migration_schemas import (
    AddDraftItemRequest,
    AddDraftItemResponse,
    CreateDraftRunRequest,
    CreateDraftRunResponse,
    MigrationDomainListResponse,
    MigrationRunOut,
)
from app.auth import get_current_user
from app.directory.common import as_http500, call_service
from app.directory.rbac import require_hr_import_admin_or_403
from app.services.personnel_migration_commit_service import (
    add_draft_item_tx,
    create_draft_run_tx,
)
from app.services.personnel_migration_query_service import (
    get_migration_run_tx,
    list_migration_domains,
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
    return HTTPException(status_code=422, detail=str(exc))


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
