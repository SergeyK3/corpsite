# FILE: app/directory/personnel_demo_routes.py
"""Personnel register routes.

Track B (personnel-events) is production-safe when ``employee_events`` exists.
ADR-034 professional documents are local-demo-only (optional demo tables).
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.security.directory_scope import is_privileged as _is_privileged
from app.services.directory_service import list_personnel_events as svc_list_personnel_events
from app.services.professional_documents_service import (
    list_professional_documents_demo,
    professional_documents_available,
)

from .common import as_http500, call_service

router = APIRouter()


@router.get("/personnel-events")
def list_personnel_events_register(
    event_type: Optional[str] = Query(default=None),
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Track B: organization-wide personnel event register."""
    try:
        if not _is_privileged(user):
            raise HTTPException(status_code=403, detail="Forbidden.")

        return call_service(
            svc_list_personnel_events,
            event_type=event_type,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)


@router.get("/professional-documents/availability")
def professional_documents_availability(
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, bool]:
    """Whether local ADR-034 demo tables are installed."""
    return {"available": professional_documents_available()}


@router.get("/professional-documents")
def list_professional_documents(
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """ADR-034 local demo: professional documents register (empty when tables absent)."""
    try:
        if not _is_privileged(user):
            raise HTTPException(status_code=403, detail="Forbidden.")

        return call_service(list_professional_documents_demo)
    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)
