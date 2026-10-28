"""Medical qualification directory has no mutation endpoints."""
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, Query
from app.auth import get_current_user
from app.services.medical_qualification_categories_service import list_categories
from .common import as_http500, call_service
from .rbac import require_personnel_admin_or_403

router = APIRouter()


@router.get("/medical-qualification-categories")
def get_medical_qualification_categories(
    q: Optional[str] = Query(default=None, max_length=500),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    require_personnel_admin_or_403(user)
    try:
        return call_service(list_categories, q=q)
    except Exception as exc:
        raise as_http500(exc)
