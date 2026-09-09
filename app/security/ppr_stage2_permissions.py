from fastapi import HTTPException
from app.security.admin_permissions import PPR_STAGE2_EDUCATION_MANAGE_PERMISSION, has_admin_permission


def require_ppr_stage2_education_manage(user: dict) -> int:
    user_id = int(user.get("user_id") or 0)
    if str(user.get("role_code") or user.get("role") or "").upper() != "HR_HEAD":
        raise HTTPException(403, detail={"code": "PPR_STAGE2_EDUCATION_PERMISSION_DENIED", "message": "Требуется роль HR_HEAD."})
    if not has_admin_permission(user_id, PPR_STAGE2_EDUCATION_MANAGE_PERMISSION):
        raise HTTPException(403, detail={"code": "PPR_STAGE2_EDUCATION_PERMISSION_DENIED", "message": "Недостаточно прав для этапа образования."})
    return user_id
