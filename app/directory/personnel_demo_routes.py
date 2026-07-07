# FILE: app/directory/personnel_demo_routes.py
"""Personnel register routes.

Track B (personnel-events) is production-safe when ``employee_events`` exists.

ADR-034 professional documents demo API was retired in WP-CLEAN-005B (CCR-008).
Production documents use ADR-037 ``/directory/employee-documents*``.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.directory.rbac import require_personnel_admin_or_403
from app.services.directory_service import list_personnel_events as svc_list_personnel_events

from .common import as_http500, call_service

router = APIRouter()


@router.get("/personnel-events")
def list_personnel_events_register(
    event_type: Optional[str] = Query(default=None),
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    org_group_id: Optional[int] = Query(default=None, ge=1),
    org_unit_id: Optional[int] = Query(default=None, ge=1),
    position_id: Optional[int] = Query(default=None, ge=1),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Track B: organization-wide personnel event register."""
    try:
        require_personnel_admin_or_403(user)

        return call_service(
            svc_list_personnel_events,
            event_type=event_type,
            date_from=date_from,
            date_to=date_to,
            org_group_id=org_group_id,
            org_unit_id=org_unit_id,
            position_id=position_id,
            limit=limit,
            offset=offset,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise as_http500(e)
