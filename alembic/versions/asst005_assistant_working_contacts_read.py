"""Organization-wide read-only working contacts for standalone assistants."""
from alembic import op
from sqlalchemy import text

revision = "asst005"
down_revision = "asst004"
branch_labels = None
depends_on = None

CODE = "ASSISTANT_WORKING_CONTACTS_READ"
REASON = "asst005: assistant organization-wide working contacts read only"


def upgrade():
    conn = op.get_bind()
    conn.execute(text("""INSERT INTO public.access_roles
        (code,name,description,access_level,level_rank,is_system)
        VALUES (:code,'Assistant: working contacts read',
            'Read working contacts across the organization; no account or contact mutations',
            'OBSERVER',10,TRUE) ON CONFLICT(code) DO NOTHING"""), {"code": CODE})
    if conn.execute(text("""SELECT access_role_id FROM public.access_roles
        WHERE code=:code AND is_active AND access_level='OBSERVER' AND level_rank=10"""),
        {"code": CODE}).scalar_one_or_none() is None:
        raise RuntimeError("Assistant working contacts permission must be active OBSERVER/10")
    grants = conn.execute(text("""INSERT INTO public.access_grants
        (access_role_id,target_type,target_id,resource_key,scope_type,include_subtree,
         starts_at,active_flag,granted_by_user_id,reason)
        SELECT a.access_role_id,'USER',u.user_id,'*','GLOBAL',FALSE,now(),TRUE,
            (SELECT user_id FROM public.users WHERE role_id=2 AND is_active ORDER BY user_id LIMIT 1),:reason
        FROM public.users u JOIN public.roles r USING(role_id)
        CROSS JOIN public.access_roles a
        WHERE r.code='SYSADMIN_ASSISTANT' AND u.is_active AND a.code=:code
          AND NOT EXISTS(SELECT 1 FROM public.access_grants g
            WHERE g.target_type='USER' AND g.target_id=u.user_id
              AND g.access_role_id=a.access_role_id AND g.active_flag
              AND g.revoked_at IS NULL AND g.starts_at<=now()
              AND (g.ends_at IS NULL OR g.ends_at>now()))
        RETURNING grant_id,target_id,granted_by_user_id"""),
        {"code": CODE, "reason": REASON}).mappings().all()
    for grant in grants:
        conn.execute(text("""INSERT INTO public.audit_log
            (actor_user_id,entity,entity_id,action,after_data)
            VALUES (:actor,'access_grants',:id,'ASSISTANT_WORKING_CONTACTS_READ_GRANTED',
                jsonb_build_object('target_user_id',:target,'permission',:code))"""),
            {"actor": grant["granted_by_user_id"], "id": grant["grant_id"],
             "target": grant["target_id"], "code": CODE})


def downgrade():
    op.get_bind().execute(text("""UPDATE public.access_grants
        SET active_flag=FALSE,revoked_at=now() WHERE reason=:reason AND revoked_at IS NULL"""),
        {"reason": REASON})
