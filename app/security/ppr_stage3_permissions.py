from fastapi import HTTPException

from app.security.admin_permissions import (
    PPR_STAGE3_TRAINING_MANAGE_PERMISSION,
    VIEW_TRAINING_CERTIFICATE_DETAILS_PERMISSION,
    has_admin_permission,
)


def require_ppr_stage3_training_manage(user: dict) -> int:
    user_id = int(user.get("user_id") or 0)
    if str(user.get("role_code") or user.get("role") or "").upper() != "HR_HEAD":
        raise HTTPException(403, detail={"code": "PPR_STAGE3_TRAINING_PERMISSION_DENIED"})
    if not has_admin_permission(user_id, PPR_STAGE3_TRAINING_MANAGE_PERMISSION):
        raise HTTPException(403, detail={"code": "PPR_STAGE3_TRAINING_PERMISSION_DENIED"})
    return user_id


def can_view_training_certificate_details(user: dict) -> bool:
    return has_admin_permission(
        int(user.get("user_id") or 0), VIEW_TRAINING_CERTIFICATE_DETAILS_PERMISSION
    )
