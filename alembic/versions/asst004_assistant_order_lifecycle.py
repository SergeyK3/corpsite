"""Non-deleting HR order lifecycle for standalone assistants."""
from alembic import op
from sqlalchemy import text

revision = "asst004"
down_revision = "asst003"
branch_labels = None
depends_on = None

REASON = "asst004: assistant non-deleting order lifecycle"
CODES = ["ASSISTANT_PERSONNEL_ORDERS_VOID", "PERSONNEL_ORDERS_CANCEL_OWN",
         "PERSONNEL_ORDERS_CANCEL_SCOPE", "PERSONNEL_ORDERS_ARCHIVE", "PERSONNEL_ORDERS_RESTORE"]


def upgrade():
    conn = op.get_bind()
    conn.execute(text("""INSERT INTO access_roles(code,name,description,access_level,level_rank,is_system)
        VALUES ('ASSISTANT_PERSONNEL_ORDERS_VOID','Assistant: audited order void',
          'Existing audited void workflow; never physical deletion','MANAGER',20,TRUE)
        ON CONFLICT(code) DO NOTHING"""))
    conn.execute(text("""INSERT INTO access_grants
        (access_role_id,target_type,target_id,granted_by_user_id,reason)
        SELECT a.access_role_id,'USER',u.user_id,
            (SELECT user_id FROM users WHERE role_id=2 AND is_active ORDER BY user_id LIMIT 1),:reason
        FROM users u JOIN roles r USING(role_id) CROSS JOIN access_roles a
        WHERE r.code='SYSADMIN_ASSISTANT' AND u.is_active AND a.code=ANY(:codes)
          AND NOT EXISTS(SELECT 1 FROM access_grants g WHERE g.target_type='USER'
            AND g.target_id=u.user_id AND g.access_role_id=a.access_role_id
            AND g.active_flag AND g.revoked_at IS NULL
            AND g.starts_at<=now() AND (g.ends_at IS NULL OR g.ends_at>now()))"""),
        {"codes": CODES, "reason": REASON})
    conn.execute(text("""INSERT INTO audit_log(actor_user_id,entity,entity_id,action,after_data)
        SELECT granted_by_user_id,'access_grants',grant_id,'ASSISTANT_ORDER_LIFECYCLE_GRANTED',
            jsonb_build_object('target_user_id',target_id,'permission',a.code)
        FROM access_grants g JOIN access_roles a USING(access_role_id) WHERE g.reason=:reason"""),
        {"reason": REASON})


def downgrade():
    op.get_bind().execute(text("""UPDATE access_grants SET active_flag=FALSE,revoked_at=now()
        WHERE reason=:reason AND revoked_at IS NULL"""), {"reason": REASON})
