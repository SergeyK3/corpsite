# FILE: app/directory/import_routes.py
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth import get_current_user
from app.security.directory_scope import is_privileged as _is_privileged
from app.services.directory_import_csv import import_employees_csv_bytes
from app.services.directory_import_xlsx import import_employees_xlsx_bytes

router = APIRouter()


@router.post("/import/employees_csv")
async def import_employees_csv(
    request: Request,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    # JWT-only: user comes from Authorization: Bearer <token>
    if not _is_privileged(user):
        raise HTTPException(status_code=403, detail="Forbidden.")

    try:
        raw = await request.body()
        return import_employees_csv_bytes(raw=raw)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"import error: {type(e).__name__}: {str(e)}")


@router.post("/import/employees_xlsx")
async def import_employees_xlsx(
    request: Request,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    # JWT-only: user comes from Authorization: Bearer <token>
    if not _is_privileged(user):
        raise HTTPException(status_code=403, detail="Forbidden.")

    try:
        raw = await request.body()
        return import_employees_xlsx_bytes(raw=raw)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"import xlsx error: {type(e).__name__}: {str(e)}")
