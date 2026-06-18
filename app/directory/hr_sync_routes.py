# FILE: app/directory/hr_sync_routes.py
"""HR sync package admin API — export, preview, and apply (ADR-038 Phase D.1/D.2)."""
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
    return {
        "schema_version": SCHEMA_VERSION,
        "package_version": PACKAGE_VERSION,
    }


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

    tmp_dir: Optional[str] = None
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
        return {
            "package_name": result.output_path.name,
            "employee_count": result.employee_count,
            "override_count": result.override_count,
            "skipped_override_count": result.skipped_override_count,
            "warnings": result.warnings,
            "validation_ok": result.validation_ok,
            "package_base64": base64.b64encode(zip_bytes).decode("ascii"),
        }
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

    tmp_path: Optional[str] = None
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

    tmp_path: Optional[str] = None
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
        else:
            with engine.begin() as conn:
                import_result = import_hr_sync_package(
                    conn,
                    package_path=package_path,
                    apply_changes=True,
                    enforce_apply_gate=True,
                )

        return sync_apply_result_to_api_dict(
            import_result,
            preview_result,
            dry_run=dry_run,
            package_name=filename,
            notes=trimmed_notes,
        )
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
