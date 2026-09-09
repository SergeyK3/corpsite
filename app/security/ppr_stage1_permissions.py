from fastapi import HTTPException
from app.security.admin_permissions import PPR_STAGE1_GENERAL_MANAGE_PERMISSION, has_admin_permission

def require_ppr_stage1_general_manage(user: dict) -> int:
    try: user_id = int(user['user_id'])
    except (KeyError, TypeError, ValueError) as exc: raise HTTPException(401, 'Unauthorized.') from exc
    if str(user.get('role_code') or '').upper() != 'HR_HEAD': raise HTTPException(403, 'HR_HEAD role required.')
    if not has_admin_permission(user_id, PPR_STAGE1_GENERAL_MANAGE_PERMISSION): raise HTTPException(403, 'PPR Stage 1 general permission required.')
    return user_id
