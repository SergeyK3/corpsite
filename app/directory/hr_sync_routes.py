# FILE: app/directory/hr_sync_routes.py
"""HR sync package admin API — export, preview, apply, audit (ADR-038 Phase D.1–D.3)."""
from __future__ import annotations

import base64
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.auth import get_current_user
from app.db.engine import engine
from app.directory.rbac import require_privileged_or_403
from app.services.sync.audit_service import (
    get_sync_audit_log,
    insert_sync_audit_log,
    list_sync_audit_log,
    sync_audit_entry_to_api_dict,
    sync_audit_log_available,
)
from app.services.sync.export_service import SyncExportError, export_hr_sync_package
from app.services.sync.import_service import import_hr_sync_package
from app.services.sync.package_schema import PACKAGE_VERSION, SCHEMA_VERSION
from app.services.sync.preview_service import (
    preview_hr_sync_package,
    preview_result_to_api_dict,
    sync_apply_result_to_api_dict,
)

from .common import as_http500

router = APIRouter()


def _sync_actor(user: Dict[str, Any]) -> tuple[Optional[int], Optional[str]]:
    actor_user_id = user.get("user_id")
    try:
        actor_id = int(actor_user_id) if actor_user_id is not None else None
    except (TypeError, ValueError):
        actor_id = None
    actor_login = str(user.get("login") or "").strip() or None
    return actor_id, actor_login


class SyncExportRequest(BaseModel):
    source_instance_id: str = Field(..., min_length=1, max_length=128)
    source_organization_id: str = Field(..., min_length=1, max_length=128)
    source_organization_name: str = Field(..., min_length=1, max_length=512)
    environment: Literal["server", "local", "staging"] = "server"
    notes: Optional[str] = Field(default=None, max_length=2000)


