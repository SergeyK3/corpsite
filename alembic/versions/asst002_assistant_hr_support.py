"""Explicit assistant HR support permissions, preserving standalone restrictions."""
from alembic import op
from sqlalchemy import text

revision = "asst002"
down_revision = "asst001"
branch_labels = None
depends_on = None

NEW_PERMISSIONS = {
    "ASSISTANT_HR_SUPPORT": "Assistant: personnel processes and organization-wide HR support",
    "ASSISTANT_PERSONNEL_CARD_EDIT": "Assistant: personnel card corrections",
    "ASSISTANT_HR_EXPORT": "Assistant: authorized directory and personnel Excel exports",
    **{f"ASSISTANT_PPR_STAGE{i}_MANAGE": f"Assistant: PPR migration stage {i}" for i in range(4)},
}
SUPPORT_READ_PERMISSIONS = (
    "CONTROL_LIST_EXPORT", "PPR_MIGRATION_STATUS_READ", "VIEW_TRAINING_CERTIFICATE_DETAILS",
)
REASON = "asst002: assistant HR support"


def upgrade():
    conn = op.get_bind()
    for code, name in NEW_PERMISSIONS.items():
        conn.execute(text("""INSERT INTO public.access_roles
            (code,name,description,access_level,level_rank,is_system)
            VALUES (:code,:name,:name,'MANAGER',20,TRUE) ON CONFLICT(code) DO NOTHING"""),
            {"code": code, "name": name})
    # Existing independently provisioned assistants keep their primary role and identity.
    # USER grants, rather than inherited HR_HEAD or administrative roles.
    conn.execute(text("""INSERT INTO public.access_grants
        (access_role_id,target_type,target_id,resource_key,scope_type,include_subtree,
         starts_at,active_flag,granted_by_user_id,reason)
        SELECT a.access_role_id,'USER',u.user_id,'*','GLOBAL',FALSE,now(),TRUE,
               (SELECT user_id FROM public.users WHERE role_id=2 AND is_active=TRUE
                ORDER BY user_id LIMIT 1),:reason
        FROM public.users u JOIN public.roles r USING(role_id)
        CROSS JOIN public.access_roles a
        WHERE r.code='SYSADMIN_ASSISTANT' AND a.code=ANY(:codes)
          AND NOT EXISTS (SELECT 1 FROM public.access_grants g
            WHERE g.target_type='USER' AND g.target_id=u.user_id
              AND g.access_role_id=a.access_role_id AND g.active_flag=TRUE
              AND g.revoked_at IS NULL AND g.starts_at<=now()
              AND (g.ends_at IS NULL OR g.ends_at>now()))"""),
        {"reason": REASON, "codes": [*NEW_PERMISSIONS, *SUPPORT_READ_PERMISSIONS]})
    conn.execute(text("""INSERT INTO public.audit_log
        (actor_user_id,entity,entity_id,action,before_data,after_data)
        SELECT g.granted_by_user_id,'access_grants',g.grant_id,'ASSISTANT_HR_SUPPORT_GRANTED',
               NULL,jsonb_build_object('permission',a.code,'target_user_id',g.target_id)
        FROM public.access_grants g JOIN public.access_roles a USING(access_role_id)
        WHERE g.reason=:reason"""), {"reason": REASON})


def downgrade():
    # Do not remove permission definitions or grants provisioned later by administrators.
    op.get_bind().execute(text("""UPDATE public.access_grants
        SET active_flag=FALSE,revoked_at=now() WHERE reason=:reason AND revoked_at IS NULL"""),
        {"reason": REASON})
