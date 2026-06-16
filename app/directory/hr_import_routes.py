# FILE: app/directory/hr_import_routes.py
"""HR control list import staging — analytics and upload (ADR-038 Analytics MVP)."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response

from app.auth import get_current_user
from app.db.engine import engine
from app.directory.rbac import require_privileged_or_403
from app.services.hr_import_analytics_service import (
    BatchNotFoundError,
    age_distribution,
    batch_summary,
    certification_analytics,
    delete_batch,
    department_analytics,
    list_batch_rows,
    list_batches,
    position_analytics,
    risk_analytics,
    sheet_diagnostics,
    training_analytics,
)
from app.services.hr_import_document_candidate_service import (
    document_candidates_summary,
    education_portfolio,
    employee_training_history,
    list_document_candidates,
    rebuild_document_candidates,
)
from app.services.department_recoding_service import list_recoding_options, seed_department_recoding
from app.services.hr_import_ai_extraction_service import run_ai_extraction
from app.services.hr_import_education_profile_service import (
    archive_education_profile,
    get_education_profile,
    list_education_profiles,
    update_education_profile,
)
from app.services.hr_import_row_review_service import export_declarations_excel, get_row_review_detail

from app.services.hr_import_service import import_control_list

from .common import as_http500, call_service

router = APIRouter()


def _with_conn(fn, **kwargs):
    with engine.begin() as conn:
        return fn(conn, **kwargs)


def _batch_not_found(exc: BatchNotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


@router.get("/personnel/import/batches")
def get_import_batches(
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    require_privileged_or_403(user)
    try:
        return _with_conn(list_batches)
    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)


@router.delete("/personnel/import/batches/{batch_id}")
def delete_import_batch(
    batch_id: int,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    require_privileged_or_403(user)
    try:
        return _with_conn(delete_batch, batch_id=batch_id)
    except BatchNotFoundError as e:
        raise _batch_not_found(e)
    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)


@router.get("/personnel/import/batches/{batch_id}/summary")
def get_import_batch_summary(
    batch_id: int,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    require_privileged_or_403(user)
    try:
        return _with_conn(batch_summary, batch_id=batch_id)
    except BatchNotFoundError as e:
        raise _batch_not_found(e)
    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)


@router.get("/personnel/import/batches/{batch_id}/age-distribution")
def get_import_batch_age_distribution(
    batch_id: int,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    require_privileged_or_403(user)
    try:
        return _with_conn(age_distribution, batch_id=batch_id)
    except BatchNotFoundError as e:
        raise _batch_not_found(e)
    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)


@router.get("/personnel/import/batches/{batch_id}/departments")
def get_import_batch_departments(
    batch_id: int,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    require_privileged_or_403(user)
    try:
        return _with_conn(department_analytics, batch_id=batch_id)
    except BatchNotFoundError as e:
        raise _batch_not_found(e)
    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)


@router.get("/personnel/import/batches/{batch_id}/positions")
def get_import_batch_positions(
    batch_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    require_privileged_or_403(user)
    try:
        return _with_conn(position_analytics, batch_id=batch_id, limit=limit)
    except BatchNotFoundError as e:
        raise _batch_not_found(e)
    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)


@router.get("/personnel/import/batches/{batch_id}/training")
def get_import_batch_training(
    batch_id: int,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    require_privileged_or_403(user)
    try:
        return _with_conn(training_analytics, batch_id=batch_id)
    except BatchNotFoundError as e:
        raise _batch_not_found(e)
    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)


@router.get("/personnel/import/batches/{batch_id}/certification")
def get_import_batch_certification(
    batch_id: int,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    require_privileged_or_403(user)
    try:
        return _with_conn(certification_analytics, batch_id=batch_id)
    except BatchNotFoundError as e:
        raise _batch_not_found(e)
    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)


@router.get("/personnel/import/batches/{batch_id}/risks")
def get_import_batch_risks(
    batch_id: int,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    require_privileged_or_403(user)
    try:
        return _with_conn(risk_analytics, batch_id=batch_id)
    except BatchNotFoundError as e:
        raise _batch_not_found(e)
    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)


@router.get("/personnel/import/batches/{batch_id}/sheet-diagnostics")
def get_import_batch_sheet_diagnostics(
    batch_id: int,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    require_privileged_or_403(user)
    try:
        return _with_conn(sheet_diagnostics, batch_id=batch_id)
    except BatchNotFoundError as e:
        raise _batch_not_found(e)
    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)


@router.get("/personnel/import/batches/{batch_id}/document-candidates")
def get_import_batch_document_candidates(
    batch_id: int,
    document_kind: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    department: Optional[str] = Query(default=None),
    q_name: Optional[str] = Query(default=None),
    has_hours: Optional[bool] = Query(default=None),
    has_valid_until: Optional[bool] = Query(default=None),
    no_link: Optional[bool] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    require_privileged_or_403(user)
    try:
        return _with_conn(
            list_document_candidates,
            batch_id=batch_id,
            document_kind=document_kind,
            status=status,
            department=department,
            q_name=q_name,
            has_hours=has_hours,
            has_valid_until=has_valid_until,
            no_link=no_link,
            limit=limit,
            offset=offset,
        )
    except BatchNotFoundError as e:
        raise _batch_not_found(e)
    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)


@router.get("/personnel/import/batches/{batch_id}/document-candidates/summary")
def get_import_batch_document_candidates_summary(
    batch_id: int,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    require_privileged_or_403(user)
    try:
        return _with_conn(document_candidates_summary, batch_id=batch_id)
    except BatchNotFoundError as e:
        raise _batch_not_found(e)
    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)


@router.post("/personnel/import/batches/{batch_id}/document-candidates/rebuild")
def post_import_batch_rebuild_document_candidates(
    batch_id: int,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    require_privileged_or_403(user)
    try:
        return _with_conn(rebuild_document_candidates, batch_id=batch_id)
    except BatchNotFoundError as e:
        raise _batch_not_found(e)
    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)


@router.get("/personnel/import/batches/{batch_id}/document-candidates/employees/{row_id}")
def get_import_batch_employee_training_history(
    batch_id: int,
    row_id: int,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    require_privileged_or_403(user)
    try:
        return _with_conn(employee_training_history, batch_id=batch_id, row_id=row_id)
    except BatchNotFoundError as e:
        raise _batch_not_found(e)
    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)


@router.get("/personnel/import/department-recoding/options")
def get_department_recoding_options(
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    require_privileged_or_403(user)
    try:
        return _with_conn(list_recoding_options)
    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)


@router.post("/personnel/import/department-recoding/seed")
def post_department_recoding_seed(
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    require_privileged_or_403(user)
    try:
        return _with_conn(seed_department_recoding)
    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)


@router.get("/personnel/import/batches/{batch_id}/education-portfolio")
def get_import_batch_education_portfolio(
    batch_id: int,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    require_privileged_or_403(user)
    try:
        return _with_conn(education_portfolio, batch_id=batch_id)
    except BatchNotFoundError as e:
        raise _batch_not_found(e)
    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)


@router.get("/personnel/import/batches/{batch_id}/education-profiles")
def get_import_batch_education_profiles(
    batch_id: int,
    org_unit_id: Optional[int] = Query(default=None),
    org_unit_name: Optional[str] = Query(default=None),
    q_name: Optional[str] = Query(default=None),
    include_archived: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    require_privileged_or_403(user)
    try:
        return _with_conn(
            list_education_profiles,
            batch_id=batch_id,
            org_unit_id=org_unit_id,
            org_unit_name=org_unit_name,
            q_name=q_name,
            include_archived=include_archived,
            limit=limit,
            offset=offset,
        )
    except BatchNotFoundError as e:
        raise _batch_not_found(e)
    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)


@router.get("/personnel/import/batches/{batch_id}/education-profiles/{profile_id}")
def get_import_batch_education_profile_detail(
    batch_id: int,
    profile_id: int,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    require_privileged_or_403(user)
    try:
        return _with_conn(get_education_profile, batch_id=batch_id, profile_id=profile_id)
    except BatchNotFoundError as e:
        raise _batch_not_found(e)
    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)


@router.patch("/personnel/import/batches/{batch_id}/education-profiles/{profile_id}")
def patch_import_batch_education_profile(
    batch_id: int,
    profile_id: int,
    body: Dict[str, Any] = Body(default={}),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    require_privileged_or_403(user)
    try:
        return _with_conn(
            update_education_profile,
            batch_id=batch_id,
            profile_id=profile_id,
            profile=body.get("profile"),
            review_status=body.get("review_status"),
            profile_status=body.get("profile_status"),
        )
    except BatchNotFoundError as e:
        raise _batch_not_found(e)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)


@router.post("/personnel/import/batches/{batch_id}/education-profiles/{profile_id}/archive")
def post_import_batch_education_profile_archive(
    batch_id: int,
    profile_id: int,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    require_privileged_or_403(user)
    try:
        return _with_conn(archive_education_profile, batch_id=batch_id, profile_id=profile_id)
    except BatchNotFoundError as e:
        raise _batch_not_found(e)
    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)


@router.get("/personnel/import/batches/{batch_id}/rows/{row_id}/review")
def get_import_batch_row_review(
    batch_id: int,
    row_id: int,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    require_privileged_or_403(user)
    try:
        return _with_conn(get_row_review_detail, batch_id=batch_id, row_id=row_id)
    except BatchNotFoundError as e:
        raise _batch_not_found(e)
    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)


@router.post("/personnel/import/batches/{batch_id}/rows/{row_id}/ai-extraction")
def post_import_batch_row_ai_extraction(
    batch_id: int,
    row_id: int,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    require_privileged_or_403(user)
    try:
        return _with_conn(run_ai_extraction, batch_id=batch_id, row_id=row_id)
    except BatchNotFoundError as e:
        raise _batch_not_found(e)
    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)


@router.get("/personnel/import/batches/{batch_id}/declarations/export")
def get_import_batch_declarations_export(
    batch_id: int,
    department_group: Optional[str] = Query(default=None),
    org_unit_id: Optional[int] = Query(default=None),
    staff_type: Optional[str] = Query(default=None),
    q_name: Optional[str] = Query(default=None),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Response:
    require_privileged_or_403(user)
    try:
        with engine.begin() as conn:
            content = export_declarations_excel(
                conn,
                batch_id,
                department_group=department_group,
                org_unit_id=org_unit_id,
                staff_type=staff_type,
                q_name=q_name,
            )
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="declarations_batch_{batch_id}.xlsx"'
            },
        )
    except BatchNotFoundError as e:
        raise _batch_not_found(e)
    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)


@router.get("/personnel/import/batches/{batch_id}/rows")
def get_import_batch_rows(
    batch_id: int,
    department: Optional[str] = Query(default=None),
    sheet_type: Optional[str] = Query(default=None),
    age_bucket: Optional[str] = Query(default=None),
    has_training: Optional[bool] = Query(default=None),
    has_certification: Optional[bool] = Query(default=None),
    risk_type: Optional[str] = Query(default=None),
    roster_scope: Optional[str] = Query(default=None),
    q_name: Optional[str] = Query(default=None),
    q_position: Optional[str] = Query(default=None),
    department_group: Optional[str] = Query(default=None),
    org_unit_id: Optional[int] = Query(default=None),
    org_unit_name: Optional[str] = Query(default=None),
    certification_category: Optional[str] = Query(default=None),
    staff_type: Optional[str] = Query(default=None),
    part_time: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    require_privileged_or_403(user)
    try:
        return _with_conn(
            list_batch_rows,
            batch_id=batch_id,
            department=department,
            sheet_type=sheet_type,
            age_bucket=age_bucket,
            has_training=has_training,
            has_certification=has_certification,
            risk_type=risk_type,
            roster_scope=roster_scope,
            q_name=q_name,
            q_position=q_position,
            department_group=department_group,
            org_unit_id=org_unit_id,
            org_unit_name=org_unit_name,
            certification_category=certification_category,
            staff_type=staff_type,
            part_time=part_time,
            limit=limit,
            offset=offset,
        )
    except BatchNotFoundError as e:
        raise _batch_not_found(e)
    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)


@router.post("/personnel/import/upload")
async def upload_import_control_list(
    file: UploadFile = File(...),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Stage HR control list Excel — no apply, no employee writes."""
    require_privileged_or_403(user)
    filename = (file.filename or "").strip()
    if not filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="Expected .xlsx control list file.")

    suffix = Path(filename).suffix or ".xlsx"
    tmp_path: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp_path = tmp.name
            content = await file.read()
            if not content:
                raise HTTPException(status_code=400, detail="Empty file.")
            tmp.write(content)

        imported_by = int(user["user_id"])
        with engine.begin() as conn:
            batch_id, summary, warnings = import_control_list(
                conn,
                file_path=tmp_path,
                imported_by=imported_by,
            )
        return {
            "batch_id": batch_id,
            "file_name": filename,
            "summary": summary,
            "warnings": warnings,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