@router.get("/personnel/sync/meta")
def get_sync_meta(
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Sync package format metadata for admin UI."""
    require_privileged_or_403(user)
    with engine.connect() as conn:
        audit_available = sync_audit_log_available(conn)
    return {
        "schema_version": SCHEMA_VERSION,
        "package_version": PACKAGE_VERSION,
        "audit_log_available": audit_available,
    }


@router.get("/personnel/sync/history")
def get_sync_history(
    limit: int = 20,
    offset: int = 0,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """List persisted sync admin audit log entries (newest first)."""
    require_privileged_or_403(user)
    with engine.connect() as conn:
        entries, total = list_sync_audit_log(conn, limit=limit, offset=offset)
        audit_available = sync_audit_log_available(conn)
    return {
        "audit_log_available": audit_available,
        "total": total,
        "limit": max(1, min(limit, 100)),
        "offset": max(0, offset),
        "items": [sync_audit_entry_to_api_dict(entry) for entry in entries],
    }


@router.get("/personnel/sync/history/{sync_audit_id}")
def get_sync_history_item(
    sync_audit_id: int,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Single sync audit log entry with warnings/errors."""
    require_privileged_or_403(user)
    with engine.connect() as conn:
        entry = get_sync_audit_log(conn, sync_audit_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Sync audit entry not found.")
    return sync_audit_entry_to_api_dict(entry, include_messages=True)


@router.post("/personnel/sync/export")
def post_sync_export(
    body: SyncExportRequest = Body(...),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Export HR sync package — read-only DB read, returns zip as base64 for browser download."""
    require_privileged_or_403(user)

    source_organization = {
        "id": body.source_organization_id.strip(),
        "name": body.source_organization_name.strip(),
    }
    exported_by_login = str(user.get("login") or "").strip() or None
    actor_user_id, actor_login = _sync_actor(user)

    tmp_dir: Optional[str] = None
    audit_id: Optional[int] = None
    try:
        tmp_dir = tempfile.mkdtemp(prefix="corpsite_sync_export_")
        with engine.connect() as conn:
            result = export_hr_sync_package(
                conn,
                output_dir=Path(tmp_dir),
                source_instance_id=body.source_instance_id.strip(),
                source_organization=source_organization,
                environment=body.environment,
                notes=body.notes.strip() if body.notes else None,
                exported_by_user_login=exported_by_login,
            )
        zip_bytes = result.output_path.read_bytes()
        response = {
            "package_name": result.output_path.name,
            "employee_count": result.employee_count,
            "override_count": result.override_count,
            "skipped_override_count": result.skipped_override_count,
            "warnings": result.warnings,
            "validation_ok": result.validation_ok,
            "package_base64": base64.b64encode(zip_bytes).decode("ascii"),
        }
        with engine.begin() as conn:
            audit_id = insert_sync_audit_log(
                conn,
                operation="export",
                actor_user_id=actor_user_id,
                actor_login=actor_login,
                package_name=result.output_path.name,
                validation_ok=result.validation_ok,
                notes=body.notes.strip() if body.notes else None,
                summary={
                    "employee_count": result.employee_count,
                    "override_count": result.override_count,
                    "skipped_override_count": result.skipped_override_count,
                },
                context={
                    "source_instance_id": body.source_instance_id.strip(),
                    "source_organization_id": source_organization["id"],
                    "source_organization_name": source_organization["name"],
                    "environment": body.environment,
                },
                warnings=result.warnings,
            )
        if audit_id is not None:
            response["audit_id"] = audit_id
        return response
    except SyncExportError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)
    finally:
        if tmp_dir:
            for path in Path(tmp_dir).glob("*"):
                try:
                    path.unlink()
                except OSError:
                    pass
            try:
                os.rmdir(tmp_dir)
            except OSError:
                pass


@router.post("/personnel/sync/preview")
async def post_sync_preview(
    file: UploadFile = File(...),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Preview sync package import — no DB writes."""
    require_privileged_or_403(user)

    filename = (file.filename or "").strip()
    if not filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Expected .zip sync package file.")

    actor_user_id, actor_login = _sync_actor(user)

    tmp_path: Optional[str] = None
    audit_id: Optional[int] = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            tmp_path = tmp.name
            content = await file.read()
            if not content:
                raise HTTPException(status_code=400, detail="Empty file.")
            tmp.write(content)

        with engine.connect() as conn:
            result = preview_hr_sync_package(conn, package_path=Path(tmp_path))

        payload = preview_result_to_api_dict(result)
        payload["package_name"] = filename
        with engine.begin() as conn:
            audit_id = insert_sync_audit_log(
                conn,
                operation="preview",
                actor_user_id=actor_user_id,
                actor_login=actor_login,
                package_name=filename,
                validation_ok=result.validation_ok,
                summary={
                    "total_records": result.total_records,
                    "new_count": result.new_count,
                    "update_count": result.update_count,
                    "merge_count": result.merge_count,
                    "identical_count": result.identical_count,
                    "orphan_count": result.orphan_count,
                    "ambiguous_count": result.ambiguous_count,
                    "conflict_count": result.conflict_count,
                    "skipped_count": result.skipped_count,
                    "apply_allowed_count": result.apply_allowed_count,
                },
                warnings=result.warnings,
                errors=result.errors,
            )
        if audit_id is not None:
            payload["audit_id"] = audit_id
        return payload
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


@router.post("/personnel/sync/apply")
async def post_sync_apply(
    file: UploadFile = File(...),
    dry_run: bool = Form(False),
    notes: Optional[str] = Form(None),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Apply sync package with apply gate — dry-run or real apply, no force apply."""
    require_privileged_or_403(user)

    filename = (file.filename or "").strip()
    if not filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Expected .zip sync package file.")

    trimmed_notes = notes.strip() if notes else None
    if trimmed_notes and len(trimmed_notes) > 2000:
        raise HTTPException(status_code=400, detail="Notes must be at most 2000 characters.")

    actor_user_id, actor_login = _sync_actor(user)

    tmp_path: Optional[str] = None
    audit_id: Optional[int] = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            tmp_path = tmp.name
            content = await file.read()
            if not content:
                raise HTTPException(status_code=400, detail="Empty file.")
            tmp.write(content)

        package_path = Path(tmp_path)
        with engine.connect() as conn:
            preview_result = preview_hr_sync_package(conn, package_path=package_path)

        if dry_run:
            with engine.connect() as conn:
                import_result = import_hr_sync_package(
                    conn,
                    package_path=package_path,
                    apply_changes=False,
                    enforce_apply_gate=True,
                )
            with engine.begin() as conn:
                audit_id = insert_sync_audit_log(
                    conn,
                    operation="apply",
                    actor_user_id=actor_user_id,
                    actor_login=actor_login,
                    dry_run=True,
                    package_name=filename,
                    validation_ok=import_result.validation_ok,
                    notes=trimmed_notes,
                    summary={
                        "resolved": import_result.resolved_count,
                        "applied": import_result.applied_count,
                        "skipped": import_result.skipped_count,
                        "identical": import_result.identical_count,
                        "blocked": import_result.blocked_count,
                        "conflict": import_result.conflict_count,
                        "orphan": import_result.orphan_count,
                        "ambiguous": import_result.ambiguous_count,
                    },
                    warnings=import_result.warnings,
                    errors=import_result.errors,
                )
        else:
            with engine.begin() as conn:
                import_result = import_hr_sync_package(
                    conn,
                    package_path=package_path,
                    apply_changes=True,
                    enforce_apply_gate=True,
                )
                audit_id = insert_sync_audit_log(
                    conn,
                    operation="apply",
                    actor_user_id=actor_user_id,
                    actor_login=actor_login,
                    dry_run=False,
                    package_name=filename,
                    validation_ok=import_result.validation_ok,
                    notes=trimmed_notes,
                    summary={
                        "resolved": import_result.resolved_count,
                        "applied": import_result.applied_count,
                        "skipped": import_result.skipped_count,
                        "identical": import_result.identical_count,
                        "blocked": import_result.blocked_count,
                        "conflict": import_result.conflict_count,
                        "orphan": import_result.orphan_count,
                        "ambiguous": import_result.ambiguous_count,
                    },
                    warnings=import_result.warnings,
                    errors=import_result.errors,
                )

        payload = sync_apply_result_to_api_dict(
            import_result,
            preview_result,
            dry_run=dry_run,
            package_name=filename,
            notes=trimmed_notes,
        )
        if audit_id is not None:
            payload["audit_id"] = audit_id
        return payload
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc)
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
